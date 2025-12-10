from wevote_tokens.enums import TokenTypes
from wevote_tokens.models.single_use_tokens import SingleUseTokenManager
from wevote_tokens.enums import TokenHeaders, TokenCookies
from wevote_utils.functions import positive_value



class TokensManager():

    def __init__(self, token_types, scope, expiration_seconds=None, json_data=None):
        if not isinstance(token_types, list):
            token_types = [token_types]
        
        self.scope = scope
        self.token_types = token_types
        self.expiration_seconds = expiration_seconds
        self.json_data = json_data

        self.token_response = TokenResponse.TOKEN_RESPONSE.get_value()
        self.token_auth_info = TokenResponse.TOKEN_AUTHENTICATION.get_value()
        self.token_creation_info = TokenResponse.TOKEN_CREATION.get_value()

    #have a function tthat seves as a wrapper for a view
    def __call__(self, view_func):
        def _wrapped_view(request, *args, **kwargs):
            token_response = self.token_response

            # First, get headers
            request_token_info = self.get_request_token_info(request)

            # Check token type. Return 401 Unauthorized if not valid.
            if not request_token_info['token_type'] or request_token_info['token_type'] not in self.token_types:
                # return 401 unauthorized
                pass
            
            # And authenticate it with id, key, and scope
            token_response['token_authentication'] = self.token_authentication(request_token_info)

            
            # If that doesnt work, then see if we can use see if we can unlock a valid token
            # # by searching through user id, token typ,e and check old and new key for each token
            # # along with scope
            # # if that doesn't work, then return 401 unauthorized


            # if exists and is True, then create a new token
            if request_token_info['create_token'] and token_response['token_authentication']['success']:
                    token_response['token_creation'] = self.token_creation(request_token_info)
            else:
                pass

            # If no authorization, "return 401 Unauthorized"
            
            response =  view_func(request, *args, **kwargs)

            # check response type to append info to
            if response.headers.get("Content-Type") == "application/json":
                # Append token response info to response
            
            
        return _wrapped_view

    # While this function seems unecessary
    # It's better to have in case processing is necessary
    def get_user_id(self, user_id):
        return user_id

    def get_create_token(self, create_token):
        if create_token:
            if isinstance(create_token, bool):
                return create_token
            elif isinstance(create_token, str):
                return create_token.lower() == 'true'
            elif isinstance(create_token, int):
                return create_token == 1
        return False

    def get_token_type(self, token_type):
        if token_type:
            return token_type
        return None

    def get_bearer_token(self, authorization):
        if authorization:
            return authorization.split(' ')[-1]
        return None

    def encode_token_key(self, token_key):
        if token_key:
            return token_key.encode()
        return None

    # something that takes in a request, and gets needed information from headers or cookies
    def get_request_token_info(self, request):
        user_id = request.headers.get(TokenHeaders.USER_ID.value)
        token_type = request.headers.get(TokenHeaders.TOKEN_TYPE.value)
        authorization = request.headers.get(TokenHeaders.AUTHORIZATION.value)
        create_token = request.headers.get(TokenHeaders.CREATE_TOKEN.value)
        token_key = request.headers.get(TokenHeaders.TOKEN_KEY.value)
        new_token_key = request.headers.get(TokenHeaders.TOKEN_NEW_KEY.value)

        user_id = self.get_user_id(user_id)
        create_token = self.get_create_token(create_token)
        token_type = self.get_token_type(token_type)
        authorization = self.get_bearer_token(authorization)
        token_key = self.encode_token_key(token_key)
        new_token_key = self.encode_token_key(new_token_key)

        return {
            'user_id': user_id,
            'token_type': token_type,
            'authorization': authorization,
            'create_token': create_token,
            'token_key': token_key,
            'new_token_key': new_token_key,
        }

    # Have a function that takes in the request to validate the token info
    def token_authentication(self, request_token_info):
        token_auth_info = self.token_auth_info

        scope = self.scope

        user_id = request_token_info['user_id']
        token_type = request_token_info['token_type']
        token_id = request_token_info['authorization']
        token_key = request_token_info['token_key']

        if not token_id or not token_key:
            token_auth_info['error_message'] = "Authorization and token key are required"
            return token_auth_info
        
        if token_type == TokenTypes.SINGLE_USE:
            token_info = SingleUseTokenManager.authenticate_token(token_id, token_key, scope)
        else:
            token_auth_info['error_message'] = "Invalid token type"

        if token_info['success']:
            token_auth_info['success'] = True
            token_auth_info['status'] = token_info['status']
            token_auth_info['error_message'] = None
            token_auth_info['token_info'] = token_info
        elif positive_value(token_info['status']):
            token_auth_info['error_message'] = token_info['status']
        else:
            token_auth_info['error_message'] = "Unknown error"
        
        return token_auth_info
        

    def token_creation(self, request_token_info):
        token_creation_info = self.token_creation_info

        scope = self.scope
        expiration_seconds = self.expiration_seconds
        json_data = self.json_data

        user_id = request_token_info['user_id']
        token_type = request_token_info['token_type']
        encryption_key = request_token_info['new_token_key']

        if token_type == TokenTypes.SINGLE_USE:
            token_info = SingleUseTokenManager.create_token(user_id, validation_key, scope, expiration_seconds, json_data)
            if token_info['expiration_datetime']:
                token_info['expiration_datetime'] = \
                    token_info['expiration_datetime'].strftime('%Y-%m-%d %H:%M:%S')
        else:
            token_creation_info['error_message'] = "Invalid token type"

        if token_info['success']:
            token_creation_info['success'] = True
            token_creation_info['status'] = token_info['status']
            token_creation_info['error_message'] = None
            token_creation_info['token_info'] = token_info
        elif positive_value(token_info['status']):
            token_creation_info['error_message'] = token_info['status']
        else:
            token_creation_info['error_message'] = "Unknown error"
        
        return token_creation_info

    # something that takes a response, and adds needed token information to headers
    def add_response_token_info_headers(self, response, token_info):
        pass

    # something that takes a response, and adds needed token information to cookies
    def add_response_token_info_cookies(self, response, token_info):
        pass


    

