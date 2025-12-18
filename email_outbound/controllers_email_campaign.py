# email_outbound/controllers_email_campaign.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from config.base import get_environment_variable
import json

from voter.models import VoterManager
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists
from wevote_functions.functions_date import DATE_FORMAT_YMD

logger = wevote_functions.admin.get_logger(__name__)

WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")


def email_campaign_send(email_campaign_id=''):
    from email_outbound.controllers import schedule_email_with_email_outbound_description
    from email_outbound.models import EmailManager, CAMPAIGNX_FRIEND_HAS_SUPPORTED_TEMPLATE
    status = ""

    voter_manager = VoterManager()
    from organization.controllers import transform_web_app_url  # transform_campaigns_url
    # campaigns_root_url_verified = transform_campaigns_url('')  # Change to client URL if needed
    web_app_root_url_verified = transform_web_app_url('')  # Change to client URL if needed

    # Get the voter who is triggering the sending of the email campaign
    # sender_voter_results = voter_manager.retrieve_voter_by_we_vote_id(sender_voter_we_vote_id)
    # if not sender_voter_results['voter_found']:
    #     error_results = {
    #         'status':                               "RECIPIENT_VOTER_NOT_FOUND ",
    #         'success':                              False,
    #     }
    #     return error_results
    #
    # sender_voter = sender_voter_results['voter']

    email_manager = EmailManager()
    # Keep track of the voter_we_vote_id who triggered the sending of the email campaign
    sender_voter_we_vote_id = ''

    # if not positive_value_exists(sender_voter_we_vote_id):
    #     status += "RECIPIENT_VOTER_DOES_NOT_HAVE_VOTER_WE_VOTE_ID "
    #     success = True
    #     results = {
    #         'success': success,
    #         'status': status,
    #     }
    #     return results

    real_name_only = True
    recipient_name = sender_voter.get_full_name(real_name_only)

    speaker_voter_name = ''
    if positive_value_exists(speaker_voter_we_vote_id):
        speaker_voter_results = voter_manager.retrieve_voter_by_we_vote_id(speaker_voter_we_vote_id)
        if speaker_voter_results['voter_found']:
            speaker_voter = speaker_voter_results['voter']
            speaker_voter_name = speaker_voter.get_full_name(real_name_only)
            # speaker_voter_photo = speaker_voter.voter_photo_url()

    from campaign.controllers import fetch_sentence_string_from_politician_list
    from campaign.models import CampaignXManager
    campaignx_manager = CampaignXManager()
    results = campaignx_manager.retrieve_campaignx(campaignx_we_vote_id=campaignx_we_vote_id)
    campaignx_title = ''
    campaignx_url = web_app_root_url_verified + '/id/' + campaignx_we_vote_id  # Default link
    linked_politician_we_vote_id = ''
    we_vote_hosted_campaign_photo_large_url = ''
    if results['campaignx_found']:
        campaignx = results['campaignx']
        campaignx_title = campaignx.campaign_title
        linked_politician_we_vote_id = campaignx.linked_politician_we_vote_id
        if positive_value_exists(linked_politician_we_vote_id):
            if positive_value_exists(campaignx.seo_friendly_path):
                campaignx_url = web_app_root_url_verified + '/' + campaignx.seo_friendly_path + '/-'
            else:
                campaignx_url = web_app_root_url_verified + '/p/' + campaignx.linked_politician_we_vote_id
        elif positive_value_exists(campaignx.seo_friendly_path):
            campaignx_url = web_app_root_url_verified + '/c/' + campaignx.seo_friendly_path
        we_vote_hosted_campaign_photo_large_url = campaignx.we_vote_hosted_campaign_photo_large_url

    politician_list = campaignx_manager.retrieve_campaignx_politician_list(campaignx_we_vote_id=campaignx_we_vote_id)
    politician_count = len(politician_list)
    your_friends_name = speaker_voter_name if positive_value_exists(speaker_voter_name) else 'Your friend'
    if politician_count > 0:
        subject = your_friends_name + " supports" + fetch_sentence_string_from_politician_list(
            politician_list=politician_list,
            max_number_of_list_items=4,
        )
        politician_full_sentence_string = fetch_sentence_string_from_politician_list(
            politician_list=politician_list,
        )
    else:
        subject = your_friends_name + " supports " + campaignx_title
        politician_full_sentence_string = ''

    # Unsubscribe link in email
    recipient_unsubscribe_url = \
        web_app_root_url_verified + "/settings/notifications/esk/" + recipient_email_subscription_secret_key
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

    template_variables_for_json = {
        "subject":                          subject,
        "campaignx_title":                  campaignx_title,
        "campaignx_url":                    campaignx_url,
        "politician_count":                 politician_count,
        "politician_full_sentence_string":  politician_full_sentence_string,
        "recipient_name":                   recipient_name,
        "recipient_unsubscribe_url":        recipient_unsubscribe_url,
        "recipient_voter_email":            recipient_email,
        "speaker_voter_name":               speaker_voter_name,
        "view_main_discussion_page_url":    web_app_root_url_verified + "/news",
        "view_your_ballot_url":             web_app_root_url_verified + "/ballot",
        "we_vote_hosted_campaign_photo_large_url":  we_vote_hosted_campaign_photo_large_url,
    }
    template_variables_in_json = json.dumps(template_variables_for_json, ensure_ascii=True)
    from_email_for_daily_summary = "We Vote <info@WeVote.US>"  # TODO DALE Make system variable

    # Create the outbound email description, then schedule it
    kind_of_email_template = CAMPAIGNX_FRIEND_HAS_SUPPORTED_TEMPLATE
    outbound_results = email_manager.create_email_outbound_description(
        sender_voter_we_vote_id=speaker_voter_we_vote_id,
        sender_voter_email=from_email_for_daily_summary,
        sender_voter_name=speaker_voter_name,
        recipient_voter_we_vote_id=recipient_voter_we_vote_id,
        recipient_email_we_vote_id=recipient_email_we_vote_id,
        recipient_voter_email=recipient_email,
        template_variables_in_json=template_variables_in_json,
        kind_of_email_template=kind_of_email_template,
        # list_unsubscribe_mailto=list_unsubscribe_mailto,
        # list_unsubscribe_url=list_unsubscribe_url,
    )
    status += outbound_results['status'] + " "
    success = outbound_results['success']
    if outbound_results['email_outbound_description_saved']:
        email_outbound_description = outbound_results['email_outbound_description']
        schedule_results = schedule_email_with_email_outbound_description(email_outbound_description)
        status += schedule_results['status'] + " "
        success = schedule_results['success']
        if schedule_results['email_scheduled_saved']:
            # messages_to_send.append(schedule_results['email_scheduled_id'])
            email_scheduled = schedule_results['email_scheduled']
            send_results = email_manager.send_scheduled_email(email_scheduled)
            email_scheduled_sent = send_results['email_scheduled_sent']
            status += send_results['status']
            success = send_results['success']

    results = {
        'success':                              success,
        'status':                               status,
    }
    return results

