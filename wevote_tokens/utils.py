import json
import logging

from django.http import HttpResponse, StreamingHttpResponse

from config.environment_variable_functions import get_environment_variable_default
from wevote_functions.functions import positive_value_exists
from wevote_tokens.enums import TokenTypes, TokenHeaders, TokenResponse
from wevote_tokens.models.single_use_tokens import SingleUseTokenManager


class TokensManager():

    def __init__(self, token_types, scope, expiration_seconds=None, json_data=None):
        if not isinstance(token_types, list):
            token_types = [str(token_types)]
        
        self.scope = scope
        self.token_types = token_types
        self.expiration_seconds = expiration_seconds
        self.json_data = json_data

    # have a function that serves as a wrapper for a view
    def __call__(self, view_func):
        def _wrapped_view(request, *args, **kwargs):
            token_response = TokenResponse.TOKEN_RESPONSE.get_value()
            process_success = False
            try:
                # First, get headers
                request_token_info = self.get_request_token_info(request)

                if request_token_info['error_message']:
                    token_response['token_authentication'] = {
                        'success': False,
                        'status': "",
                        'error_message': request_token_info['error_message'],
                        'token_info': None
                    }

                    TokensManager.test_log_to_cloudwatch('get_request_token_info',
                                                         request_token_info, process_success, token_response)

                # Check token type
                if not request_token_info['error_message'] and \
                        (not request_token_info['token_type'] or
                         request_token_info['token_type'] not in self.token_types):
                    # TODO: return 401 unauthorized
                    token_response['token_authentication'] = {
                        'success': False,
                        'status': 'INVALID_TOKEN_TYPE',
                        'error_message': "Invalid token type",
                        'token_info': None
                    }

                    TokensManager.test_log_to_cloudwatch('verify_token_type',
                                                         request_token_info, process_success, token_response)
                
                if not token_response['token_authentication']:
                    # And authenticate it with id, key, and scope
                    token_response['token_authentication'] = self.token_authentication(request_token_info)

                    process_success = token_response['token_authentication']['success']
                    
                    # if exists and is True, then create a new token
                    if request_token_info['create_token'] and token_response['token_authentication']['success']:
                        token_response['token_creation'] = self.token_creation(request_token_info)

                        process_success = token_response['token_creation']['success']

                TokensManager.test_log_to_cloudwatch('token_authenticated_and_created', request_token_info, process_success, token_response)
                
            except Exception as e:
                token_response['exception_error_message'] = str(e)
                TokensManager.test_log_to_cloudwatch('error_on_token_authentication_and_creation', request_token_info, False, token_response)
                
            response = view_func(request, *args, **kwargs)
            
            try:
                self.add_response_token_info_headers(response, token_response)
            except Exception as e:
                token_response['exception_error_message'] = e.message
                TokensManager.test_log_to_cloudwatch('error_on_adding_response_token_info_headers', request_token_info, False, token_response)

            return response
        return _wrapped_view

    # something that takes in a request, and gets needed information from headers or cookies
    @staticmethod
    def get_request_token_info(request):
        user_id = request.headers.get(TokenHeaders.USER_ID.value)
        token_type = request.headers.get(TokenHeaders.TOKEN_TYPE.value)
        authorization = request.headers.get(TokenHeaders.AUTHORIZATION.value)
        create_token = request.headers.get(TokenHeaders.CREATE_TOKEN.value)
        token_key = request.headers.get(TokenHeaders.TOKEN_KEY.value)
        new_token_key = request.headers.get(TokenHeaders.TOKEN_NEW_KEY.value)

        try:
            user_id = TokensManager.get_user_id(user_id)
            token_type = TokensManager.get_token_type(token_type)
            create_token = TokensManager.get_create_token(create_token)
            authorization = TokensManager.get_bearer_token(authorization)
            token_key = TokensManager.encode_token_key(token_key)
            new_token_key = TokensManager.encode_token_key(new_token_key)
        except Exception as e:
            return {
                'user_id': None,
                'token_type': None,
                'authorization': None,
                'create_token': None,
                'token_key': None,
                'new_token_key': None,
                'error_message': f"Error getting request token info: {e}"
            }

        return {
            'user_id': user_id,
            'token_type': token_type,
            'authorization': authorization,
            'create_token': create_token,
            'token_key': token_key,
            'new_token_key': new_token_key,
            'error_message': None
        }

    @staticmethod
    def format_request_headers(user_id=None, token_type=None, authorization=None, create_token=None, token_key=None, new_token_key=None):
        if user_id:
            user_id = str(user_id)
        if token_type:
            token_type = str(token_type)
        if authorization:
            authorization = f"Bearer {authorization}"
        if create_token:
            create_token = str(create_token)
        if token_key:
            token_key = str(token_key)
        if new_token_key:
            new_token_key = str(new_token_key)

        headers = {
            TokenHeaders.USER_ID.value: user_id,
            TokenHeaders.TOKEN_TYPE.value: token_type,
            TokenHeaders.AUTHORIZATION.value: authorization,
            TokenHeaders.CREATE_TOKEN.value: create_token,
            TokenHeaders.TOKEN_KEY.value: token_key,
            TokenHeaders.TOKEN_NEW_KEY.value: new_token_key,
        }

        headers = {key: value for key, value in headers.items() if value is not None}

        return headers

    def token_creation(self, request_token_info):
        token_creation_info = TokenResponse.TOKEN_CREATION.get_value()

        scope = self.scope
        expiration_seconds = self.expiration_seconds
        json_data = self.json_data

        user_id = request_token_info['user_id']
        token_type = request_token_info['token_type']
        encryption_key = request_token_info['new_token_key']

        token_info = None
        if token_type == TokenTypes.SINGLE_USE.value:
            token_info = SingleUseTokenManager.create_token(user_id, encryption_key, scope, expiration_seconds, json_data)
            if token_info['success']:
                token_info['expiration_datetime'] = \
                    token_info['expiration_datetime'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            token_creation_info['error_message'] = f"Invalid token type: {token_type}"

        if token_info is not None:
            if token_info['success']:
                token_creation_info['success'] = True
                token_creation_info['status'] = token_info['status']
                token_creation_info['error_message'] = None
                token_creation_info['token_info'] = token_info
            elif positive_value_exists(token_info['status']):
                token_creation_info['error_message'] = token_info['status']
            else:
                token_creation_info['error_message'] = "Unknown error"

        TokensManager.test_log_to_cloudwatch('token_creation', request_token_info, token_creation_info['success'], token_creation_info)

        return token_creation_info

    # Have a function that takes in the request to validate the token info
    def token_authentication(self, request_token_info):
        token_auth_info = TokenResponse.TOKEN_AUTHENTICATION.get_value()

        scope = self.scope

        user_id = request_token_info['user_id']
        token_type = request_token_info['token_type']
        token_id = request_token_info['authorization']
        token_key = request_token_info['token_key']
        new_token_key = request_token_info['new_token_key']

        if not token_id or not token_key:
            token_auth_info['error_message'] = "Authorization and token key are required"
            return token_auth_info
        
        token_info = None
        if token_type == TokenTypes.SINGLE_USE.value:
            # breakpoint()
            token_info = SingleUseTokenManager.authenticate_retrieve_token(token_id, token_key, scope)
            if token_info['success']:
                token_info['expiration_datetime'] = \
                    token_info['expiration_datetime'].strftime('%Y-%m-%d %H:%M:%S')

            # This is for retries in case of faulty api connection
            # if the previous token key was used, its likely that
            # a new token was created with the new key
            if not token_info['success'] and 'TOKEN NOT FOUND' in token_info['status']:
                user_tokens = SingleUseTokenManager.get_tokens_by_user_id(request_token_info['user_id'], scope)
                if isinstance(user_tokens, str):
                    token_auth_info['error_message'] = user_tokens
                else:
                    for user_token in user_tokens:
                        user_token_pk = user_token['pk']
                        temp_token_check_info = SingleUseTokenManager.authenticate_retrieve_token(user_token_pk, new_token_key, scope)
                        if temp_token_check_info['success']:
                            token_info = temp_token_check_info
                            break

        else:
            token_auth_info['error_message'] = f"Invalid token type: {token_type}"

        TokensManager.test_log_to_cloudwatch('token_authentication', request_token_info, token_auth_info['success'], token_auth_info)

        if token_info is not None:
            if token_info['success']:
                token_auth_info['success'] = True
                token_auth_info['status'] = token_info['status']
                token_auth_info['error_message'] = None
                token_auth_info['token_info'] = token_info
            elif positive_value_exists(token_info['status']):
                token_auth_info['error_message'] = token_info['status']
            else:
                token_auth_info['error_message'] = "Unknown error"
        
        return token_auth_info

    # something that takes a response, and adds needed token information to headers
    @staticmethod
    def add_response_token_info_headers(response, token_response, reject_keys=None):
        if isinstance(response, HttpResponse) and not isinstance(response, StreamingHttpResponse):
            headers_mapping = TokenResponse.HEADERS_MAPPING.get_value()

            for key, value in token_response.items():
                if key in headers_mapping.keys() and value is not None:
                    response[headers_mapping[key]] = json.dumps(value)

        return response

    # # something that takes a response, and adds needed token information to cookies
    # def add_response_token_info_cookies(self, response, token_info):
    #     pass

    #########################################################
    # Error Handling
    #########################################################
    @staticmethod
    def handle_error(error):
        if isinstance(error, Exception):
            return error.message
        return str(error)

    #########################################################
    # Helper Functions
    #########################################################
    @staticmethod
    def get_user_id(user_id):
        if isinstance(user_id, (str, int, float)):
            return str(user_id)
        elif user_id is None:
            return None

        raise ValueError("User ID Must Be a String, Integer, Float, or None")

    @staticmethod
    def get_token_type(token_type):
        if token_type:
            return token_type
        return None

    @staticmethod
    def get_create_token(create_token):
        if create_token:
            if isinstance(create_token, bool):
                return create_token
            elif isinstance(create_token, str):
                return create_token.lower() == 'true'
            elif isinstance(create_token, (int, float)):
                return create_token == 1
            else:
                raise ValueError("Create Token Must Be a Boolean, String, Integer, Float, or None")
        return False

    @staticmethod
    def get_bearer_token(authorization):
        if isinstance(authorization, str):
            authorization = authorization.split(' ')
            if len(authorization) == 2:
                return authorization[1]
            else:
                raise ValueError("Authorization Must Be in the Format '<name> <token>'")
        elif authorization is None:
            return None

        raise ValueError("Authorization Must Be a String or None")

    @staticmethod
    def encode_token_key(token_key):
        if isinstance(token_key, str):
            return token_key.encode()
        elif token_key is None:
            return None
        
        raise ValueError("Token Key Must Be a String or None")

    @staticmethod
    def convert_headers_to_dict(headers):
        headers_mapping = TokenResponse.HEADERS_MAPPING.get_value()

        try:
            headers = dict(headers)
        except:
            raise ValueError("headers must be a dict or convertable to a dict")

        result = {}

        for key, header_key in headers_mapping.items():
            if header_key in headers:
                result[key] = json.loads(headers[header_key])

        return result

    @staticmethod
    def test_log_to_cloudwatch(final_step, request_token_info, success, return_info):

        # TODO: Add more insurance that sensitive info can't be logged

        user_passed_info = {
            'user_id': request_token_info['user_id'],
            'token_type': request_token_info['token_type'],
            'authorization': request_token_info['authorization'],
            'create_token': request_token_info['create_token'],
        }
        
        result = {
            'final_step': final_step,
            'user_passed_info': user_passed_info,
            'success': success,
            'return_info': return_info,
        }
        
        # TODO: change level to info when possible. Add security tagging.
        if not get_environment_variable_default("DEBUG_FASTLOAD_SINGLE_SERVER", False):
            logging.warning("[TOKEN_MANAGER_TEST_WARNING]: " + json.dumps(result))
