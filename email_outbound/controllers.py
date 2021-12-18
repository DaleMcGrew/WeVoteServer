# email_outbound/controllers.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from .functions import merge_message_content_with_template
from .models import EmailAddress, EmailManager, EmailOutboundDescription, EmailScheduled,\
    GENERIC_EMAIL_TEMPLATE, LINK_TO_SIGN_IN_TEMPLATE, SendGridApiCounterManager, \
    SIGN_IN_CODE_EMAIL_TEMPLATE, TO_BE_PROCESSED, VERIFY_EMAIL_ADDRESS_TEMPLATE
from config.base import get_environment_variable
from concurrent.futures import ThreadPoolExecutor, as_completed
from exception.models import handle_exception
import json
from organization.controllers import transform_web_app_url
from organization.models import OrganizationManager, INDIVIDUAL
from ratelimit import limits, sleep_and_retry
import requests
from validate_email import validate_email
from voter.models import VoterContactEmail, VoterDeviceLinkManager, VoterManager
import wevote_functions.admin
from wevote_functions.functions import is_voter_device_id_valid, positive_value_exists

logger = wevote_functions.admin.get_logger(__name__)

SENDGRID_API_KEY = get_environment_variable("SENDGRID_API_KEY", no_exception=True)
SENDGRID_EMAIL_VALIDATION_API_KEY = get_environment_variable("SENDGRID_EMAIL_VALIDATION_API_KEY", no_exception=True)
SENDGRID_EMAIL_VALIDATION_URL = "https://api.sendgrid.com/v3/validations/email"
SENDGRID_LIMIT_PER_SECOND = 7
WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")


def augment_email_address_list(email_address_list, voter):
    email_address_list_augmented = []
    primary_email_address = None
    primary_email_address_found = False

    status = ""
    success = True
    for email_address in email_address_list:
        is_primary_email_address = False
        if email_address.we_vote_id == voter.primary_email_we_vote_id:
            is_primary_email_address = True
            primary_email_address_found = True
            primary_email_address = email_address
        elif email_address.normalized_email_address == voter.email:
            is_primary_email_address = True
            primary_email_address_found = True
            primary_email_address = email_address
        email_address_for_json = {
            'normalized_email_address': email_address.normalized_email_address,
            'primary_email_address': is_primary_email_address,
            'email_permanent_bounce': email_address.email_permanent_bounce,
            'email_ownership_is_verified': email_address.email_ownership_is_verified,
            'voter_we_vote_id': email_address.voter_we_vote_id,
            'email_we_vote_id': email_address.we_vote_id,
        }
        email_address_list_augmented.append(email_address_for_json)

    voter_manager = VoterManager()
    if primary_email_address_found:
        # Make sure the voter's cached "email" and "primary_email_we_vote_id" are both correct and match same email
        voter_data_updated = False
        if voter.primary_email_we_vote_id and \
                voter.primary_email_we_vote_id.lower() != primary_email_address.we_vote_id.lower():
            voter.primary_email_we_vote_id = primary_email_address.we_vote_id
            voter_data_updated = True
        if voter.email and voter.email.lower() != primary_email_address.normalized_email_address.lower():
            voter.email = primary_email_address.normalized_email_address
            voter_data_updated = True

        if voter_data_updated:
            try:
                voter.save()
                status += "SAVED_UPDATED_EMAIL_VALUES "
            except Exception as e:
                # We could get this exception if the EmailAddress table has email X for voter 1
                # and the voter table stores the same email X for voter 2
                status += "UNABLE_TO_SAVE_UPDATED_EMAIL_VALUES"
                remove_cached_results = \
                    voter_manager.remove_voter_cached_email_entries_from_email_address_object(primary_email_address)
                status += remove_cached_results['status']
                try:
                    voter.primary_email_we_vote_id = primary_email_address.we_vote_id
                    voter.email_ownership_is_verified = True
                    voter.email = primary_email_address.normalized_email_address
                    voter.save()
                    status += "SAVED_UPDATED_EMAIL_VALUES2 "
                    success = True
                except Exception as e:
                    status += "UNABLE_TO_SAVE_UPDATED_EMAIL_VALUES2 "
    else:
        # If here we need to heal data. If here we know that the voter record doesn't have any email info that matches
        #  an email address, so we want to make the first email address in the list the new master
        for primary_email_address_candidate in email_address_list:
            if primary_email_address_candidate.email_ownership_is_verified:
                # Now that we have found a verified email, save it to the voter account, and break out of loop
                voter.primary_email_we_vote_id = primary_email_address_candidate.we_vote_id
                voter.email = primary_email_address_candidate.normalized_email_address
                voter.email_ownership_is_verified = True
                try:
                    voter.save()
                    status += "SAVED_PRIMARY_EMAIL_ADDRESS_CANDIDATE"
                except Exception as e:
                    status += "UNABLE_TO_SAVE_PRIMARY_EMAIL_ADDRESS_CANDIDATE"
                    remove_cached_results = \
                        voter_manager.remove_voter_cached_email_entries_from_email_address_object(
                            primary_email_address_candidate)
                    status += remove_cached_results['status']
                    try:
                        voter.primary_email_we_vote_id = primary_email_address_candidate.we_vote_id
                        voter.email_ownership_is_verified = True
                        voter.email = primary_email_address_candidate.normalized_email_address
                        voter.save()
                        status += "SAVED_PRIMARY_EMAIL_ADDRESS_CANDIDATE2 "
                        success = True
                    except Exception as e:
                        status += "UNABLE_TO_SAVE_PRIMARY_EMAIL_ADDRESS_CANDIDATE2 "
                break

    results = {
        'status':                           status,
        'success':                          success,
        'email_address_list':               email_address_list_augmented,
    }
    return results


# 2021-09-30 SendGrid email verification requires Pro account which costs $90/month - Turned on as of 2021-12
def augment_emails_for_voter_with_sendgrid(voter_we_vote_id=''):
    status = ''
    success = True

    api_counter_manager = SendGridApiCounterManager()
    voter_manager = VoterManager()
    # Augment all voter contacts with data from SendGrid
    voter_contact_results = voter_manager.retrieve_voter_contact_email_list(
        imported_by_voter_we_vote_id=voter_we_vote_id,
        include_invalid=True)
    if not voter_contact_results['voter_contact_email_list_found']:
        status += "NO_EMAILS_TO_AUGMENT_WITH_SENDGRID "
        results = {
            'success': success,
            'status': status,
        }
        return results

    all_emails_text_list = voter_contact_results['email_addresses_returned_list']

    # Note: We rely on email_outbound/controller.py augment_emails_for_voter_with_we_vote_data having
    #  created a contact_email_augmented entry for every one of these emails previously

    # Get list of emails which need to be augmented (updated) with data from SendGrid
    results = voter_manager.retrieve_contact_email_augmented_list(
        checked_against_sendgrid_more_than_x_days_ago=365,
        email_address_text_list=all_emails_text_list,
        read_only=False,
    )
    contact_email_augmented_list = results['contact_email_augmented_list']
    contact_email_augmented_list_as_dict = results['contact_email_augmented_list_as_dict']
    email_addresses_returned_list = results['email_addresses_returned_list']
    email_addresses_remaining_list = email_addresses_returned_list

    if len(email_addresses_remaining_list) == 0:
        status += "NO_MORE_EMAILS_TO_CHECK_AGAINST_SENDGRID "
    else:
        # Now reach out to SendGrid, in blocks of 200
        failed_api_count = 0
        loop_count = 0
        safety_valve_triggered = False
        number_of_outer_loop_executions_allowed = 60  # 2100 total = 60 loops * 35 number_executed_per_block
        number_executed_per_block = 35  # 7 per second * 5 seconds
        while len(email_addresses_remaining_list) > 0 and not safety_valve_triggered:
            loop_count += 1
            safety_valve_triggered = loop_count >= number_of_outer_loop_executions_allowed
            email_address_list_chunk = email_addresses_remaining_list[:number_executed_per_block]
            email_addresses_remaining_list = list(set(email_addresses_remaining_list) - set(email_address_list_chunk))

            if len(email_address_list_chunk) == 0:
                break

            sendgrid_results = query_sendgrid_api_to_augment_email_list(email_list=email_address_list_chunk)
            number_of_items_sent_in_query = sendgrid_results['number_of_items_sent_in_query']
            if not sendgrid_results['success']:
                failed_api_count += 1
                if failed_api_count >= 3:
                    safety_valve_triggered = True
                    status += "SENDGRID_API_FAILED_3_TIMES "
            elif sendgrid_results['email_results_found']:
                # A dict of results from Sendgrid, with email_address_text as the key
                email_results_dict = sendgrid_results['email_results_dict']

                # Update our cached augmented data
                for contact_email_augmented in contact_email_augmented_list:
                    if contact_email_augmented.email_address_text in email_results_dict:
                        augmented_email = email_results_dict[contact_email_augmented.email_address_text]
                        augmented_email_found = positive_value_exists(augmented_email['augmented_email_found']) \
                            if 'augmented_email_found' in augmented_email else False
                        if augmented_email_found:
                            is_invalid = positive_value_exists(augmented_email['is_invalid']) \
                                if 'is_invalid' in augmented_email else None
                            results = voter_manager.update_or_create_contact_email_augmented(
                                checked_against_sendgrid=True,
                                email_address_text=contact_email_augmented.email_address_text,
                                existing_contact_email_augmented_dict=contact_email_augmented_list_as_dict,
                                is_invalid=is_invalid,
                            )
                            if not results['success']:
                                status += results['status']
                            # And update the VoterContactEmail
                            defaults = {
                                'is_invalid': contact_email_augmented.is_invalid,
                            }
                            try:
                                number_updated = VoterContactEmail.objects.filter(
                                    email_address_text__iexact=contact_email_augmented.email_address_text) \
                                    .update(**defaults)
                                status += "NUMBER_OF_VOTER_CONTACT_EMAIL_UPDATED-SENDGRID: " + str(number_updated) + " "
                            except Exception as e:
                                status += "NUMBER_OF_VOTER_CONTACT_EMAIL_NOT_UPDATED-SENDGRID: " + str(e) + " "

            # Use SendGrid API call counter to track the number of queries we are doing each day
            if positive_value_exists(number_of_items_sent_in_query):
                api_counter_manager.create_counter_entry(
                    'EmailVerificationAPI',
                    number_of_items_sent_in_query=number_of_items_sent_in_query)

    results = {
        'success': success,
        'status': status,
    }
    return results


def augment_emails_for_voter_with_we_vote_data(voter_we_vote_id=''):
    status = ''
    success = True

    from voter.models import VoterManager
    voter_manager = VoterManager()
    # Augment all voter contacts with updated data from We Vote
    voter_contact_results = voter_manager.retrieve_voter_contact_email_list(
        imported_by_voter_we_vote_id=voter_we_vote_id)
    if voter_contact_results['voter_contact_email_list_found']:
        email_addresses_returned_list = voter_contact_results['email_addresses_returned_list']

        # Get list of emails which need to be augmented (updated) with data
        #  We need to do this for later steps where we reach out to other services like Open People Search and Twilio
        contact_email_augmented_list_as_dict = {}
        results = voter_manager.retrieve_contact_email_augmented_list(
            email_address_text_list=email_addresses_returned_list,
            read_only=False,
        )
        if results['contact_email_augmented_list_found']:
            # We retrieve all existing at once so we don't need 200 separate queries
            #  within update_or_create_contact_email_augmented
            contact_email_augmented_list_as_dict = results['contact_email_augmented_list_as_dict']

        # Make sure we have an augmented entry for each email
        for email_address_text in email_addresses_returned_list:
            if email_address_text.lower() not in contact_email_augmented_list_as_dict:
                voter_manager.update_or_create_contact_email_augmented(
                    email_address_text=email_address_text,
                    existing_contact_email_augmented_dict=contact_email_augmented_list_as_dict)

        # Now augment VoterContactEmail table with data from the We Vote database to help find friends
        # Start by retrieving checking EmailAddress table (in one query) for all entries we currently have in our db
        email_addresses_found_list = []
        try:
            queryset = EmailAddress.objects.filter(normalized_email_address__in=email_addresses_returned_list)
            queryset = queryset.filter(email_ownership_is_verified=True)
            email_addresses_found_list = list(queryset)
        except Exception as e:
            status += "FAILED_TO_RETRIEVE_EMAIL_ADDRESSES: " + str(e) + ' '

        for email_address_object in email_addresses_found_list:
            # Retrieve the voter to see if there is data to use in the VoterContactEmail table
            results = voter_manager.retrieve_voter_by_we_vote_id(email_address_object.voter_we_vote_id)
            if results['voter_found']:
                voter = results['voter']
                voter_data_found = positive_value_exists(voter.we_vote_hosted_profile_image_url_medium) or \
                    positive_value_exists(voter.we_vote_id)
                if results['success'] and voter_data_found:
                    # Now update all of the VoterContactEmail entries, irregardless of whose contact it is
                    try:
                        number_updated = VoterContactEmail.objects.filter(
                            email_address_text__iexact=email_address_object.normalized_email_address) \
                            .update(
                                voter_we_vote_id=voter.we_vote_id,
                                we_vote_hosted_profile_image_url_medium=voter.we_vote_hosted_profile_image_url_medium)
                        status += "NUMBER_OF_VOTER_CONTACT_EMAIL_UPDATED: " + str(number_updated) + " "
                    except Exception as e:
                        status += "FAILED_TO_UPDATE_VOTER_CONTACT_EMAIL: " + str(e) + ' '

    results = {
        'success': success,
        'status': status,
    }
    return results


def delete_email_address_entries_for_voter(voter_to_delete_we_vote_id, voter_to_delete):
    status = "DELETE_EMAIL_ADDRESSES "
    success = False
    email_addresses_deleted = 0
    email_addresses_not_deleted = 0

    if not positive_value_exists(voter_to_delete_we_vote_id):
        status += "DELETE_EMAIL_ADDRESS_ENTRIES_MISSING_FROM_VOTER_WE_VOTE_ID "
        results = {
            'status':                       status,
            'success':                      success,
            'voter_to_delete_we_vote_id':   voter_to_delete_we_vote_id,
            'voter_to_delete':              voter_to_delete,
            'email_addresses_deleted':      email_addresses_deleted,
            'email_addresses_not_deleted':  email_addresses_not_deleted,
        }
        return results

    email_manager = EmailManager()
    email_address_list_results = email_manager.retrieve_voter_email_address_list(voter_to_delete_we_vote_id)
    if email_address_list_results['email_address_list_found']:
        email_address_list = email_address_list_results['email_address_list']

        for email_address_object in email_address_list:
            try:
                email_address_object.delete()
                email_addresses_deleted += 1
            except Exception as e:
                email_addresses_not_deleted += 1
                status += "UNABLE_TO_DELETE_EMAIL_ADDRESS " + str(e) + " "

        status += "EMAIL_ADDRESSES-DELETED: " + str(email_addresses_deleted) + \
                  ", NOT_DELETED: " + str(email_addresses_not_deleted) + " "
    else:
        status += email_address_list_results['status']

    if positive_value_exists(voter_to_delete.primary_email_we_vote_id):
        # Remove the email information so we don't have a future conflict
        try:
            voter_to_delete.email = None
            voter_to_delete.primary_email_we_vote_id = None
            voter_to_delete.email_ownership_is_verified = False
            voter_to_delete.save()
        except Exception as e:
            status += "CANNOT_CLEAR_OUT_VOTER_EMAIL_INFO: " + str(e) + " "

    results = {
        'status':                       status,
        'success':                      success,
        'voter_to_delete':              voter_to_delete,
        'voter_to_delete_we_vote_id':   voter_to_delete_we_vote_id,
        'email_addresses_deleted':      email_addresses_deleted,
        'email_addresses_not_deleted':  email_addresses_not_deleted,
    }
    return results


def heal_primary_email_data_for_voter(email_address_list, voter):
    primary_email_address = None
    primary_email_address_found = False
    primary_email_address_we_vote_id = None

    status = ""
    success = True
    for email_address in email_address_list:
        if not primary_email_address_found:
            if email_address.we_vote_id == voter.primary_email_we_vote_id:
                primary_email_address_found = True
                primary_email_address = email_address
                primary_email_address_we_vote_id = primary_email_address.we_vote_id
            elif email_address.normalized_email_address == voter.email:
                primary_email_address_found = True
                primary_email_address = email_address
                primary_email_address_we_vote_id = primary_email_address.we_vote_id

    voter_manager = VoterManager()
    if primary_email_address_found:
        # Make sure the voter's cached "email" and "primary_email_we_vote_id" are both correct and match same email
        voter_data_updated = False
        if not voter.primary_email_we_vote_id:
            voter.primary_email_we_vote_id = primary_email_address_we_vote_id
            voter_data_updated = True
        elif voter.primary_email_we_vote_id and \
                voter.primary_email_we_vote_id.lower() != primary_email_address_we_vote_id.lower():
            voter.primary_email_we_vote_id = primary_email_address_we_vote_id
            voter_data_updated = True
        if not voter.email:
            voter.email = primary_email_address.normalized_email_address
            voter_data_updated = True
        elif voter.email and voter.email.lower() != primary_email_address.normalized_email_address.lower():
            voter.email = primary_email_address.normalized_email_address
            voter_data_updated = True

        if voter_data_updated:
            try:
                voter.save()
                status += "SAVED_UPDATED_EMAIL_VALUES "
            except Exception as e:
                # We could get this exception if the EmailAddress table has email X for voter 1
                # and the voter table stores the same email X for voter 2
                status += "UNABLE_TO_SAVE_UPDATED_EMAIL_VALUES " + str(e) + " "
                remove_cached_results = \
                    voter_manager.remove_voter_cached_email_entries_from_email_address_object(primary_email_address)
                status += remove_cached_results['status']
                try:
                    voter.primary_email_we_vote_id = primary_email_address_we_vote_id
                    voter.email_ownership_is_verified = True
                    voter.email = primary_email_address.normalized_email_address
                    voter.save()
                    status += "SAVED_UPDATED_EMAIL_VALUES2 "
                    success = True
                except Exception as e:
                    status += "UNABLE_TO_SAVE_UPDATED_EMAIL_VALUES2 " + str(e) + " "
    else:
        # If here we need to heal data. If here we know that the voter record doesn't have any email info that matches
        #  an email address, so we want to make the first verified email address in the list the new master
        for primary_email_address_candidate in email_address_list:
            if primary_email_address_candidate.email_ownership_is_verified:
                # Now that we have found a verified email, save it to the voter account, and break out of loop
                voter.primary_email_we_vote_id = primary_email_address_candidate.we_vote_id
                voter.email = primary_email_address_candidate.normalized_email_address
                voter.email_ownership_is_verified = True
                try:
                    voter.save()
                    status += "SAVED_PRIMARY_EMAIL_ADDRESS_CANDIDATE "
                except Exception as e:
                    status += "UNABLE_TO_SAVE_PRIMARY_EMAIL_ADDRESS_CANDIDATE " + str(e) + " "
                    remove_cached_results = \
                        voter_manager.remove_voter_cached_email_entries_from_email_address_object(
                            primary_email_address_candidate)
                    status += remove_cached_results['status']
                    try:
                        voter.primary_email_we_vote_id = primary_email_address_candidate.we_vote_id
                        voter.email_ownership_is_verified = True
                        voter.email = primary_email_address_candidate.normalized_email_address
                        voter.save()
                        status += "SAVED_PRIMARY_EMAIL_ADDRESS_CANDIDATE2 "
                        success = True
                    except Exception as e:
                        status += "UNABLE_TO_SAVE_PRIMARY_EMAIL_ADDRESS_CANDIDATE2 " + str(e) + " "
                break

    email_address_list_deduped = []
    for email_address in email_address_list:
        add_to_list = True
        is_primary_email_address = False
        if positive_value_exists(email_address.we_vote_id) and positive_value_exists(primary_email_address_we_vote_id):
            if email_address.we_vote_id == voter.primary_email_we_vote_id or \
                    email_address.we_vote_id == primary_email_address_we_vote_id:
                is_primary_email_address = True
        if not is_primary_email_address:
            if primary_email_address_found and hasattr(primary_email_address, "normalized_email_address"):
                # See if this email is the same as the primary email address
                if positive_value_exists(email_address.normalized_email_address) \
                        and positive_value_exists(primary_email_address.normalized_email_address):
                    if email_address.normalized_email_address.lower() == \
                            primary_email_address.normalized_email_address.lower():
                        # We want to get rid of this email
                        add_to_list = False
                        pass
        if add_to_list:
            email_address_list_deduped.append(email_address)

    results = {
        'status':               status,
        'success':              success,
        'email_address_list':   email_address_list_deduped,
    }
    return results


def move_email_address_entries_to_another_voter(from_voter_we_vote_id, to_voter_we_vote_id, from_voter, to_voter):
    status = "MOVE_EMAIL_ADDRESSES "
    success = False
    email_addresses_moved = 0
    email_addresses_not_moved = 0

    if not positive_value_exists(from_voter_we_vote_id) or not positive_value_exists(to_voter_we_vote_id):
        status += "MOVE_EMAIL_ADDRESS_ENTRIES_MISSING_FROM_OR_TO_VOTER_ID "
        results = {
            'status': status,
            'success': success,
            'from_voter_we_vote_id': from_voter_we_vote_id,
            'to_voter_we_vote_id': to_voter_we_vote_id,
            'from_voter': from_voter,
            'to_voter': to_voter,
            'email_addresses_moved': email_addresses_moved,
            'email_addresses_not_moved': email_addresses_not_moved,
        }
        return results

    if from_voter_we_vote_id == to_voter_we_vote_id:
        status += "MOVE_EMAIL_ADDRESS_ENTRIES-IDENTICAL_FROM_AND_TO_VOTER_ID "
        results = {
            'status': status,
            'success': success,
            'from_voter_we_vote_id': from_voter_we_vote_id,
            'to_voter_we_vote_id': to_voter_we_vote_id,
            'from_voter': from_voter,
            'to_voter': to_voter,
            'email_addresses_moved': email_addresses_moved,
            'email_addresses_not_moved': email_addresses_not_moved,
        }
        return results

    email_manager = EmailManager()
    email_address_list_results = email_manager.retrieve_voter_email_address_list(from_voter_we_vote_id)
    if email_address_list_results['email_address_list_found']:
        email_address_list = email_address_list_results['email_address_list']

        for email_address_object in email_address_list:
            # Change the voter_we_vote_id
            try:
                email_address_object.voter_we_vote_id = to_voter_we_vote_id
                email_address_object.save()
                email_addresses_moved += 1
            except Exception as e:
                email_addresses_not_moved += 1
                status += "UNABLE_TO_SAVE_EMAIL_ADDRESS "

        status += "MOVE_EMAIL_ADDRESSES-MOVED: " + str(email_addresses_moved) + \
                  ", NOT_MOVED: " + str(email_addresses_not_moved) + " "
    else:
        status += email_address_list_results['status']

    # Now clean up the list of emails
    merge_results = email_manager.find_and_merge_all_duplicate_emails(to_voter_we_vote_id)
    status += merge_results['status']

    email_results = email_manager.retrieve_voter_email_address_list(to_voter_we_vote_id)
    status += email_results['status']
    if email_results['email_address_list_found']:
        email_address_list_found = True
        email_address_list = email_results['email_address_list']

        # Make sure the voter's primary email address matches email table data
        merge_results = heal_primary_email_data_for_voter(email_address_list, to_voter)
        email_address_list = merge_results['email_address_list']
        status += merge_results['status']

    if positive_value_exists(from_voter.primary_email_we_vote_id):
        # Remove the email information so we don't have a future conflict
        try:
            from_voter.email = None
            from_voter.primary_email_we_vote_id = None
            from_voter.email_ownership_is_verified = False
            from_voter.save()
        except Exception as e:
            status += "CANNOT_CLEAR_OUT_VOTER_EMAIL_INFO: " + str(e) + " "

    # Update EmailOutboundDescription entries: Sender
    try:
        email_scheduled_queryset = EmailOutboundDescription.objects.all()
        email_scheduled_queryset.filter(sender_voter_we_vote_id=from_voter_we_vote_id).\
            update(sender_voter_we_vote_id=to_voter_we_vote_id)
        status += 'UPDATED_EMAIL_OUTBOUND-SENDER '
    except Exception as e:
        success = False
        status += 'FAILED_UPDATE_EMAIL_OUTBOUND-SENDER ' + str(e) + " "
    # Recipient
    try:
        email_scheduled_queryset = EmailOutboundDescription.objects.all()
        email_scheduled_queryset.filter(recipient_voter_we_vote_id=from_voter_we_vote_id).\
            update(recipient_voter_we_vote_id=to_voter_we_vote_id)
        status += 'UPDATED_EMAIL_OUTBOUND-RECIPIENT '
    except Exception as e:
        success = False
        status += 'FAILED_UPDATE_EMAIL_OUTBOUND-RECIPIENT ' + str(e) + " "

    # Update EmailScheduled entries: Sender
    try:
        email_scheduled_queryset = EmailScheduled.objects.all()
        email_scheduled_queryset.filter(sender_voter_we_vote_id=from_voter_we_vote_id).\
            update(sender_voter_we_vote_id=to_voter_we_vote_id)
        status += 'UPDATED_EMAIL_SCHEDULED-SENDER '
    except Exception as e:
        success = False
        status += 'FAILED_UPDATE_EMAIL_SCHEDULED-SENDER ' + str(e) + " "
    # Recipient
    try:
        email_scheduled_queryset = EmailScheduled.objects.all()
        email_scheduled_queryset.filter(recipient_voter_we_vote_id=from_voter_we_vote_id).\
            update(recipient_voter_we_vote_id=to_voter_we_vote_id)
        status += 'UPDATED_EMAIL_SCHEDULED-RECIPIENT '
    except Exception as e:
        success = False
        status += 'FAILED_UPDATE_EMAIL_SCHEDULED-RECIPIENT ' + str(e) + " "

    results = {
        'status': status,
        'success': success,
        'from_voter': from_voter,
        'from_voter_we_vote_id': from_voter_we_vote_id,
        'to_voter_we_vote_id': to_voter_we_vote_id,
        'to_voter': to_voter,
        'email_addresses_moved': email_addresses_moved,
        'email_addresses_not_moved': email_addresses_not_moved,
    }
    return results


# 2021-09-30 SendGrid email verification requires Pro account which costs $90/month - Turned on as of 2021-12
def query_sendgrid_api_to_augment_email_list(email_list=None):
    success = True
    status = ""
    email_results_dict = {}
    email_results_found = False
    number_of_items_sent_in_query = 0

    if email_list is None or not len(email_list) > 0:
        status += "MISSING_EMAIL_LIST_FOR_SENDGRID "
        success = False
        results = {
            'success':                          success,
            'status':                           status,
            'email_results_found':              email_results_found,
            'email_results_dict':               email_results_dict,
            'number_of_items_sent_in_query':    number_of_items_sent_in_query,
        }
        return results

    # Linear for testing
    # for one_email in email_list:
    #     one_result = {}
    #     number_of_items_sent_in_query += 1
    #     try:
    #         one_result = query_and_extract_from_sendgrid_email_verification_api(email=one_email)
    #         email_address = one_result['email_address_text']
    #         email_address = email_address.lower()
    #         email_results_dict[email_address] = one_result
    #         if one_result['augmented_email_found']:
    #             email_results_found = True
    #     except Exception as e:
    #         status += one_result['status'] if 'status' in one_result else ''
    #         status += "CRASHING_ERROR: " + str(e) + ' '

    # Multi-thread for production
    threads = []
    with ThreadPoolExecutor(max_workers=7) as executor:
        for email in email_list:
            threads.append(executor.submit(query_and_extract_from_sendgrid_email_verification_api, email))
            number_of_items_sent_in_query += 1

        for task in as_completed(threads):
            try:
                one_result = task.result()
                email_address = one_result['email_address_text']
                email_address = email_address.lower()
                email_results_dict[email_address] = one_result
                if one_result['augmented_email_found']:
                    email_results_found = True
            except Exception as e:
                status += one_result['status'] if 'status' in one_result else ''
                status += "CRASHING_ERROR: " + str(e) + ' '

    results = {
        'success':                          success,
        'status':                           status,
        'email_results_found':              email_results_found,
        'email_results_dict':               email_results_dict,
        'number_of_items_sent_in_query':    number_of_items_sent_in_query,
    }
    return results


@sleep_and_retry
@limits(calls=SENDGRID_LIMIT_PER_SECOND, period=1)
def query_and_extract_from_sendgrid_email_verification_api(email=''):
    success = True
    status = ""
    augmented_email_found = False
    json_from_sendgrid = {}

    if not positive_value_exists(email):
        status += "MISSING_EMAIL_FROM_SENDGRID "
        success = False
        results = {
            'success':                  success,
            'status':                   status,
            'augmented_email_found':    augmented_email_found,
            'is_invalid':               None,
        }
        return results

    try:
        json_from_sendgrid = query_sendgrid_email_verification_api(email=email)

        if 'errors' in json_from_sendgrid:
            success = False
            status += "[ERRORS: " + str(json_from_sendgrid['errors']) + "] "
    except Exception as e:
        success = False
        status += 'QUERY_SENDGRID_EMAIL_VERIFICATION_API_FAILED: ' + str(e) + ' '
        handle_exception(e, logger=logger, exception_message=status)

    if success:
        print(str(json_from_sendgrid))
        result = json_from_sendgrid['result'] if 'result' in json_from_sendgrid else {}
        augmented_email_found = 'result' in json_from_sendgrid
        verdict = result['verdict'] if 'verdict' in result else ''
        is_invalid = verdict in ['Invalid']
    else:
        augmented_email_found = False
        is_invalid = False

    results = {
        'success':                  success,
        'status':                   status,
        'augmented_email_found':    augmented_email_found,
        'email_address_text':       email,
        'is_invalid':               is_invalid,
    }
    return results


@sleep_and_retry
@limits(calls=SENDGRID_LIMIT_PER_SECOND, period=1)
def query_sendgrid_email_verification_api(email=''):
    try:
        url = SENDGRID_EMAIL_VALIDATION_URL
        payload = "{\"email\":\"" + email + "\"}"
        headers = {
            'authorization': "Bearer " + SENDGRID_EMAIL_VALIDATION_API_KEY,
            'content-type': "application/json",
        }
        response = requests.request("POST", url, data=payload, headers=headers)
        if response.status_code == 503:
            print("ERROR_QUERY_SENDGRID_EMAIL: " + str(response.status_code) + ": " + str(response.text))
            return {}
        else:
            structured_json = json.loads(response.text)
    except Exception as e:
        print("ERROR_QUERY_SENDGRID_EMAIL_VERIFICATION: " + str(e))
        return {}
    return structured_json


def schedule_email_with_email_outbound_description(email_outbound_description, send_status=TO_BE_PROCESSED):
    email_manager = EmailManager()
    status = ""

    template_variables_in_json = email_outbound_description.template_variables_in_json
    if positive_value_exists(email_outbound_description.kind_of_email_template):
        kind_of_email_template = email_outbound_description.kind_of_email_template
    else:
        kind_of_email_template = GENERIC_EMAIL_TEMPLATE

    email_template_results = merge_message_content_with_template(kind_of_email_template, template_variables_in_json)
    if email_template_results['success']:
        subject = email_template_results['subject']
        message_text = email_template_results['message_text']
        message_html = email_template_results['message_html']
        schedule_email_results = email_manager.schedule_email(email_outbound_description, subject,
                                                              message_text, message_html, send_status)
        success = schedule_email_results['success']
        status += schedule_email_results['status']
        email_scheduled_saved = schedule_email_results['email_scheduled_saved']
        email_scheduled = schedule_email_results['email_scheduled']
        email_scheduled_id = schedule_email_results['email_scheduled_id']
    else:
        success = False
        status += "SCHEDULE_EMAIL_TEMPLATE_NOT_PROCESSED "
        status += email_template_results['status'] + " "
        email_scheduled_saved = False
        email_scheduled = EmailScheduled()
        email_scheduled_id = 0

    results = {
        'success': success,
        'status': status,
        'email_scheduled_saved': email_scheduled_saved,
        'email_scheduled_id': email_scheduled_id,
        'email_scheduled': email_scheduled,
    }
    return results


def schedule_verification_email(
        sender_voter_we_vote_id='',
        recipient_voter_we_vote_id='',
        recipient_email_we_vote_id='',
        recipient_voter_email='',
        recipient_email_address_secret_key='',
        recipient_email_subscription_secret_key='',
        web_app_root_url=''):
    """
    When a voter adds a new email address for self, create and send an outbound email with a link
    that the voter can click to verify the email.
    :param sender_voter_we_vote_id:
    :param recipient_voter_we_vote_id:
    :param recipient_email_we_vote_id:
    :param recipient_voter_email:
    :param recipient_email_address_secret_key:
    :param recipient_email_subscription_secret_key:
    :param web_app_root_url:
    :return:
    """
    email_scheduled_saved = False
    email_scheduled_sent = False
    email_scheduled_id = 0

    email_manager = EmailManager()
    status = ""
    kind_of_email_template = VERIFY_EMAIL_ADDRESS_TEMPLATE
    web_app_root_url_verified = transform_web_app_url(web_app_root_url)  # Change to client URL if needed

    # Generate secret key if needed
    if not positive_value_exists(recipient_email_address_secret_key):
        recipient_email_address_secret_key = email_manager.update_email_address_with_new_secret_key(
            recipient_email_we_vote_id)

    if not positive_value_exists(recipient_email_address_secret_key):
        results = {
            'status': "SCHEDULE_VERIFICATION-MISSING_EMAIL_SECRET_KEY ",
            'success': False,
            'email_scheduled_saved': email_scheduled_saved,
            'email_scheduled_sent': email_scheduled_sent,
            'email_scheduled_id': email_scheduled_id,
        }
        return results

    subject = "Please verify your email"

    template_variables_for_json = {
        "subject":                      subject,
        "recipient_voter_email":        recipient_voter_email,
        "we_vote_url":                  web_app_root_url_verified,
        "verify_email_link":
            web_app_root_url_verified + "/verify_email/" + recipient_email_address_secret_key,
        "recipient_unsubscribe_url":    web_app_root_url_verified + "/settings/notifications/esk/" +
            recipient_email_subscription_secret_key,
        "email_open_url":               WE_VOTE_SERVER_ROOT_URL + "/apis/v1/emailOpen?email_key=1234",
    }
    template_variables_in_json = json.dumps(template_variables_for_json, ensure_ascii=True)
    verification_from_email = "We Vote <info@WeVote.US>"  # TODO DALE Make system variable

    outbound_results = email_manager.create_email_outbound_description(
        sender_voter_we_vote_id=sender_voter_we_vote_id,
        sender_voter_email=verification_from_email,
        sender_voter_name='',
        recipient_voter_we_vote_id=recipient_voter_we_vote_id,
        recipient_email_we_vote_id=recipient_email_we_vote_id,
        recipient_voter_email=recipient_voter_email,
        template_variables_in_json=template_variables_in_json,
        kind_of_email_template=kind_of_email_template)
    status += outbound_results['status'] + " "
    if outbound_results['email_outbound_description_saved']:
        email_outbound_description = outbound_results['email_outbound_description']

        schedule_results = schedule_email_with_email_outbound_description(email_outbound_description)
        status += schedule_results['status'] + " "
        email_scheduled_saved = schedule_results['email_scheduled_saved']
        email_scheduled_id = schedule_results['email_scheduled_id']
        email_scheduled = schedule_results['email_scheduled']

        if email_scheduled_saved:
            send_results = email_manager.send_scheduled_email(email_scheduled)
            email_scheduled_sent = send_results['email_scheduled_sent']

    results = {
        'status':                   status,
        'success':                  True,
        'email_scheduled_saved':    email_scheduled_saved,
        'email_scheduled_sent':     email_scheduled_sent,
        'email_scheduled_id':       email_scheduled_id,
    }
    return results


def schedule_link_to_sign_in_email(
        sender_voter_we_vote_id='',
        recipient_voter_we_vote_id='',
        recipient_email_we_vote_id='',
        recipient_voter_email='',
        recipient_email_address_secret_key='',
        recipient_email_subscription_secret_key='',
        is_cordova=False,
        web_app_root_url=''):
    """
    When a voter wants to sign in with a pre-existing email, create and send an outbound email with a link
    that the voter can click to sign in.
    :param sender_voter_we_vote_id:
    :param recipient_voter_we_vote_id:
    :param recipient_email_we_vote_id:
    :param recipient_voter_email:
    :param recipient_email_address_secret_key:
    :param recipient_email_subscription_secret_key:
    :param is_cordova:
    :param web_app_root_url:
    :return:
    """
    email_scheduled_saved = False
    email_scheduled_sent = False
    email_scheduled_id = 0

    email_manager = EmailManager()
    status = ""
    kind_of_email_template = LINK_TO_SIGN_IN_TEMPLATE
    web_app_root_url_verified = transform_web_app_url(web_app_root_url)  # Change to client URL if needed

    # Generate secret key if needed
    if not positive_value_exists(recipient_email_address_secret_key):
        recipient_email_address_secret_key = email_manager.update_email_address_with_new_secret_key(
            recipient_email_we_vote_id)

    if not positive_value_exists(recipient_email_address_secret_key):
        results = {
            'status': "SCHEDULE_LINK_TO_SIGN_IN-MISSING_EMAIL_SECRET_KEY ",
            'success': False,
            'email_scheduled_saved': email_scheduled_saved,
            'email_scheduled_sent': email_scheduled_sent,
            'email_scheduled_id': email_scheduled_id,
        }
        return results

    subject = "Sign in link you requested"
    link_to_sign_in = web_app_root_url_verified + "/sign_in_email/" + recipient_email_address_secret_key
    if is_cordova:
        link_to_sign_in = "wevotetwitterscheme://sign_in_email/" + recipient_email_address_secret_key

    template_variables_for_json = {
        "subject":                      subject,
        "recipient_voter_email":        recipient_voter_email,
        "we_vote_url":                  web_app_root_url_verified,
        "link_to_sign_in":              link_to_sign_in,
        "recipient_unsubscribe_url":    web_app_root_url_verified + "/settings/notifications/esk/" +
        recipient_email_subscription_secret_key,
        "email_open_url":               WE_VOTE_SERVER_ROOT_URL + "/apis/v1/emailOpen?email_key=1234",
    }
    template_variables_in_json = json.dumps(template_variables_for_json, ensure_ascii=True)
    verification_from_email = "We Vote <info@WeVote.US>"  # TODO DALE Make system variable

    outbound_results = email_manager.create_email_outbound_description(
        sender_voter_we_vote_id=sender_voter_we_vote_id,
        sender_voter_email=verification_from_email,
        recipient_voter_we_vote_id=recipient_voter_we_vote_id,
        recipient_email_we_vote_id=recipient_email_we_vote_id,
        recipient_voter_email=recipient_voter_email,
        template_variables_in_json=template_variables_in_json,
        kind_of_email_template=kind_of_email_template)
    status += outbound_results['status'] + " "
    if outbound_results['email_outbound_description_saved']:
        email_outbound_description = outbound_results['email_outbound_description']

        schedule_results = schedule_email_with_email_outbound_description(email_outbound_description)
        status += schedule_results['status'] + " "
        email_scheduled_saved = schedule_results['email_scheduled_saved']
        email_scheduled_id = schedule_results['email_scheduled_id']
        email_scheduled = schedule_results['email_scheduled']

        if email_scheduled_saved:
            send_results = email_manager.send_scheduled_email(email_scheduled)
            email_scheduled_sent = send_results['email_scheduled_sent']

    results = {
        'status':                   status,
        'success':                  True,
        'email_scheduled_saved':    email_scheduled_saved,
        'email_scheduled_sent':     email_scheduled_sent,
        'email_scheduled_id':       email_scheduled_id,
    }
    return results


def schedule_sign_in_code_email(
        sender_voter_we_vote_id='',
        recipient_voter_we_vote_id='',
        recipient_email_we_vote_id='',
        recipient_voter_email='',
        secret_numerical_code='',
        recipient_email_subscription_secret_key='',
        web_app_root_url=''):
    """
    When a voter wants to sign in with a pre-existing email, create and send an outbound email with a secret
    code that can be entered into the interface where the code was requested.
    :param sender_voter_we_vote_id:
    :param recipient_voter_we_vote_id:
    :param recipient_email_we_vote_id:
    :param recipient_voter_email:
    :param secret_numerical_code:
    :param recipient_email_subscription_secret_key:
    :param web_app_root_url:
    :return:
    """
    email_scheduled_saved = False
    email_scheduled_sent = False
    email_scheduled_id = 0

    email_manager = EmailManager()
    status = ""
    kind_of_email_template = SIGN_IN_CODE_EMAIL_TEMPLATE
    web_app_root_url_verified = transform_web_app_url(web_app_root_url)  # Change to client URL if needed

    if not positive_value_exists(secret_numerical_code):
        results = {
            'status': "SCHEDULE_SIGN_IN_CODE_EMAIL-MISSING_EMAIL_SECRET_NUMERICAL_CODE ",
            'success': False,
            'email_scheduled_saved': email_scheduled_saved,
            'email_scheduled_sent': email_scheduled_sent,
            'email_scheduled_id': email_scheduled_id,
        }
        return results

    subject = "Your Sign in Code"

    template_variables_for_json = {
        "subject":                      subject,
        "recipient_voter_email":        recipient_voter_email,
        "we_vote_url":                  web_app_root_url_verified,
        "secret_numerical_code":        secret_numerical_code,
        "recipient_unsubscribe_url":    web_app_root_url_verified + "/settings/notifications/esk/" +
        recipient_email_subscription_secret_key,
        "email_open_url":               WE_VOTE_SERVER_ROOT_URL + "/apis/v1/emailOpen?email_key=1234",
    }
    template_variables_in_json = json.dumps(template_variables_for_json, ensure_ascii=True)
    verification_from_email = "We Vote <info@WeVote.US>"  # TODO DALE Make system variable

    outbound_results = email_manager.create_email_outbound_description(
        sender_voter_we_vote_id=sender_voter_we_vote_id,
        sender_voter_email=verification_from_email,
        recipient_voter_we_vote_id=recipient_voter_we_vote_id,
        recipient_email_we_vote_id=recipient_email_we_vote_id,
        recipient_voter_email=recipient_voter_email,
        template_variables_in_json=template_variables_in_json,
        kind_of_email_template=kind_of_email_template)
    status += outbound_results['status']
    if outbound_results['email_outbound_description_saved']:
        email_outbound_description = outbound_results['email_outbound_description']

        schedule_results = schedule_email_with_email_outbound_description(email_outbound_description)
        status += schedule_results['status']
        status += "SCHEDULE_EMAIL_WITH_OUTBOUND_DESCRIPTION_SENT "
        email_scheduled_saved = schedule_results['email_scheduled_saved']
        email_scheduled_id = schedule_results['email_scheduled_id']
        email_scheduled = schedule_results['email_scheduled']

        if email_scheduled_saved:
            status += "EMAIL_SCHEDULED_SAVED "
            send_results = email_manager.send_scheduled_email(email_scheduled)
            status += send_results['status']
            email_scheduled_sent = send_results['email_scheduled_sent']
        else:
            status += "EMAIL_SCHEDULED_NOT_SAVED "
    else:
        status += "EMAIL_OUTBOUND_DESCRIPTION_NOT_SAVED "

    results = {
        'status':                   status,
        'success':                  True,
        'email_scheduled_saved':    email_scheduled_saved,
        'email_scheduled_sent':     email_scheduled_sent,
        'email_scheduled_id':       email_scheduled_id,
    }
    return results


def voter_email_address_retrieve_for_api(voter_device_id):  # voterEmailAddressRetrieve
    """
    :param voter_device_id:
    :return:
    """
    email_address_list_found = False
    status = ""
    success = True

    # If a voter_device_id is passed in that isn't valid, we want to throw an error
    device_id_results = is_voter_device_id_valid(voter_device_id)
    if not device_id_results['success']:
        json_data = {
            'status':                           device_id_results['status'],
            'success':                          False,
            'voter_device_id':                  voter_device_id,
            'email_address_list_found':         False,
            'email_address_list':               [],
        }
        return json_data

    voter_manager = VoterManager()
    voter_results = voter_manager.retrieve_voter_from_voter_device_id(voter_device_id)
    voter_id = voter_results['voter_id']
    if not positive_value_exists(voter_id):
        error_results = {
            'status':                           "VOTER_NOT_FOUND_FROM_VOTER_DEVICE_ID",
            'success':                          False,
            'voter_device_id':                  voter_device_id,
            'email_address_list_found':         False,
            'email_address_list':               [],
        }
        return error_results
    voter = voter_results['voter']
    voter_we_vote_id = voter.we_vote_id

    email_manager = EmailManager()
    merge_results = email_manager.find_and_merge_all_duplicate_emails(voter_we_vote_id)
    status += merge_results['status']

    email_address_list_augmented = []
    email_results = email_manager.retrieve_voter_email_address_list(voter_we_vote_id)
    status += email_results['status']
    if email_results['email_address_list_found']:
        email_address_list_found = True
        email_address_list = email_results['email_address_list']

        # Make sure the voter's primary email address matches email table data
        merge_results = heal_primary_email_data_for_voter(email_address_list, voter)
        email_address_list = merge_results['email_address_list']
        status += merge_results['status']

        augment_results = augment_email_address_list(email_address_list, voter)
        email_address_list_augmented = augment_results['email_address_list']
        status += augment_results['status']

    json_data = {
        'status':                           status,
        'success':                          success,
        'voter_device_id':                  voter_device_id,
        'email_address_list_found':         email_address_list_found,
        'email_address_list':               email_address_list_augmented,
    }
    return json_data


def voter_email_address_sign_in_for_api(voter_device_id, email_secret_key):  # voterEmailAddressSignIn
    """
    :param voter_device_id:
    :param email_secret_key:
    :return:
    """
    email_secret_key_belongs_to_this_voter = False
    status = ""
    success = False

    # If a voter_device_id is passed in that isn't valid, we want to throw an error
    device_id_results = is_voter_device_id_valid(voter_device_id)
    if not device_id_results['success']:
        json_data = {
            'status':                                   device_id_results['status'],
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
            'voter_we_vote_id_from_secret_key':         "",
        }
        return json_data

    if not positive_value_exists(email_secret_key):
        error_results = {
            'status':                                   "VOTER_EMAIL_ADDRESS_VERIFY_MISSING_SECRET_KEY",
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
            'voter_we_vote_id_from_secret_key':         "",
        }
        return error_results

    voter_manager = VoterManager()
    voter_results = voter_manager.retrieve_voter_from_voter_device_id(voter_device_id)
    voter_id = voter_results['voter_id']
    if not positive_value_exists(voter_id):
        error_results = {
            'status':                                   "VOTER_NOT_FOUND_FROM_VOTER_DEVICE_ID",
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
            'voter_we_vote_id_from_secret_key':         "",
        }
        return error_results
    voter = voter_results['voter']
    voter_we_vote_id = voter.we_vote_id

    email_manager = EmailManager()
    # Look to see if there is an EmailAddress entry for the incoming text_for_email_address or email_we_vote_id
    email_results = email_manager.retrieve_email_address_object_from_secret_key(email_secret_key)
    if not email_results['email_address_object_found']:
        status += email_results['status']
        error_results = {
            'status':                                   status,
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
            'voter_we_vote_id_from_secret_key':         "",
        }
        return error_results

    success = email_results['success']
    status += email_results['status']
    email_address_object = email_results['email_address_object']
    email_address_found = True

    email_ownership_is_verified = email_address_object.email_ownership_is_verified
    if voter_we_vote_id == email_address_object.voter_we_vote_id:
        email_secret_key_belongs_to_this_voter = True

    json_data = {
        'status':                                   status,
        'success':                                  success,
        'voter_device_id':                          voter_device_id,
        'email_ownership_is_verified':              email_ownership_is_verified,
        'email_secret_key_belongs_to_this_voter':   email_secret_key_belongs_to_this_voter,
        'email_address_found':                      email_address_found,
        'voter_we_vote_id_from_secret_key':         email_address_object.voter_we_vote_id,
    }
    return json_data


def voter_email_address_verify_for_api(voter_device_id, email_secret_key):  # voterEmailAddressVerify
    """

    :param voter_device_id:
    :param email_secret_key:
    :return:
    """
    email_secret_key_belongs_to_this_voter = False
    voter_ownership_saved = False
    status = "ENTERING_VOTER_EMAIL_ADDRESS_VERIFY "
    success = False

    # If a voter_device_id is passed in that isn't valid, we want to throw an error
    device_id_results = is_voter_device_id_valid(voter_device_id)
    if not device_id_results['success']:
        status += device_id_results['status']
        json_data = {
            'status':                                   device_id_results['status'],
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
        }
        return json_data

    if not positive_value_exists(email_secret_key):
        status += "VOTER_EMAIL_ADDRESS_VERIFY_MISSING_SECRET_KEY "
        error_results = {
            'status':                                   status,
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
        }
        return error_results

    voter_manager = VoterManager()
    voter_results = voter_manager.retrieve_voter_from_voter_device_id(voter_device_id)
    voter_id = voter_results['voter_id']
    if not positive_value_exists(voter_id):
        status += "VOTER_NOT_FOUND_FROM_VOTER_DEVICE_ID "
        error_results = {
            'status':                                   status,
            'success':                                  False,
            'voter_device_id':                          voter_device_id,
            'email_ownership_is_verified':              False,
            'email_secret_key_belongs_to_this_voter':   False,
            'email_address_found':                      False,
        }
        return error_results
    voter = voter_results['voter']
    voter_we_vote_id = voter.we_vote_id

    email_manager = EmailManager()
    # Look to see if there is an EmailAddress entry for the incoming text_for_email_address or email_we_vote_id
    email_results = email_manager.verify_email_address_object_from_secret_key(email_secret_key)
    if email_results['email_address_object_found']:
        email_address_object = email_results['email_address_object']
        email_address_found = True
        status += "EMAIL_ADDRESS_FOUND_FROM_VERIFY "

        email_ownership_is_verified = email_address_object.email_ownership_is_verified
        if voter_we_vote_id == email_address_object.voter_we_vote_id:
            email_secret_key_belongs_to_this_voter = True
            voter_ownership_results = voter_manager.update_voter_email_ownership_verified(voter, email_address_object)
            voter_ownership_saved = voter_ownership_results['voter_updated']
            if voter_ownership_saved:
                voter = voter_ownership_results['voter']
        else:
            email_owner_results = voter_manager.retrieve_voter_by_we_vote_id(email_address_object.voter_we_vote_id)
            if email_owner_results['voter_found']:
                email_owner_voter = email_owner_results['voter']
                voter_manager.update_voter_email_ownership_verified(email_owner_voter, email_address_object)
                # If we verify it but don't use it to sign in, don't set voter_ownership_saved
                # (which invalidates email_secret_key below)
    else:
        email_results = email_manager.retrieve_email_address_object_from_secret_key(email_secret_key)
        if email_results['email_address_object_found']:
            status += "EMAIL_ADDRESS_FOUND_FROM_RETRIEVE "
            email_address_object = email_results['email_address_object']
            email_address_found = True

            email_ownership_is_verified = email_address_object.email_ownership_is_verified
            if voter_we_vote_id == email_address_object.voter_we_vote_id:
                email_secret_key_belongs_to_this_voter = True
                voter_ownership_results = voter_manager.update_voter_email_ownership_verified(voter,
                                                                                              email_address_object)
                voter_ownership_saved = voter_ownership_results['voter_updated']
                if voter_ownership_saved:
                    voter = voter_ownership_results['voter']
        else:
            status += "EMAIL_NOT_FOUND_FROM_SECRET_KEY "
            error_results = {
                'status':                                   status,
                'success':                                  False,
                'voter_device_id':                          voter_device_id,
                'email_ownership_is_verified':              False,
                'email_secret_key_belongs_to_this_voter':   False,
                'email_address_found':                      False,
            }
            return error_results

    organization_manager = OrganizationManager()
    if voter_ownership_saved:
        if not positive_value_exists(voter.linked_organization_we_vote_id):
            # Create new organization
            organization_name = voter.get_full_name()
            organization_image = voter.voter_photo_url()
            organization_type = INDIVIDUAL
            create_results = organization_manager.create_organization(
                organization_name=organization_name,
                organization_image=organization_image,
                organization_type=organization_type,
                we_vote_hosted_profile_image_url_large=voter.we_vote_hosted_profile_image_url_large,
                we_vote_hosted_profile_image_url_medium=voter.we_vote_hosted_profile_image_url_medium,
                we_vote_hosted_profile_image_url_tiny=voter.we_vote_hosted_profile_image_url_tiny
            )
            if create_results['organization_created']:
                # Add value to twitter_owner_voter.linked_organization_we_vote_id when done.
                organization = create_results['organization']
                try:
                    voter.linked_organization_we_vote_id = organization.we_vote_id
                    voter.save()
                except Exception as e:
                    status += "UNABLE_TO_LINK_NEW_ORGANIZATION_TO_VOTER "

        # TODO DALE We want to invalidate the email_secret key used

    is_organization = False
    organization_full_name = ""
    if positive_value_exists(voter.linked_organization_we_vote_id):
        organization_results = organization_manager.retrieve_organization_from_we_vote_id(
            voter.linked_organization_we_vote_id)
        if organization_results['organization_found']:
            organization = organization_results['organization']
            if organization.is_organization():
                is_organization = True
                organization_full_name = organization.organization_name

    # send previous scheduled emails
    real_name_only = True
    from_voter_we_vote_id = email_address_object.voter_we_vote_id
    if is_organization:
        if positive_value_exists(organization_full_name) and 'Voter-' not in organization_full_name:
            # Only send if the organization name exists
            send_results = email_manager.send_scheduled_emails_waiting_for_verification(
                from_voter_we_vote_id, organization_full_name)
            status += send_results['status']
            # invitation_update_results = friend_manager.update_friend_data_with_name(
            #     from_voter_we_vote_id, organization_full_name)
        else:
            status += "CANNOT_SEND_SCHEDULED_EMAILS_WITHOUT_ORGANIZATION_NAME-EMAIL_CONTROLLER "
    elif positive_value_exists(voter.get_full_name(real_name_only)):
        # Only send if the sender's full name exists
        send_results = email_manager.send_scheduled_emails_waiting_for_verification(
            from_voter_we_vote_id, voter.get_full_name(real_name_only))
        status += send_results['status']
    else:
        status += "CANNOT_SEND_SCHEDULED_EMAILS_WITHOUT_NAME-EMAIL_CONTROLLER "

    json_data = {
        'status':                                   status,
        'success':                                  success,
        'voter_device_id':                          voter_device_id,
        'email_ownership_is_verified':              email_ownership_is_verified,
        'email_secret_key_belongs_to_this_voter':   email_secret_key_belongs_to_this_voter,
        'email_address_found':                      email_address_found,
    }
    return json_data


def voter_email_address_save_for_api(voter_device_id='',
                                     text_for_email_address='',
                                     incoming_email_we_vote_id='',
                                     send_link_to_sign_in=False,
                                     send_sign_in_code_email=False,
                                     resend_verification_email=False,
                                     resend_verification_code_email=False,
                                     make_primary_email=False,
                                     delete_email=False,
                                     is_cordova=False,
                                     web_app_root_url=''):
    """
    voterEmailAddressSave
    :param voter_device_id:
    :param text_for_email_address:
    :param incoming_email_we_vote_id:
    :param send_link_to_sign_in:
    :param send_sign_in_code_email:
    :param resend_verification_email:
    :param resend_verification_code_email:
    :param make_primary_email:
    :param delete_email:
    :param is_cordova:
    :param web_app_root_url:
    :return:
    """
    email_address_we_vote_id = ""
    email_address_saved_we_vote_id = ""
    email_address_created = False
    email_address_deleted = False
    email_address_not_valid = False
    verification_email_sent = False
    link_to_sign_in_email_sent = False
    sign_in_code_email_sent = False
    sign_in_code_email_already_valid = False
    send_verification_email = False
    email_address_found = False
    email_address_list_found = False
    recipient_email_address_secret_key = ""
    messages_to_send = []
    status = "VOTER_EMAIL_ADDRESS_SAVE-START "
    success = False

    # If a voter_device_id is passed in that isn't valid, we want to throw an error
    device_id_results = is_voter_device_id_valid(voter_device_id)
    if not device_id_results['success']:
        status += device_id_results['status'] + " VOTER_DEVICE_ID_NOT_VALID "
        json_data = {
            'status':                           status,
            'success':                          False,
            'voter_device_id':                  voter_device_id,
            'text_for_email_address':           text_for_email_address,
            'email_address_we_vote_id':         incoming_email_we_vote_id,
            'email_address_saved_we_vote_id':   "",
            'email_address_created':            False,
            'email_address_deleted':            False,
            'email_address_not_valid':          False,
            'verification_email_sent':          False,
            'link_to_sign_in_email_sent':       False,
            'sign_in_code_email_sent':          False,
            'email_address_already_owned_by_other_voter': False,
            'email_address_already_owned_by_this_voter': False,
            'email_address_found':              False,
            'email_address_list_found':         False,
            'email_address_list':               [],
            'secret_code_system_locked_for_this_voter_device_id': False,
        }
        return json_data

    # Is the text_for_email_address a valid email address?
    if positive_value_exists(incoming_email_we_vote_id):
        # We are happy
        pass
    elif positive_value_exists(text_for_email_address):
        if not validate_email(text_for_email_address):
            status += "VOTER_EMAIL_ADDRESS_SAVE_MISSING_VALID_EMAIL "
            error_results = {
                'status':                           status,
                'success':                          False,
                'voter_device_id':                  voter_device_id,
                'text_for_email_address':           text_for_email_address,
                'email_address_we_vote_id':         incoming_email_we_vote_id,
                'email_address_saved_we_vote_id':   "",
                'email_address_created':            False,
                'email_address_deleted':            False,
                'email_address_not_valid':          True,  # Signal that the email address wasn't valid
                'verification_email_sent':          False,
                'link_to_sign_in_email_sent':       False,
                'sign_in_code_email_sent':          False,
                'email_address_already_owned_by_other_voter': False,
                'email_address_already_owned_by_this_voter': False,
                'email_address_found':              False,
                'email_address_list_found':         False,
                'email_address_list':               [],
                'secret_code_system_locked_for_this_voter_device_id': False,
            }
            return error_results
    else:
        # We need EITHER incoming_email_we_vote_id or text_for_email_address
        status += "VOTER_EMAIL_ADDRESS_SAVE_MISSING_EMAIL "
        error_results = {
            'status':                           status,
            'success':                          False,
            'voter_device_id':                  voter_device_id,
            'text_for_email_address':           text_for_email_address,
            'email_address_we_vote_id':         "",
            'email_address_saved_we_vote_id':   incoming_email_we_vote_id,
            'email_address_created':            False,
            'email_address_deleted':            False,
            'email_address_not_valid':          False,
            'verification_email_sent':          False,
            'link_to_sign_in_email_sent':       False,
            'sign_in_code_email_sent':          False,
            'email_address_already_owned_by_other_voter': False,
            'email_address_already_owned_by_this_voter': False,
            'email_address_found':              False,
            'email_address_list_found':         False,
            'email_address_list':               [],
            'secret_code_system_locked_for_this_voter_device_id': False,
        }
        return error_results

    voter_manager = VoterManager()
    voter_results = voter_manager.retrieve_voter_from_voter_device_id(voter_device_id)
    voter_id = voter_results['voter_id']
    if not positive_value_exists(voter_id):
        status += "VOTER_NOT_FOUND_FROM_VOTER_DEVICE_ID "
        error_results = {
            'status':                           status,
            'success':                          False,
            'voter_device_id':                  voter_device_id,
            'text_for_email_address':           text_for_email_address,
            'email_address_we_vote_id':         "",
            'email_address_saved_we_vote_id':   "",
            'email_address_created':            False,
            'email_address_deleted':            False,
            'email_address_not_valid':          False,
            'verification_email_sent':          False,
            'link_to_sign_in_email_sent':       False,
            'sign_in_code_email_sent':          False,
            'email_address_already_owned_by_other_voter': False,
            'email_address_already_owned_by_this_voter': False,
            'email_address_found':              False,
            'email_address_list_found':         False,
            'email_address_list':               [],
            'secret_code_system_locked_for_this_voter_device_id': False,
        }
        return error_results
    voter = voter_results['voter']
    voter_we_vote_id = voter.we_vote_id

    email_manager = EmailManager()
    email_address_already_owned_by_this_voter = False
    email_address_already_owned_by_other_voter = False
    verified_email_address_object = EmailAddress()
    verified_email_address_we_vote_id = ""
    email_address_list = []
    # Is this email already verified by another account?
    temp_voter_we_vote_id = ""
    find_verified_email_results = email_manager.retrieve_primary_email_with_ownership_verified(
        temp_voter_we_vote_id, text_for_email_address)
    if find_verified_email_results['email_address_object_found']:
        verified_email_address_object = find_verified_email_results['email_address_object']
        verified_email_address_we_vote_id = verified_email_address_object.we_vote_id
        if verified_email_address_object.voter_we_vote_id != voter_we_vote_id:
            email_address_already_owned_by_other_voter = True

    if email_address_already_owned_by_other_voter:
        status += "EMAIL_ALREADY_OWNED "
        if send_link_to_sign_in or send_sign_in_code_email:
            email_address_we_vote_id = verified_email_address_object.we_vote_id
            email_address_saved_we_vote_id = ""
            text_for_email_address = verified_email_address_object.normalized_email_address
            if positive_value_exists(verified_email_address_object.secret_key):
                recipient_email_address_secret_key = verified_email_address_object.secret_key
                status += "EXISTING_SECRET_KEY_FOUND "
            else:
                recipient_email_address_secret_key = \
                    email_manager.update_email_address_with_new_secret_key(email_address_we_vote_id)
                if positive_value_exists(recipient_email_address_secret_key):
                    status += "NEW_SECRET_KEY_GENERATED "
                else:
                    status += "NEW_SECRET_KEY_COULD_NOT_BE_GENERATED "
            email_address_created = False
            email_address_found = True
        else:
            status += "EMAIL_ALREADY_OWNED_BY_ANOTHER_VOTER-NO_SEND "
            error_results = {
                'status': status,
                'success': True,
                'voter_device_id': voter_device_id,
                'text_for_email_address': text_for_email_address,
                'email_address_we_vote_id': verified_email_address_we_vote_id,
                'email_address_saved_we_vote_id': "",
                'email_address_created':        False,
                'email_address_deleted':        False,
                'email_address_not_valid':      False,
                'verification_email_sent':      False,
                'link_to_sign_in_email_sent':   False,
                'sign_in_code_email_sent':      False,
                'email_address_already_owned_by_other_voter': True,
                'email_address_already_owned_by_this_voter': False,
                'email_address_found':          True,
                'email_address_list_found':     False,
                'email_address_list':           [],
                'secret_code_system_locked_for_this_voter_device_id': False,
            }
            return error_results

    # Look to see if there is an EmailAddress entry for the incoming text_for_email_address or
    #  incoming_email_we_vote_id for this voter
    email_results = email_manager.retrieve_email_address_object(text_for_email_address, incoming_email_we_vote_id,
                                                                voter_we_vote_id)
    if email_results['email_address_object_found']:
        email_address_object = email_results['email_address_object']
        email_address_list.append(email_address_object)
    elif email_results['email_address_list_found']:
        # This email was used by more than one person
        email_address_list = email_results['email_address_list']

    # Clean up our email list
    # 1) Remove duplicates
    excess_email_objects = []
    filtered_email_address_list = []
    ownership_verified_email_object = None
    ownership_verified_emails = []
    ownership_not_verified_email_object = None
    ownership_not_verified_emails = []
    for email_address_object in email_address_list:
        if email_address_object.email_ownership_is_verified:
            if email_address_object.normalized_email_address not in ownership_verified_emails:
                ownership_verified_email_object = email_address_object
                ownership_verified_emails.append(email_address_object.normalized_email_address)
            else:
                excess_email_objects.append(email_address_object)
        else:
            if email_address_object.normalized_email_address not in ownership_not_verified_emails:
                ownership_not_verified_email_object = email_address_object
                ownership_not_verified_emails.append(email_address_object.normalized_email_address)
            else:
                excess_email_objects.append(email_address_object)

    if ownership_verified_email_object is not None:
        status += "VERIFIED_EMAIL_FOUND "
        filtered_email_address_list.append(ownership_verified_email_object)
        excess_email_objects.append(ownership_not_verified_email_object)
        if send_sign_in_code_email:
            sign_in_code_email_already_valid = True
    elif ownership_not_verified_email_object is not None:
        status += "UNVERIFIED_EMAIL_FOUND "
        filtered_email_address_list.append(ownership_not_verified_email_object)

    # Delete the duplicates from the database
    for email_address_object in excess_email_objects:
        try:
            email_address_object.delete()
        except Exception as e:
            status += "CANNOT_DELETE_EXCESS_EMAIL: " + str(e) + " "

    # Cycle through all EmailAddress entries with "text_for_email_address" or "incoming_email_we_vote_id"
    for email_address_object in filtered_email_address_list:
        email_address_already_owned_by_this_voter = True
        email_address_we_vote_id = email_address_object.we_vote_id
        email_address_saved_we_vote_id = ""
        text_for_email_address = email_address_object.normalized_email_address
        if positive_value_exists(email_address_object.secret_key):
            recipient_email_address_secret_key = email_address_object.secret_key
            status += "IN_LIST-SECRET_KEY_EXISTS "
        else:
            recipient_email_address_secret_key = \
                email_manager.update_email_address_with_new_secret_key(email_address_we_vote_id)
            if positive_value_exists(recipient_email_address_secret_key):
                status += "IN_LIST-NEW_SECRET_KEY_GENERATED "
            else:
                status += "IN_LIST-NEW_SECRET_KEY_COULD_NOT_BE_GENERATED "
        email_address_created = False
        email_address_found = True
        if delete_email:
            status += "STARTING_DELETE_EMAIL "
            # If this email is cached in a voter record, remove it as long as primary_email_we_vote_id
            # matches email_address_object.we_vote_id
            primary_email_address_deleted = False
            if positive_value_exists(voter.primary_email_we_vote_id) \
                    and voter.primary_email_we_vote_id.lower() == email_address_object.we_vote_id.lower():
                try:
                    voter.primary_email_we_vote_id = None
                    voter.email_ownership_is_verified = False
                    voter.email = None
                    voter.save()
                    primary_email_address_deleted = True
                    status += "VOTER_PRIMARY_EMAIL_ADDRESS_REMOVED "
                    success = True
                except Exception as e:
                    status += "UNABLE_TO_REMOVE_VOTER_PRIMARY_EMAIL_ADDRESS "
            try:
                email_address_object.delete()
                email_address_deleted = True
                status += "DELETED_EMAIL_ADDRESS "
                success = True
            except Exception as e:
                status += "UNABLE_TO_DELETE_EMAIL_ADDRESS "
                success = False

            if email_address_deleted:
                # Delete all other emails associated with this account that are not verified
                if positive_value_exists(text_for_email_address):
                    duplicate_results = email_manager.retrieve_email_address_object(
                        text_for_email_address, voter_we_vote_id=voter_we_vote_id)
                    if duplicate_results['email_address_object_found']:
                        email_address_object_to_delete = duplicate_results['email_address_object']
                        if not positive_value_exists(email_address_object_to_delete.email_ownership_is_verified):
                            try:
                                email_address_object_to_delete.delete()
                                status += "DELETED_ONE_DUP_EMAIL_ADDRESS "
                            except Exception as e:
                                status += "UNABLE_TO_DELETE_ONE_DUP_EMAIL_ADDRESS "
                    elif duplicate_results['email_address_list_found']:
                        email_address_list_for_delete = duplicate_results['email_address_list']
                        for email_address_object_to_delete in email_address_list_for_delete:
                            if not positive_value_exists(email_address_object_to_delete.email_ownership_is_verified):
                                try:
                                    email_address_object_to_delete.delete()
                                    status += "DELETED_DUP_EMAIL_ADDRESS_IN_LIST "
                                except Exception as e:
                                    status += "UNABLE_TO_DELETE_DUP_EMAIL_ADDRESS_IN_LIST "

                # If there are any other verified emails, promote the first one to be the voter's verified email
                if positive_value_exists(primary_email_address_deleted):
                    email_promotion_results = email_manager.retrieve_voter_email_address_list(voter_we_vote_id)
                    email_address_list_for_promotion = []
                    if email_promotion_results['email_address_list_found']:
                        # This email was used by more than one person
                        email_address_list_for_promotion = email_promotion_results['email_address_list']
                        email_address_list_found_for_promotion_to_primary = True
                    else:
                        email_address_list_found_for_promotion_to_primary = False

                    if email_address_list_found_for_promotion_to_primary:
                        for email_address_object_for_promotion in email_address_list_for_promotion:
                            if positive_value_exists(
                                    email_address_object_for_promotion.email_ownership_is_verified):
                                # Assign this as voter's new primary email
                                try:
                                    voter.primary_email_we_vote_id = email_address_object_for_promotion.we_vote_id
                                    voter.email_ownership_is_verified = True
                                    voter.email = email_address_object_for_promotion.normalized_email_address
                                    voter.save()
                                    status += "SAVED_EMAIL_ADDRESS_AS_NEW_PRIMARY "
                                    success = True
                                except Exception as e:
                                    status += "UNABLE_TO_SAVE_EMAIL_ADDRESS_AS_NEW_PRIMARY "
                                    remove_cached_results = \
                                        voter_manager.remove_voter_cached_email_entries_from_email_address_object(
                                            email_address_object_for_promotion)
                                    status += remove_cached_results['status']
                                    try:
                                        voter.primary_email_we_vote_id = email_address_object_for_promotion.we_vote_id
                                        voter.email_ownership_is_verified = True
                                        voter.email = email_address_object_for_promotion.normalized_email_address
                                        voter.save()
                                        status += "SAVED_EMAIL_ADDRESS_AS_NEW_PRIMARY "
                                        success = True
                                    except Exception as e:
                                        status += "UNABLE_TO_REMOVE_VOTER_PRIMARY_EMAIL_ADDRESS2 "
                                break  # Stop looking at email addresses to make the new primary

            break  # TODO DALE Is there ever a case where we want to delete more than one email at a time?
        elif make_primary_email and positive_value_exists(incoming_email_we_vote_id):
            status += "STARTING_MAKE_PRIMARY_EMAIL "
            # We know we want to make incoming_email_we_vote_id the primary email
            if not email_address_object.email_ownership_is_verified:
                # Do not make an unverified email primary
                status += "DO_NOT_MAKE_UNVERIFIED_EMAIL_PRIMARY "
            elif email_address_object.we_vote_id.lower() == incoming_email_we_vote_id.lower():
                # Make sure this isn't already the primary
                if positive_value_exists(voter.primary_email_we_vote_id) \
                        and voter.primary_email_we_vote_id.lower() == email_address_object.we_vote_id.lower():
                    # If already the primary email, leave it but make sure to heal the data
                    try:
                        voter.primary_email_we_vote_id = email_address_object.we_vote_id
                        voter.email_ownership_is_verified = True
                        voter.email = email_address_object.normalized_email_address
                        voter.save()
                        status += "SAVED_EMAIL_ADDRESS_AS_PRIMARY-HEALING_DATA "
                        success = True
                    except Exception as e:
                        status += "UNABLE_TO_SAVE_EMAIL_ADDRESS_AS_PRIMARY-HEALING_DATA "
                        remove_cached_results = \
                            voter_manager.remove_voter_cached_email_entries_from_email_address_object(
                                email_address_object)
                        status += remove_cached_results['status']
                        try:
                            voter.primary_email_we_vote_id = email_address_object.we_vote_id
                            voter.email_ownership_is_verified = True
                            voter.email = email_address_object.normalized_email_address
                            voter.save()
                            status += "SAVED_EMAIL_ADDRESS_AS_NEW_PRIMARY "
                            success = True
                        except Exception as e:
                            status += "UNABLE_TO_REMOVE_VOTER_PRIMARY_EMAIL_ADDRESS2 "
                            success = False
                else:
                    # Set this email address as the primary
                    status += "SET_THIS_EMAIL_ADDRESS_AS_PRIMARY "

                    # First, search for any other voter records that think they are using this
                    # normalized_email_address or primary_email_we_vote_id. If there are other records
                    # using these, they are bad data that don't reflect
                    remove_cached_results = \
                        voter_manager.remove_voter_cached_email_entries_from_email_address_object(
                            email_address_object)
                    status += remove_cached_results['status']

                    # And now, update current voter
                    try:
                        voter.primary_email_we_vote_id = email_address_object.we_vote_id
                        voter.email_ownership_is_verified = True
                        voter.email = email_address_object.normalized_email_address
                        voter.save()
                        status += "SAVED_EMAIL_ADDRESS_AS_PRIMARY "
                        success = True
                    except Exception as e:
                        status += "UNABLE_TO_SAVE_EMAIL_ADDRESS_AS_PRIMARY "
                        success = False
                break  # Break out of the email_address_list loop
            elif positive_value_exists(voter.primary_email_we_vote_id) \
                    and voter.primary_email_we_vote_id.lower() == email_address_object.we_vote_id.lower():
                # If here, we know that we are not looking at the email we want to make primary,
                # but we only want to wipe out a voter's primary email when we replace it with another email
                status += "LOOKING_AT_EMAIL_WITHOUT_WIPING_OUT_VOTER_PRIMARY "

    send_verification_email = False
    recipient_email_subscription_secret_key = ''
    if email_address_deleted:
        # We cannot proceed with this email address, since it was just marked deleted
        pass
    elif email_address_already_owned_by_this_voter:
        status += "EMAIL_ADDRESS_ALREADY_OWNED_BY_THIS_VOTER "
        # We send back a message that the email already owned by setting email_address_found = True
        if resend_verification_email:
            send_verification_email = True
    elif not positive_value_exists(incoming_email_we_vote_id):
        # Save the new email address
        status += "CREATE_NEW_EMAIL_ADDRESS "
        email_ownership_is_verified = False
        email_save_results = email_manager.create_email_address(
            text_for_email_address, voter_we_vote_id, email_ownership_is_verified, make_primary_email)
        status += email_save_results['status']
        if email_save_results['email_address_object_saved']:
            # Send verification email
            send_verification_email = True
            new_email_address_object = email_save_results['email_address_object']
            email_address_we_vote_id = new_email_address_object.we_vote_id
            email_address_saved_we_vote_id = new_email_address_object.we_vote_id
            if positive_value_exists(new_email_address_object.secret_key):
                recipient_email_address_secret_key = new_email_address_object.secret_key
            else:
                recipient_email_address_secret_key = \
                    email_manager.update_email_address_with_new_secret_key(email_address_we_vote_id)
            if positive_value_exists(new_email_address_object.subscription_secret_key):
                recipient_email_subscription_secret_key = new_email_address_object.subscription_secret_key
            else:
                recipient_email_subscription_secret_key = \
                    email_manager.update_email_address_with_new_subscription_secret_key(
                        email_we_vote_id=email_address_we_vote_id)
            email_address_created = True
            email_address_found = True
            success = True
            status += email_save_results['status']
        else:
            send_verification_email = False
            success = False
            status += "UNABLE_TO_SAVE_EMAIL_ADDRESS "

    secret_code_system_locked_for_this_voter_device_id = False
    voter_device_link_manager = VoterDeviceLinkManager()
    if send_link_to_sign_in and not email_address_already_owned_by_this_voter:
        # Run the code to send sign in email
        email_address_we_vote_id = email_address_we_vote_id if positive_value_exists(email_address_we_vote_id) \
            else incoming_email_we_vote_id
        link_send_results = schedule_link_to_sign_in_email(
            sender_voter_we_vote_id=voter_we_vote_id,
            recipient_voter_we_vote_id=voter_we_vote_id,
            recipient_email_we_vote_id=email_address_we_vote_id,
            recipient_voter_email=text_for_email_address,
            recipient_email_address_secret_key=recipient_email_address_secret_key,
            recipient_email_subscription_secret_key=recipient_email_subscription_secret_key,
            is_cordova=is_cordova,
            web_app_root_url=web_app_root_url)
        status += link_send_results['status']
        email_scheduled_saved = link_send_results['email_scheduled_saved']
        if email_scheduled_saved:
            link_to_sign_in_email_sent = True
            success = True
    elif send_sign_in_code_email and not sign_in_code_email_already_valid:
        # Run the code to send email with sign in verification code (6 digit)
        email_address_we_vote_id = email_address_we_vote_id if positive_value_exists(email_address_we_vote_id) \
            else incoming_email_we_vote_id
        status += "ABOUT_TO_SEND_SIGN_IN_CODE_EMAIL: " + str(email_address_we_vote_id) + " "
        # We need to link a randomly generated 6 digit code to this voter_device_id
        results = voter_device_link_manager.retrieve_voter_secret_code_up_to_date(voter_device_id)
        secret_code = results['secret_code']
        secret_code_system_locked_for_this_voter_device_id = \
            results['secret_code_system_locked_for_this_voter_device_id']

        if positive_value_exists(secret_code_system_locked_for_this_voter_device_id):
            status += "SECRET_CODE_SYSTEM_LOCKED-EMAIL_SAVE "
            success = True
        elif positive_value_exists(secret_code):
            # And we need to store the secret_key (as opposed to the 6 digit secret code) in the voter_device_link
            #  so we can match this email to this session
            link_results = voter_device_link_manager.retrieve_voter_device_link(voter_device_id)
            if link_results['voter_device_link_found']:
                voter_device_link = link_results['voter_device_link']
                update_results = voter_device_link_manager.update_voter_device_link_with_email_secret_key(
                    voter_device_link, recipient_email_address_secret_key)
                if positive_value_exists(update_results['success']):
                    status += "UPDATED_VOTER_DEVICE_LINK_WITH_SECRET_KEY "
                else:
                    status += update_results['status']
                    status += "COULD_NOT_UPDATE_VOTER_DEVICE_LINK_WITH_SECRET_KEY "
                    # Wipe out existing value and save again
                    voter_device_link_manager.clear_secret_key(email_secret_key=recipient_email_address_secret_key)
                    update_results = voter_device_link_manager.update_voter_device_link_with_email_secret_key(
                        voter_device_link, recipient_email_address_secret_key)
                    if not positive_value_exists(update_results['success']):
                        status += update_results['status']
            else:
                status += "VOTER_DEVICE_LINK_NOT_UPDATED_WITH_EMAIL_SECRET_KEY "

            email_subscription_secret_key = ''
            results = email_manager.retrieve_email_address_object(
                email_address_object_we_vote_id=email_address_we_vote_id)
            if results['email_address_object_found']:
                recipient_email_address_object = results['email_address_object']
                if positive_value_exists(recipient_email_address_object.subscription_secret_key):
                    email_subscription_secret_key = recipient_email_address_object.subscription_secret_key
                else:
                    email_subscription_secret_key = \
                        email_manager.update_email_address_with_new_subscription_secret_key(
                            email_we_vote_id=email_address_we_vote_id)

            status += 'ABOUT_TO_SEND_SIGN_IN_CODE '
            link_send_results = schedule_sign_in_code_email(
                sender_voter_we_vote_id=voter_we_vote_id,
                recipient_voter_we_vote_id=voter_we_vote_id,
                recipient_email_we_vote_id=email_address_we_vote_id,
                recipient_voter_email=text_for_email_address,
                secret_numerical_code=secret_code,
                recipient_email_subscription_secret_key=email_subscription_secret_key,
                web_app_root_url=web_app_root_url)
            status += link_send_results['status']
            email_scheduled_saved = link_send_results['email_scheduled_saved']
            if email_scheduled_saved:
                status += "EMAIL_CODE_SCHEDULED "
                sign_in_code_email_sent = True
                success = True
            else:
                status += 'SCHEDULE_SIGN_IN_CODE_EMAIL_FAILED '
                success = False
        else:
            status += results['status']
            status += 'RETRIEVE_VOTER_SECRET_CODE_UP_TO_DATE_FAILED '
            success = False
    elif send_verification_email:
        # Run the code to send verification email
        email_address_we_vote_id = email_address_we_vote_id if positive_value_exists(email_address_we_vote_id) \
            else incoming_email_we_vote_id
        verifications_send_results = schedule_verification_email(
            sender_voter_we_vote_id=voter_we_vote_id,
            recipient_voter_we_vote_id=voter_we_vote_id,
            recipient_email_we_vote_id=email_address_we_vote_id,
            recipient_voter_email=text_for_email_address,
            recipient_email_address_secret_key=recipient_email_address_secret_key,
            recipient_email_subscription_secret_key=recipient_email_subscription_secret_key,
            web_app_root_url=web_app_root_url)
        status += verifications_send_results['status']
        email_scheduled_saved = verifications_send_results['email_scheduled_saved']
        if email_scheduled_saved:
            status += "EMAIL_SCHEDULED "
            verification_email_sent = True
            success = True

    # Now that the save is complete, retrieve the updated list
    email_address_list_augmented = []
    email_results = email_manager.retrieve_voter_email_address_list(voter_we_vote_id)
    if email_results['email_address_list_found']:
        email_address_list_found = True
        email_address_list = email_results['email_address_list']
        augment_results = augment_email_address_list(email_address_list, voter)
        email_address_list_augmented = augment_results['email_address_list']
        status += augment_results['status']

    json_data = {
        'status':                           status,
        'success':                          success,
        'voter_device_id':                  voter_device_id,
        'text_for_email_address':           text_for_email_address,
        'email_address_we_vote_id':         email_address_we_vote_id,
        'email_address_already_owned_by_other_voter':   email_address_already_owned_by_other_voter,
        'email_address_already_owned_by_this_voter':    email_address_already_owned_by_this_voter,
        'email_address_found':              email_address_found,
        'email_address_list_found':         email_address_list_found,
        'email_address_list':               email_address_list_augmented,
        'email_address_saved_we_vote_id':   email_address_saved_we_vote_id,
        'email_address_created':            email_address_created,
        'email_address_deleted':            email_address_deleted,
        'email_address_not_valid':          email_address_not_valid,
        'verification_email_sent':          verification_email_sent,
        'link_to_sign_in_email_sent':       link_to_sign_in_email_sent,
        'sign_in_code_email_sent':          sign_in_code_email_sent,
        'secret_code_system_locked_for_this_voter_device_id': secret_code_system_locked_for_this_voter_device_id,
    }
    return json_data
