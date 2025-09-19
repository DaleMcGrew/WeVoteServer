# apis_v1/documentation_source/politician_save_doc.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-


def politician_save_doc_template_values(url_root):
    """
    Show documentation about politicianSave
    """
    required_query_parameter_list = [
        {
            'name':         'voter_device_id',
            'value':        'string',  # boolean, integer, long, string
            'description':  'An 88 character unique identifier linked to a voter record on the server',
        },
        {
            'name':         'api_key',
            'value':        'string (from post, cookie, or get (in that order))',  # boolean, integer, long, string
            'description':  'The unique key provided to any organization using the WeVoteServer APIs',
        },
    ]
    optional_query_parameter_list = [
        {
            'name':         'politician_we_vote_id',
            'value':        'string',  # boolean, integer, long, string
            'description':  'The we_vote_id for the politician.',
        },
        {
            'name':         'politician_name',
            'value':        'string',  # boolean, integer, long, string
            'description':  'The name of the politician.',
        },
        {
            'name':         'politician_name_changed',
            'value':        'boolean',  # boolean, integer, long, string
            'description':  'Are we trying to change the politician\'s name?',
        },
    ]

    potential_status_codes_list = [
        {
            'code':         'VALID_VOTER_DEVICE_ID_MISSING',
            'description':  'Cannot proceed. A valid voter_device_id parameter was not included.',
        },
        {
            'code':         'VALID_VOTER_ID_MISSING',
            'description':  'Cannot proceed. A valid voter_id was not found.',
        },
    ]

    try_now_link_variables_dict = {
        # 'politician_we_vote_id': 'wv85pol1',
    }

    api_response = '{\n' \
                   '  "status": string,\n' \
                   '  "success": boolean,\n' \
                   '  "politician_name": string,\n' \
                   '  "politician_we_vote_id": string,\n' \
                   ' (SAME RESPONSES as politicianRetrieve)' \
                   '}'

    template_values = {
        'api_name': 'politicianSave',
        'api_slug': 'politicianSave',
        'api_introduction':
            "",
        'try_now_link': 'apis_v1:politicianSaveView',
        'try_now_link_variables_dict': try_now_link_variables_dict,
        'url_root': url_root,
        'get_or_post': 'POST',
        'required_query_parameter_list': required_query_parameter_list,
        'optional_query_parameter_list': optional_query_parameter_list,
        'api_response': api_response,
        'api_response_notes':
            "",
        'potential_status_codes_list': potential_status_codes_list,
    }
    return template_values
