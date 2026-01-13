# apis_v1/documentation_source/voter_reviewed_app_doc.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-


def voter_reviewed_app_template_values(url_root):
    """
    Show documentation about voterReviewedApp
    """
    required_query_parameter_list = [
        {
            'name':         'voter_device_id',
            'value':        'string',  # boolean, integer, long, string
            'description':  'An 88 character unique identifier linked to a voter record on the server. ',
        },
        {
            'name':         'app_review_state',
            'value':        'string',  #    ('Positive', 'Negative', None)
            'description':  'The desired state of the app review, one of {"POSITIVE", "NEGATIVE", "NONE"}',
        },
        {
            'name':         'app_review_version',
            'value':        'string',  #    Version number string
            'description':  'The version of the app being reviewed... something like "2.7.4"',
        },
        {
            'name':         'app_review_platform',
            'value':        'string',  #
            'description':  'The platform of the app being reviewed, one of {"iOS", "Android"}',
        },
        {
            'name':         'app_review_body_negative_bypass',
            'value':        'string',  #
            'description':  'When a Negative review is bypassed, this is the message body that is sent to Zendesk',
        },
    ]


    potential_status_codes_list = [
    ]

    try_now_link_variables_dict = {
        'format': 'json',
    }

    api_response = '[{\n' \
                   '  "success": string,\n' \
                   '  "status": string,\n' \
                   '  "we_vote_id": string,\n' \
                   '  "app_review_state": string,\n' \
                   '  "app_review_version": string,\n' \
                   '  "app_review_platform": string,\n' \
                   '  "email_api_status_code": string,\n' \
                   '  "email": string,\n' \
                   '  "first_name": string,\n' \
                   '  "last_name": string,\n' \
                   '}]'

    template_values = {
        'api_name': 'voterReviewedApp',
        'api_slug': 'voterReviewedApp',
        'get_or_post': 'GET',
        'url_root': url_root,
        'api_introduction':
            "This API is called from Cordova apps when they are prompted to review the app.<br><br>"
            "For negative reviews that are screened out by the <b>\"Enjoying WeVote?\"</b> screening question "
            "(appRatePromptTitle), we do not automatically send the voter an email, but do create a ZenDesk ticket "
            "with a <b>\"donotreply@wevote.us\"</b> return address so that the voter will not receive an impersonal "
            "email. <br><br>" 
            "For (hopefully) positive reviews that fall through to the App Store/Play Store process, we won't know if "
            "they loved us or hated us, but we will send them a thank you email from ZenDesk. <br><br>"
            "In either case we update the voter's record (voter_voter) with the four "
            "<span style='font-family: monospace; font-weight: 500;'>\"app_review_...\"</span> fields (one of them "
            "being an automatic <span style='font-family: monospace; font-weight: 500;'>\"app_review_date\"</span>.) "
            "<br><br>"
            "This will allow us to build automation in the future so that could start asking for reviews again after a "
            "certain number of months, or after a major UI change.<br><br>",
        'try_now_link': 'apis_v1:voterReviewedApp',
        'try_now_link_variables_dict': try_now_link_variables_dict,
        'required_query_parameter_list': required_query_parameter_list,
        'api_response': api_response,
        'api_response_notes':
            "",
    }
    return template_values
