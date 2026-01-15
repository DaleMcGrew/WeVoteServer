# email_outbound/controllers_email_campaign.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from config.base import get_environment_variable
import json

from email_outbound.functions import convert_html_to_plain_text
from organization.controllers import transform_web_app_url
from politician.models import Politician
from voter.models import VoterManager
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists
from wevote_functions.functions_date import DATE_FORMAT_YMD
from .models import CUSTOMIZATION_TOKEN_CONVERSION_FROM_JAZZ_HR, \
    EmailCampaign, EmailCampaignRecipient, EmailManager, EmailScheduled, EmailTemplate, \
    EMAIL_TEMPLATE_CUSTOMIZATION_TOKENS, TO_BE_PROCESSED

logger = wevote_functions.admin.get_logger(__name__)

WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")


def augment_email_campaign_recipient(
        email_campaign_recipient,
        campaignx_list_dict={},
        politicians_dict={},
        sender_object={},
        voters_dict={}):
    # NOTE: We may want to bulk retrieve email addresses, voter_we_vote_ids, or politician_we_vote_ids outside
    #  of this function to reduce calls to the database
    save_changes = False
    status = ''
    success = True

    if hasattr(sender_object, 'first_name'):
        email_campaign_recipient.sender_voter_we_vote_id = sender_object.we_vote_id
        email_campaign_recipient.sender_first_name = sender_object.first_name
        email_campaign_recipient.sender_full_name = sender_object.get_full_name()
        email_campaign_recipient.sender_last_name = sender_object.last_name
        save_changes = True

    # Is this email claimed by an existing voter?
    recipient_email_address = ''
    if hasattr(email_campaign_recipient, 'email_address'):
        recipient_email_address = email_campaign_recipient.email_address

    if positive_value_exists(recipient_email_address):
        email_manager = EmailManager()
        temp_voter_we_vote_id = ""
        find_verified_email_results = email_manager.retrieve_primary_email_with_ownership_verified(
            temp_voter_we_vote_id, recipient_email_address, read_only=True)
        if find_verified_email_results['email_address_object_found']:
            verified_email_address_object = find_verified_email_results['email_address_object']
            email_campaign_recipient.recipient_email_we_vote_id = verified_email_address_object.we_vote_id
            email_campaign_recipient.recipient_voter_we_vote_id = verified_email_address_object.voter_we_vote_id
            # The only person who will see this is someone who has access to this verified_email_address
            email_campaign_recipient.recipient_email_subscription_secret_key = \
                verified_email_address_object.subscription_secret_key

    # Retrieve the recipient_voter
    if positive_value_exists(email_campaign_recipient.recipient_voter_we_vote_id):
        recipient_voter = voters_dict.get(email_campaign_recipient.recipient_voter_we_vote_id, {})
        if not hasattr(recipient_voter, 'first_name'):
            try:
                voter_manager = VoterManager()
                results = voter_manager.retrieve_voter_by_we_vote_id(email_campaign_recipient.recipient_voter_we_vote_id)
                if results['voter_found']:
                    recipient_voter = results['voter']
                    voters_dict[email_campaign_recipient.recipient_voter_we_vote_id] = recipient_voter
            except Exception as e:
                status += "VOTER_RETRIEVE_FAILED: " + str(e) + " "
        if hasattr(recipient_voter, 'first_name'):
            email_campaign_recipient.recipient_first_name = recipient_voter.first_name
            email_campaign_recipient.recipient_full_name = recipient_voter.get_full_name()
            email_campaign_recipient.recipient_last_name = recipient_voter.last_name
            save_changes = True

    # Populate politician values from database so we can use in merge_email_campaign_recipient_with_template
    if positive_value_exists(email_campaign_recipient.politician_we_vote_id):
        politician = politicians_dict.get(email_campaign_recipient.politician_we_vote_id, {})
        if not hasattr(politician, 'politician_name'):
            # Retrieve politician from database
            try:
                politician = Politician.objects.get(we_vote_id=email_campaign_recipient.politician_we_vote_id)
                politicians_dict[email_campaign_recipient.politician_we_vote_id] = politician
            except Exception as e:
                status += "POLITICIAN_RETRIEVE_FAILED: " + str(e) + " "
        if hasattr(politician, 'politician_name'):
            email_campaign_recipient.political_party = politician.political_party
            email_campaign_recipient.politician_first_name = politician.first_name
            email_campaign_recipient.politician_full_name = politician.display_full_name()
            email_campaign_recipient.politician_last_name = politician.last_name
            email_campaign_recipient.politician_seo_friendly_path = politician.seo_friendly_path
            email_campaign_recipient.politician_state_code = politician.state_code
            email_campaign_recipient.supporters_count = politician.supporters_count
            save_changes = True

        # Find the upcoming linked candidate and office that this politician is running for office next
        # We need candidate_we_vote_id office_we_vote_id in order to calculate:
        # "[office_url]",

        # Find Campaign Linked to this Politician so we can get the passkey
        try:
            from campaign.models import CampaignX
            # Cannot be read only because we may need to update passkey below
            queryset = CampaignX.objects.all()
            queryset = queryset.filter(linked_politician_we_vote_id=email_campaign_recipient.politician_we_vote_id)
            linked_campaignx_list = list(queryset)
            if len(linked_campaignx_list) > 0:
                linked_campaignx = linked_campaignx_list[0]
                if linked_campaignx and positive_value_exists(linked_campaignx.passkey_for_creating_campaign_owner):
                    email_campaign_recipient.politician_passkey = linked_campaignx.passkey_for_creating_campaign_owner
                    save_changes = True
        except Exception as e:
            status += "CAMPAIGNX_RETRIEVE_FAILED: " + str(e) + " "

    return {
        'campaignx_list_dict':      campaignx_list_dict,
        'email_campaign_recipient': email_campaign_recipient,
        'politicians_dict':         politicians_dict,
        'save_changes':             save_changes,
        'status':                   status,
        'success':                  success,
        'voters_dict':              voters_dict,
    }


def email_campaign_send(
        email_campaign={},
        email_campaign_id=''):
    status = ""
    success = True

    if not positive_value_exists(email_campaign_id):
        status += "EMAIL_CAMPAIGN_ID_REQUIRED "
        return {
            'status':   status,
            'success':  False,
        }

    if not hasattr(email_campaign, 'email_body_template_raw'):
        try:
            email_campaign = EmailCampaign.objects.get(id=email_campaign_id)
        except EmailCampaign.DoesNotExist:
            status += "SEND_EMAIL_CAMPAIGN_NOT_FOUND "
            return {
                'status':   status,
                'success':  False,
            }
        except Exception as e:
            status += f'PROBLEM_RETRIEVING_EMAIL_CAMPAIGN: {e}'
            return {
                'status':   status,
                'success':  False,
            }

    # Get the email_body_template_raw for this campaign - the EmailTemplate was the starting point,
    #  buy may have been edited
    email_body_raw = email_campaign.email_body_template_raw
    email_subject_raw = email_campaign.email_subject_template_raw

    # Get all the previously sent EmailScheduled entries for this email campaign so we can make sure to
    #  not send the same email to the same recipient more than once
    try:
        queryset = EmailScheduled.objects.filter(
            email_campaign_id=email_campaign_id)
        queryset = queryset.values_list('email_campaign_recipient_id', flat=True)
        already_scheduled_recipient_ids = list(queryset)
    except Exception as e:
        status += f'PROBLEM_RETRIEVING_EMAIL_SCHEDULED: {e}'
        return {
            'status':   status,
            'success':  False,
        }

    # Get all specific recipients for this email campaign.
    # Note that we add recipients formulaically in generate_email_campaign_recipients_from_recipient_template
    try:
        queryset = EmailCampaignRecipient.objects.filter(
            email_campaign_id=email_campaign_id)
        # Filter out recipient entries that have already been sent
        queryset = queryset.exclude(id__in=already_scheduled_recipient_ids)
        email_campaign_recipient_list = list(queryset)
    except Exception as e:
        status += f'PROBLEM_RETRIEVING_EMAIL_CAMPAIGN_RECIPIENT: {e}'
        return {
            'status':   status,
            'success':  False,
        }

    web_app_root_url_verified = transform_web_app_url('')  # Change to client URL if needed

    email_manager = EmailManager()

    # template_variables_for_json = {
    #     "subject":                          subject,
    #     "campaignx_title":                  campaignx_title,
    #     "campaignx_url":                    campaignx_url,
    #     "politician_count":                 politician_count,
    #     "politician_full_sentence_string":  politician_full_sentence_string,
    #     "recipient_name":                   recipient_name,
    #     "recipient_unsubscribe_url":        recipient_unsubscribe_url,
    #     "recipient_voter_email":            recipient_email,
    #     "speaker_voter_name":               speaker_voter_name,
    #     "view_main_discussion_page_url":    web_app_root_url_verified + "/news",
    #     "view_your_ballot_url":             web_app_root_url_verified + "/ballot",
    #     "we_vote_hosted_campaign_photo_large_url":  we_vote_hosted_campaign_photo_large_url,
    # }
    # template_variables_in_json = json.dumps(template_variables_for_json, ensure_ascii=True)
    # from_email_for_daily_summary = "We Vote <info@WeVote.US>"  # TODO DALE Make system variable

    # Loop through all recipients to collect items we want to work on in bulk
    for email_campaign_recipient in email_campaign_recipient_list:
        pass

    emails_scheduled = 0
    emails_sent = 0
    recipient_bulk_update_list = []
    recipient_email_subscription_secret_key = ''  # Temp
    for email_campaign_recipient in email_campaign_recipient_list:
        results = schedule_email_campaign_recipient(
            email_body_raw=email_body_raw,
            email_campaign_recipient=email_campaign_recipient,
            email_subject_raw=email_subject_raw,
            recipient_bulk_update_list=recipient_bulk_update_list)
        recipient_bulk_update_list = results['recipient_bulk_update_list']
        status += results['status'] + " "
        email_scheduled_saved = results['email_scheduled_saved']
        email_scheduled_id = results['email_scheduled_id']
        email_scheduled = results['email_scheduled']

        if email_scheduled_saved:
            emails_scheduled += 1
            send_results = email_manager.send_scheduled_email(email_scheduled)
            email_scheduled_sent = send_results['email_scheduled_sent']
            if email_scheduled_sent:
                emails_sent += 1
            else:
                status += "ERROR_SEND_SCHEDULED_EMAIL: " \
                    "{status} " \
                    "".format(
                        status=send_results['status'])

    # We want to bulk update the email_campaign_recipient objects in recipient_bulk_update_list
    try:
        EmailCampaignRecipient.objects.bulk_update(
            recipient_bulk_update_list, [
                'email_body_assembled',
                'email_scheduled',
                'email_subject_assembled'])
        status += \
            "email_campaign_send, EmailCampaignRecipient.objects.bulk_update: " \
            "{emails_scheduled:,} emails scheduled. " \
            "{emails_sent:,} emails_sent. " \
            "".format(
                emails_scheduled=emails_scheduled,
                emails_sent=emails_sent)
    except Exception as e:
        status += "ERROR_EMAIL_CAMPAIGN_RECIPIENT_BULK_UPDATE: {e} " \
            "".format(e=e)
        success = False

    results = {
        'success':  success,
        'status':   status,
    }
    return results


def generate_email_campaign_recipients_from_recipient_template(email_campaign_id=''):
    status = ""
    success = True

    try:
        email_campaign = EmailCampaign.objects.get(id=email_campaign_id)
    except EmailCampaign.DoesNotExist:
        status += "EMAIL_CAMPAIGN_NOT_FOUND_GENERATE_RECIPIENTS "
        return {
            'status':   status,
            'success':  False,
        }
    except Exception as e:
        status += f'GENERATE_RECIPIENTS_PROBLEM_RETRIEVING_EMAIL_CAMPAIGN: {e}'
        return {
            'status':   status,
            'success':  False,
        }

    # Get the email body & subject templates for this campaign
    # TODO: Is this necessary for generating recipients?
    try:
        email_body_template = email_campaign.email_body_template_raw
        email_subject_template = email_campaign.email_subject_template_raw
    except Exception as e:
        status += f'PROBLEM_RETRIEVING_EMAIL_TEMPLATE_RAW: {e}'
        return {
            'status':   status,
            'success':  False,
        }

    # Get all specific recipients for this email campaign, prior to adding recipients formulaically
    try:
        queryset = EmailCampaignRecipient.objects.filter(
            email_campaign_id=email_campaign_id)
        # It turns out we don't want to exclude the EmailCampaignRecipient objects that have already been scheduled yet,
        #  so we can know to not add them from the EmailRecipientTemplate searches.
        # # Filter out recipient entries that have already been sent
        # queryset = queryset.exclude(email_campaign_recipient_id__in=already_scheduled_recipient_ids)
        email_campaign_recipient_list = list(queryset)
    except Exception as e:
        status += f'Problem retrieving email campaign recipients. {e}'
        return {
            'status': status,
            'success': False,
        }

    return {
        'status': status,
        'success': success,
    }


def schedule_email_campaign_recipient(
        email_campaign_recipient=None,
        email_body_raw=None,
        email_subject_raw=None,
        recipient_bulk_update_list=[],
        template_variables_in_json=None):
    email_manager = EmailManager()
    status = ""
    template_variables_in_json = {}

    email_template_results = merge_email_campaign_recipient_with_template(
        email_body_raw=email_body_raw,
        email_campaign_recipient=email_campaign_recipient,
        email_subject_raw=email_subject_raw,
        template_variables_in_json=template_variables_in_json)
    if email_template_results['success']:
        subject = email_template_results['subject']
        message_text = email_template_results['message_text']
        message_html = email_template_results['message_html']
        schedule_email_results = email_manager.schedule_email_from_email_campaign_recipient(
            email_campaign_recipient=email_campaign_recipient,
            subject=subject,
            message_text=message_text,
            message_html=message_html,
            send_status=TO_BE_PROCESSED)
        success = schedule_email_results['success']
        status += schedule_email_results['status']
        email_scheduled_saved = schedule_email_results['email_scheduled_saved']
        email_scheduled = schedule_email_results['email_scheduled']
        email_scheduled_id = schedule_email_results['email_scheduled_id']
        if positive_value_exists(email_scheduled_saved):
            email_campaign_recipient.email_body_assembled = message_html
            email_campaign_recipient.email_scheduled = True
            email_campaign_recipient.email_subject_assembled = subject
            recipient_bulk_update_list.append(email_campaign_recipient)
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
        'recipient_bulk_update_list': recipient_bulk_update_list,
    }
    return results


def replace_token_with_space(token_key_without_square_brackets, value, token_replacements):
    token_key_with_square_brackets = f'[{token_key_without_square_brackets}]'
    if positive_value_exists(value):
        token_replacements[token_key_with_square_brackets] = value
    else:
        token_key_with_square_brackets_and_space = f' [{token_key_without_square_brackets}]'
        token_replacements[token_key_with_square_brackets_and_space] = ''  # Replace the space before also if empty
        token_replacements[token_key_with_square_brackets] = ''
    return token_replacements


def replace_token_with_unknown_if_no_value(token_key_without_square_brackets, value, token_replacements):
    token_key_with_square_brackets = f'[{token_key_without_square_brackets}]'
    if positive_value_exists(value):
        token_replacements[token_key_with_square_brackets] = value
    else:
        token_replacements[token_key_with_square_brackets] = '<ital>Unknown</ital>'
    return token_replacements


def merge_email_campaign_recipient_with_template(
        email_body_raw=None,
        email_campaign_recipient=None,
        email_subject_raw=None,
        template_variables_in_json={}):
    email_manager = EmailManager()
    success = True
    status = ''

    try:
        # Merge the email template with the recipient's specific information
        subject = email_subject_raw
    except Exception as e:
        status += "PROBLEM_GETTING_SUBJECT_FROM_TEMPLATE: " + str(e) + " "
        subject = "From We Vote"

    try:
        # Merge the email template with the recipient's specific information
        message_html = email_body_raw
    except Exception as e:
        status += "PROBLEM_GETTING_MESSAGE: " + str(e) + " "
        message_html = ""
        success = False
        # CONSIDER exiting out

    # Unsubscribe link in email
    # recipient_unsubscribe_url = \
    #     web_app_root_url_verified + "/settings/notifications/esk/" + recipient_email_subscription_secret_key
    # recipient_unsubscribe_url = \
    #     "{root_url}/unsubscribe/{email_secret_key}/friendcampaignsupport" \
    #     "".format(
    #         email_secret_key=recipient_email_subscription_secret_key,
    #         root_url=web_app_root_url_verified,
    #     )
    # Instant unsubscribe link in email header
    # list_unsubscribe_url = \
    #     "{root_url}/apis/v1/unsubscribeInstant/{email_secret_key}/friendcampaignsupport/" \
    #     "".format(
    #         email_secret_key=recipient_email_subscription_secret_key,
    #         root_url=WE_VOTE_SERVER_ROOT_URL,
    #     )
    # # Instant unsubscribe email address in email header
    # # from voter.models import NOTIFICATION_VOTER_DAILY_SUMMARY_EMAIL  # To be updated
    # list_unsubscribe_mailto = "unsubscribe@wevote.us?subject=unsubscribe%20{setting}" \
    #                           "".format(setting='friendcampaignsupport')

    # If the template was brought over from JazzHR, convert the JazzHR tokens to We Vote tokens
    for jazz_hr_token, we_vote_token in CUSTOMIZATION_TOKEN_CONVERSION_FROM_JAZZ_HR.items():
        if jazz_hr_token in message_html:
            message_html = message_html.replace(jazz_hr_token, we_vote_token)
        if jazz_hr_token in subject:
            subject = subject.replace(jazz_hr_token, we_vote_token)

    # Build a dictionary of token replacements
    token_replacements = {}

    # We want to replace all instances of these variables in the template with the recipient's specific information
    # Get values from email_campaign_recipient object, pulled from the database in augment_email_campaign_recipient
    if email_campaign_recipient:
        # These are all related to EMAIL_TEMPLATE_CUSTOMIZATION_TOKENS

        #
        open_tracking_pixel_html = ''  # WV-2447 "Open Tracking for Email Campaign System" should go here
        email_footer_html = \
            "<br />This email uses tracking to understand whether messages are opened " \
            "so we can improve our communications. Learn more: [Privacy Policy]." \
            "{open_tracking_pixel_html}<br />".format(
                open_tracking_pixel_html=open_tracking_pixel_html,
            )
        token_replacements['[email_footer]'] = email_footer_html

        # Add link to subscription key

        token_replacements['[my_first_name]'] = getattr(email_campaign_recipient, 'sender_first_name', '')
        token_replacements['[my_full_name]'] = getattr(email_campaign_recipient, 'sender_full_name', '')
        token_replacements['[my_last_name]'] = getattr(email_campaign_recipient, 'sender_last_name', '')

        # Find the upcoming linked candidate and office that this politician is running for office next
        # We need candidate_we_vote_id office_we_vote_id in order to calculate:
        # "[office_url]",
        # "[office_url_with_intro]",  # Add ?office_intro=1 to the office_page URL

        political_party = getattr(email_campaign_recipient, 'political_party', '')
        token_replacements = \
            replace_token_with_unknown_if_no_value('political_party', political_party, token_replacements)

        politician_passkey = getattr(email_campaign_recipient, 'politician_passkey', '')
        token_replacements = \
            replace_token_with_unknown_if_no_value('politician_passkey', politician_passkey, token_replacements)

        token_replacements['[seo_friendly_path]'] = \
            getattr(email_campaign_recipient, 'politician_seo_friendly_path', '')

        # Create HTML that displays we_vote_hosted_profile_image_url_large and places in [politician_photo]

        state_code = getattr(email_campaign_recipient, 'politician_state_code', '')
        token_replacements = \
            replace_token_with_unknown_if_no_value('state_code', state_code, token_replacements)

        recipient_first_name = getattr(email_campaign_recipient, 'recipient_first_name', '')
        token_replacements = replace_token_with_space('recipient_first_name', recipient_first_name, token_replacements)

        recipient_full_name = getattr(email_campaign_recipient, 'recipient_full_name', '')
        token_replacements = replace_token_with_space('recipient_full_name', recipient_full_name, token_replacements)

        recipient_last_name = getattr(email_campaign_recipient, 'recipient_last_name', '')
        token_replacements = replace_token_with_space('recipient_last_name', recipient_last_name, token_replacements)

        token_replacements['[recipient_voter_email]'] = getattr(email_campaign_recipient, 'recipient_voter_email', '')

        token_replacements['[supporters_count]'] = getattr(email_campaign_recipient, 'supporters_count', '0')

        # Sender name parts

        # Unsubscribe link

        # link_to_office
        # link_to_politician

    # Override with values from template_variables_in_json if provided
    if template_variables_in_json:
        for token in EMAIL_TEMPLATE_CUSTOMIZATION_TOKENS:
            # Remove brackets to get the key name
            key = token.strip('[]')
            if key in template_variables_in_json:
                token_replacements[token] = template_variables_in_json[key]

    # Apply all token replacements to subject and message_html
    for token, replacement_value in token_replacements.items():
        if token in subject:
            subject = subject.replace(token, str(replacement_value))
        if token in message_html:
            message_html = message_html.replace(token, str(replacement_value))

    # Convert HTML to plain text for the text version of the email
    message_text = convert_html_to_plain_text(message_html)

    results = {
        'success':      success,
        'status':       status,
        'subject':      subject,
        'message_text': message_text,
        'message_html': message_html,
    }
    return results
