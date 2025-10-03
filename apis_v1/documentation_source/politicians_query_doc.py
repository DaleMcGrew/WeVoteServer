# apis_v1/documentation_source/politicians_query.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
from wevote_functions.functions_date import DATE_FORMAT_YMD_HMS


def politicians_query_doc_template_values(url_root):
    """
    Show documentation about politiciansQuery
    """
    required_query_parameter_list = [
    ]
    optional_query_parameter_list = [
        {
            'name': 'race_office_level',
            'value': 'list of strings',  # boolean, integer, long, string
            'description': 'Limit the politicians returned to: Federal, State, Local',
        },
        {
            'name': 'search_text',
            'value': 'string',  # boolean, integer, long, string
            'description': 'The word or words we want to search for in all politicians.',
        },
        {
            'name': 'state',
            'value': 'string',  # boolean, integer, long, string
            'description': 'Limit the politicians returned to this state.',
        },
    ]

    potential_status_codes_list = [
        {
            'code':         'POLITICIANS_RETRIEVED',
            'description':  'Candidates were returned.',
        },
        {
            'code':         'NO_POLITICIANS_RETRIEVED',
            'description':  'There are no politicians stored for this Office.',
        },
    ]

    try_now_link_variables_dict = {
        'year': '2023',
    }

    api_response = '{\n' \
                   '  "status": string,\n' \
                   '  "success": boolean,\n' \
                   '  "index_start": integer,\n' \
                   '  "returned_count": integer,\n' \
                   '  "total_count": integer,\n' \
                   '  "kind": string,\n' \
                   '  "state": string,\n' \
                   '  "politicians": list\n' \
                   '   [\n' \
                   '     "id": integer,\n' \
                   '     "status": string,\n' \
                   '     "success": boolean,\n' \
                   '     "ballot_item_display_name": string,\n' \
                   '     "kind_of_ballot_item": string,\n' \
                   '     "last_updated": string (time in this format ' + DATE_FORMAT_YMD_HMS + '),\n' \
                   '     "office_held_we_vote_id": string,\n' \
                   '     "party": string,\n' \
                   '     "politician_we_vote_id": string,\n' \
                   '     "politician_photo_url_large": string,\n' \
                   '     "politician_photo_url_medium": string,\n'\
                   '     "politician_photo_url_tiny": string,\n' \
                   '     "we_vote_id": string,\n' \
                   '   ],\n' \
                   '}'

    template_values = {
        'api_name': 'politiciansQuery',
        'api_slug': 'politiciansQuery',
        'api_introduction':
            "Retrieve all the politicians in a particular state.",
        'try_now_link': 'apis_v1:politiciansQueryView',
        'try_now_link_variables_dict': try_now_link_variables_dict,
        'url_root': url_root,
        'get_or_post': 'GET',
        'required_query_parameter_list': required_query_parameter_list,
        'optional_query_parameter_list': optional_query_parameter_list,
        'api_response': api_response,
        'api_response_notes':
            "",
        'potential_status_codes_list': potential_status_codes_list,
    }
    return template_values
