# apis_v1/views/views_ballot.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
import json

from django.http import HttpResponse

import wevote_functions.admin
from config.base import get_environment_variable
from retrieve_tables.controllers_master import fast_load_status_retrieve, get_total_row_count, get_max_id, \
    retrieve_sql_tables_as_csv, backup_one_table_to_s3_controller
from retrieve_tables.controllers_master import fast_load_status_update
from wevote_functions.functions import get_voter_api_device_id
from wevote_tokens.models.single_use_tokens import SingleUseTokenManager, Scope
from wevote_tokens.enums import TokenUsage

logger = wevote_functions.admin.get_logger(__name__)

WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")


def backup_one_table_to_s3_view(request):  # backupOneTableToS3
    """
    pg_dump one SQL tables on the master server to AWS s3, for use with December 2025 version of fast load
    :param request:
    :return:
    """
    authorization = request.headers.get('Authorization')
    token_key = request.headers.get('X-Single-Use-Token-Key')
    new_token_key = request.headers.get('X-Single-Use-Token-New-Key')
    table_name = request.GET.get('table_name', 'bad_table_param_error')
    voter_api_device_id = get_voter_api_device_id(request)

    if authorization and token_key:
        token = authorization.split(' ')[-1]
        token_key_bytes = token_key.encode()

        token_info = SingleUseTokenManager.authenticate_retrieve_token(token, token_key_bytes, Scope.BACKUP_ONE_TABLE_TO_S3)
        if token_info['success']:
            token_info['expiration_datetime'] = token_info['expiration_datetime'].strftime('%Y-%m-%d %H:%M:%S')
        
        # TODO: return 401 status code
        # return HttpResponse(json.dumps({
        #     'success': False,
        #     'status': "Authentication failed",
        #     'token_info': token_info
        # }) ,status=401, content_type='application/json')
    
    else:
        token_info = {
            'success': False,
            'status': 'Authorization token and key are required',
        }
        # TODO: return 401 status code
        # return HttpResponse(json.dumps({
        #     'success': False,
        #     'status': 'Authorization and token key are required',
        # }), status=401, content_type='application/json')

    print("backup_one_table_to_s3 voter_api_device_id: ", voter_api_device_id)
    json_data = backup_one_table_to_s3_controller(voter_api_device_id, table_name)

    if new_token_key and token_info['success']:
        new_token_key_bytes = new_token_key.encode()
        new_token_info = SingleUseTokenManager.create_token(
            token_info['token_user'],
            new_token_key_bytes,
            Scope.BACKUP_ONE_TABLE_TO_S3,
            expiration_seconds=1200,
            json_data={'usage': TokenUsage.FAST_LOAD.value}
            )
        new_token_info['expiration_datetime'] = new_token_info['expiration_datetime'].strftime('%Y-%m-%d %H:%M:%S')
        
    # TODO: move this to only a new token case after 401 status code is implemented
    if new_token_key and token_info['success']:
        json_data['token_info'] = new_token_info
    else:
        json_data['token_info'] = token_info
    
    return HttpResponse(json.dumps(json_data), content_type='application/json')


def retrieve_sql_tables(request):  # retrieveSQLTables
    """
    Retrieve the SQL tables that would otherwise be synchronized via the "Sync Data with Master We Vote Servers" menu
    :param request:
    :return:
    """
    table_name = request.GET.get('table_name', 'bad_table_param_error')
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')
    voter_api_device_id = get_voter_api_device_id(request)

    print("retrieveSQLTables voter_api_device_id: ", voter_api_device_id)
    json_data = retrieve_sql_tables_as_csv(voter_api_device_id, table_name, start, end)

    return HttpResponse(json.dumps(json_data), content_type='application/json')


def retrieve_sql_tables_row_count(request):  # retrieveSQLTablesRowCount
    json_data = {
        'rowCount': str(get_total_row_count())
    }
    return HttpResponse(json.dumps(json_data), content_type='application/json')


def fast_load_status_retrieve_view(request):   # fastLoadStatusRetrieve
    return fast_load_status_retrieve(request)


def fast_load_status_update_view(request):   # fastLoadStatusUpdate
    return fast_load_status_update(request)


def retrieve_max_id(request):                   # retrieveMaxID
    table_name = request.GET.get('table_name', 'bad_table_param_error')
    json_data = {
        'maxID': get_max_id(table_name)
    }
    return HttpResponse(json.dumps(json_data), content_type='application/json')
