# politician/controllers_managed_politician.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.db.models import Q

from campaign.models import CampaignXManager, CampaignXOwner
from email_outbound.models import EmailAddress
from politician.models import Politician, PoliticianManager
from voter.models import Voter, VoterManager
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists

logger = wevote_functions.admin.get_logger(__name__)


def check_email_claimed(
        email_address,
        voter_date_last_changed_by_email={},
        voter_has_signed_in_with_email_dict={}):
    """
    Check if an email address has been used to sign in by a voter.
    """
    status = ''
    success = True
    check_results = {
        'date_last_changed': None,
        'is_claimed_profile': False,
        'status': status,
        'success': success,
    }

    if not positive_value_exists(email_address):
        return check_results

    email_address_lower_case = email_address.strip().lower()
    if email_address_lower_case in voter_has_signed_in_with_email_dict:
        if positive_value_exists(voter_has_signed_in_with_email_dict[email_address_lower_case]):
            check_results['is_claimed_profile'] = True
            if email_address_lower_case in voter_date_last_changed_by_email:
                check_results['date_last_changed'] = voter_date_last_changed_by_email[email_address_lower_case]
            return check_results
        else:
            return check_results
    else:
        check_results['status'] = "EMAIL_NOT_RESEARCHED "
        check_results['success'] = False
        return check_results


def has_politician_been_claimed_by_campaignx_owner(
        voter_we_vote_id_lists_by_campaignx_we_vote_id={},
        politician={},
        voter_dict={},
):
    date_last_changed = None
    is_claimed_profile = False
    status = ''
    success = True

    results = {
        'date_last_changed': None,
        'is_claimed_profile': is_claimed_profile,
        'status': status,
        'success': success,
    }

    if not isinstance(politician, Politician):
        results['status'] = "POLITICIAN_OBJECT_NOT_FOUND  "
        results['success'] = False
        return results

    # Start with the politician.linked_campaignx_we_vote_id and use that to find list of voters who are CampaignX owners
    if isinstance(politician, Politician) and \
            positive_value_exists(politician.linked_campaignx_we_vote_id):
        voter_we_vote_id_list = voter_we_vote_id_lists_by_campaignx_we_vote_id.get(
            politician.linked_campaignx_we_vote_id)
        for voter_we_vote_id in voter_we_vote_id_list:
            if voter_we_vote_id in voter_dict:
                voter = voter_dict[voter_we_vote_id]
                if voter.is_signed_in():
                    date_last_changed = voter.date_last_changed
                    is_claimed_profile = True
                    status += "VOTER_OWNER_IS_SIGNED_IN "
                    break

    results = {
        'date_last_changed':    date_last_changed,
        'is_claimed_profile':   is_claimed_profile,
        'status':               status,
        'success':              success,
    }
    return results


def has_politician_been_claimed_by_voter_email(
        politician,
        voter_date_last_changed_by_email={},
        voter_has_signed_in_with_email_dict={},
):
    date_last_changed = None
    is_claimed_profile = False
    status = ''
    success = True

    results = {
        'date_last_changed': date_last_changed,
        'is_claimed_profile': is_claimed_profile,
        'status': status,
        'success': success,
    }

    if not isinstance(politician, Politician):
        results['status'] = "POLITICIAN_OBJECT_NOT_FOUND  "
        results['success'] = False
        return results

    if positive_value_exists(politician.politician_email):
        claimed_results = check_email_claimed(
            politician.politician_email,
            voter_date_last_changed_by_email,
            voter_has_signed_in_with_email_dict)
        if claimed_results['is_claimed_profile']:
            results['date_last_changed'] = claimed_results['date_last_changed']
            results['is_claimed_profile'] = True
            return results

    if positive_value_exists(politician.politician_email2):
        claimed_results = check_email_claimed(
            politician.politician_email2,
            voter_date_last_changed_by_email,
            voter_has_signed_in_with_email_dict)
        if claimed_results['is_claimed_profile']:
            results['date_last_changed'] = claimed_results['date_last_changed']
            results['is_claimed_profile'] = True
            return results

    if positive_value_exists(politician.politician_email3):
        claimed_results = check_email_claimed(
            politician.politician_email3,
            voter_date_last_changed_by_email,
            voter_has_signed_in_with_email_dict)
        if claimed_results['is_claimed_profile']:
            results['date_last_changed'] = claimed_results['date_last_changed']
            results['is_claimed_profile'] = True
            return results

    results = {
        'date_last_changed':    date_last_changed,
        'is_claimed_profile':   is_claimed_profile,
        'status':               status,
        'success':              success,
    }
    return results


def politician_managed_retrieve_for_api(  # politicianManagedRetrieve
        request=None,
        voter_device_id='',
):
    status = ''
    success = True

    results = {}
    results.update({
        # 'candidate_list':                   politician_candidate_dict_list,
        'status':                           status,
        'success':                          success,
    })
    return results


def politician_managed_save_for_api(  # politicianManagedSave
        request=None,
        voter_device_id='',
):
    status = ''
    success = True

    return politician_managed_retrieve_for_api(request, voter_device_id)


def politicians_managed_retrieve_for_api(  # politiciansManagedRetrieve
        request=None,
        voter_device_id='',
):
    politician_we_vote_id_list = []
    politicians_managed_list = []
    status = ''
    success = True
    voter_is_signed_in = False
    voter_we_vote_id = ''

    error_results = {
        'politicians_managed_list': politicians_managed_list,
        'status': status,
        'success': success,
    }

    voter_manager = VoterManager()
    voter_results = voter_manager.retrieve_voter_from_voter_device_id(voter_device_id, read_only=True)
    if voter_results['voter_found']:
        voter = voter_results['voter']
        voter_is_signed_in = voter.is_signed_in()
        voter_we_vote_id = voter.we_vote_id

    if not voter_is_signed_in:
        error_results['status'] += "NOT_SIGNED_IN "
        error_results['success'] = True
        return error_results

    # Find all verified emails associated with the voter

    # Search to find all politicians this voter can manage
    campaignx_manager = CampaignXManager()
    voter_owned_campaignx_we_vote_ids = campaignx_manager.retrieve_voter_owned_campaignx_we_vote_ids(
        voter_we_vote_id=voter_we_vote_id)

    if len(voter_owned_campaignx_we_vote_ids) > 0:
        politician_manager = PoliticianManager()
        results = politician_manager.retrieve_politician_list(
            campaignx_we_vote_id_list=voter_owned_campaignx_we_vote_ids)
        if not results['success']:
            status += "FAILED_RETRIEVING_POLITICIANS_FOR_VOTER_OWNED_CAMPAIGNS: "
            status += results['status'] + ' '
            success = False
        politician_list = results['politician_list']

        for politician in politician_list:
            politicians_managed_list.append(
                {
                    'politician_we_vote_id': politician.we_vote_id,
                    'politician_name': politician.politician_name,
                    'we_vote_hosted_profile_image_url_large': politician.we_vote_hosted_profile_image_url_large,
                    'we_vote_hosted_profile_image_url_medium': politician.we_vote_hosted_profile_image_url_medium,
                    'we_vote_hosted_profile_image_url_tiny': politician.we_vote_hosted_profile_image_url_tiny,
                }
            )

    results = {}
    results.update({
        'politicians_managed_list':         politicians_managed_list,
        'status':                           status,
        'success':                          success,
    })
    return results


def retrieve_db_objects_for_claimed_profile_analysis(
        politician_list,
):
    campaignx_we_vote_id_dict_by_voter_we_vote_id = {}
    campaignx_we_vote_id_list = []
    politician_emails_to_research_list = []
    politician_dict_by_campaignx_we_vote_id = {}
    politician_we_vote_id_dict_by_campaignx_we_vote_id = {}
    politician_we_vote_id_list = []
    status = ''
    success = True
    voter_date_last_changed_by_email = {}  # key: email, value: date_last_changed
    voter_dict = {}
    voter_we_vote_id_list_from_campaignx_owners = []

    # Collect emails, campaignx_we_vote_id and politician_we_vote_id for all politicians
    for politician in politician_list:
        politician_we_vote_id_list.append(politician.we_vote_id)
        if positive_value_exists(politician.linked_campaignx_we_vote_id):
            if politician.linked_campaignx_we_vote_id not in campaignx_we_vote_id_list:
                campaignx_we_vote_id_list.append(politician.linked_campaignx_we_vote_id)
                politician_dict_by_campaignx_we_vote_id[politician.linked_campaignx_we_vote_id] = politician
                politician_we_vote_id_dict_by_campaignx_we_vote_id[politician.linked_campaignx_we_vote_id] = \
                    politician.we_vote_id
        if positive_value_exists(politician.politician_email):
            politician_emails_to_research_list.append(politician.politician_email.strip().lower())
        if positive_value_exists(politician.politician_email2):
            politician_emails_to_research_list.append(politician.politician_email2.strip().lower())
        if positive_value_exists(politician.politician_email3):
            politician_emails_to_research_list.append(politician.politician_email3.strip().lower())

    # We need to figure out who has the right to edit this politician's profile
    campaignx_owner_list = []
    if len(campaignx_we_vote_id_list) > 0:  # We do bulk retrieve here so we don't have to do it for each politician
        try:
            queryset = CampaignXOwner.objects.all()
            queryset = queryset.filter(campaignx_we_vote_id__in=campaignx_we_vote_id_list)
            queryset = queryset.exclude(
                Q(voter_we_vote_id__isnull=True) |
                Q(voter_we_vote_id="")
            )
            campaignx_owner_list = list(queryset)
        except Exception as e:
            status += "ERROR_RETRIEVING_CAMPAIGNX_OWNERS: {e} ".format(e=e)
            success = False

    # Cycle through campaignX owners
    voter_we_vote_id_lists_by_campaignx_we_vote_id = {}
    for campaignx_owner in campaignx_owner_list:
        if positive_value_exists(campaignx_owner.campaignx_we_vote_id):
            campaignx_we_vote_id_dict_by_voter_we_vote_id[
                campaignx_owner.voter_we_vote_id] = campaignx_owner.campaignx_we_vote_id
            if campaignx_owner.campaignx_we_vote_id not in voter_we_vote_id_lists_by_campaignx_we_vote_id:
                voter_we_vote_id_lists_by_campaignx_we_vote_id[campaignx_owner.campaignx_we_vote_id] = []
            if campaignx_owner.voter_we_vote_id not in voter_we_vote_id_lists_by_campaignx_we_vote_id:
                voter_we_vote_id_lists_by_campaignx_we_vote_id[campaignx_owner.campaignx_we_vote_id].append(
                    campaignx_owner.voter_we_vote_id)
        if campaignx_owner.voter_we_vote_id not in voter_we_vote_id_list_from_campaignx_owners:
            voter_we_vote_id_list_from_campaignx_owners.append(campaignx_owner.voter_we_vote_id)
        # Dictionary: key: voter_we_vote_id, value: Voter object (so we can see if they have signed in)

    # Has the CampaignXOwner voter signed in?
    if len(voter_we_vote_id_list_from_campaignx_owners) > 0:  # Do bulk retrieve here so we don't have to for each voter
        try:
            queryset = Voter.objects.filter(
                Q(email_ownership_is_verified=True) | Q(sms_ownership_is_verified=True)
            )
            queryset = queryset.filter(we_vote_id__in=voter_we_vote_id_list_from_campaignx_owners)
            voter_list_from_campaignx_owners = list(queryset)
            # Add to the voter_dict: we_vote_id as the key and the Voter object as the value
            for voter in voter_list_from_campaignx_owners:
                voter_dict[voter.we_vote_id] = voter
        except Exception as e:
            status += "ERROR_RETRIEVING_VOTERS: {e} ".format(e=e)
            success = False

    # We need to know if any of the email addresses in politician_emails_to_research_list are verified email addresses
    #  for an existing signed in voter
    email_address_found_list = []
    if len(politician_emails_to_research_list) > 0:  # Do bulk retrieve here so we don't have to for each politician
        try:
            queryset = EmailAddress.objects.filter(email_ownership_is_verified=True)
            queryset = queryset.filter(normalized_email_address__in=politician_emails_to_research_list)
            queryset = queryset.values_list('normalized_email_address', flat=True).distinct()
            email_address_found_list = list(queryset)
        except Exception as e:
            status += "ERROR_RETRIEVING_EMAIL_ADDRESS: {e} ".format(e=e)
            success = False

    email_address_found_from_voter_list = []
    if len(politician_emails_to_research_list) > 0:  # We do bulk retrieve, so we don't have to for each politician
        try:
            queryset = Voter.objects.filter(
                Q(email_ownership_is_verified=True) | Q(sms_ownership_is_verified=True)
            )
            queryset = queryset.filter(email__in=politician_emails_to_research_list)
            voter_possibilities_list = list(queryset)
            # Add to the voter_dict: we_vote_id as the key and the Voter object as the value
            for voter in voter_possibilities_list:
                voter_dict[voter.we_vote_id] = voter
            email_queryset_flat = queryset.values_list('email', flat=True).distinct()
            email_address_found_from_voter_list = list(email_queryset_flat)
        except Exception as e:
            status += "ERROR_RETRIEVING_EMAIL_ADDRESS: {e} ".format(e=e)
            success = False

    # Combine unique values from email_address_found_list with email_address_found_from_voter_list
    email_address_found_list = list(set(email_address_found_list + email_address_found_from_voter_list))

    voter_has_signed_in_with_email_dict = {}  # key: email, value: True if voter has signed in, False otherwise
    for normalized_email_address in politician_emails_to_research_list:
        if normalized_email_address in email_address_found_list:
            voter_has_signed_in_with_email_dict[normalized_email_address] = True
        else:
            voter_has_signed_in_with_email_dict[normalized_email_address] = False

    # Starting with voter_dict, create a simple list of voter objects
    voter_dict_list = list(voter_dict.values())
    # Then, iterate over voter_dict_list and add voter.email to the voter_date_last_changed_by_email dictionary
    # with voter.date_last_changed as the value. Convert email to lower case for easier comparison.
    for voter in voter_dict_list:
        email_lower_case = voter.email.lower() if voter.email else ''
        if positive_value_exists(email_lower_case):
            voter_date_last_changed_by_email[email_lower_case] = voter.date_last_changed

    return {
        'status': status,
        'success': success,
        'voter_date_last_changed_by_email': voter_date_last_changed_by_email,
        'voter_dict': voter_dict,
        'voter_has_signed_in_with_email_dict':  voter_has_signed_in_with_email_dict,
        'voter_we_vote_id_lists_by_campaignx_we_vote_id': voter_we_vote_id_lists_by_campaignx_we_vote_id,
    }
