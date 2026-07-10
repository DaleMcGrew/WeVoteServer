from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from wevote_tokens.models.single_use_tokens import SingleUseTokenManager, Scope
from wevote_tokens.enums import TokenHeaders, TokenTypes, TokenResponse
import json
from wevote_tokens.utils import TokensManager
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse, StreamingHttpResponse

class TestTokensManager(TestCase):
    # TODO: Add tests for convert_headers_to_dict
    
    @classmethod
    def setUpTestData(cls):
        cls.user_id = 'user_id'
        cls.token_type = TokenTypes.SINGLE_USE.value
        cls.validation_key = SingleUseTokenManager.generate_encryption_key()
        cls.new_validation_key = SingleUseTokenManager.generate_encryption_key()
        cls.validation_key_str = cls.validation_key.decode('utf-8')
        cls.new_validation_key_str = cls.new_validation_key.decode('utf-8')
        cls.scope = Scope.BACKUP_ONE_TABLE_TO_S3
        cls.expiration_seconds = 1200
        cls.json_data = {'test': 'test'}

        cls.request = RequestFactory().get( 
            'https://example.com',
            {'table_name': 'table_name',
            'voter_api_device_id': ''}
            )

        cls.response = HttpResponse()
        
        cls.test_token_info = SingleUseTokenManager.create_token(
            user_id=cls.user_id,
            validation_key=cls.validation_key,
            scope=cls.scope,
            expiration_seconds=cls.expiration_seconds,
            json_data=cls.json_data
        )

        cls.new_test_token_info =  SingleUseTokenManager.create_token(
            user_id=cls.user_id,
            validation_key=cls.new_validation_key,
            scope=cls.scope,
            expiration_seconds=cls.expiration_seconds,
            json_data=cls.json_data
        )

        cls.request_headers = {
            TokenHeaders.USER_ID.value: cls.user_id,
            TokenHeaders.TOKEN_TYPE.value: cls.token_type,
            TokenHeaders.AUTHORIZATION.value: f'Bearer {cls.test_token_info["token_pk"]}',
            TokenHeaders.CREATE_TOKEN.value: 'true',
            TokenHeaders.TOKEN_KEY.value: cls.validation_key_str,
            TokenHeaders.TOKEN_NEW_KEY.value: cls.new_validation_key_str,
        }

        cls.request_token_info = {
            'user_id': cls.user_id,
            'token_type': TokenTypes.SINGLE_USE.value,
            'authorization': cls.test_token_info['token_pk'],
            'create_token': True,
            'token_key': cls.validation_key,
            'new_token_key': cls.new_validation_key,
            'error_message': None
        } 

        cls.response_token_info = {
            **TokenResponse.HEADERS_MAPPING.get_value(),
            **{
                'misc_headers': 'misc_value',
            }
        }
    
    def setUp(self):
        self.manager = TokensManager(
            token_types=[TokenTypes.SINGLE_USE.value],
            scope=Scope.BACKUP_ONE_TABLE_TO_S3,
            expiration_seconds=self.expiration_seconds,
            json_data=self.json_data)

            
    #########################################################
    # test __call__
    #########################################################
    def test_wrapper_makes_calls(self):
        token_authentication_info = {
            'success': True,
            'status': 'TOKEN RETRIEVED AND AUTHENTICATED',
            'error_message': None,
            'token_info': None
        }
        token_creation_info = {
            'success': True,
            'status': 'TOKEN CREATED',
            'error_message': None,
            'token_info': None
        }

        with patch.object(self.manager, "get_request_token_info", return_value=self.request_token_info) as mock_get_request_token_info, \
             patch.object(self.manager, "token_authentication", return_value=token_authentication_info) as mock_token_authentication, \
             patch.object(self.manager, "token_creation", return_value=token_creation_info) as mock_token_creation:

            mock_view_func = MagicMock()
            mock_view_func.return_value = HttpResponse(status=200)
            response = self.manager.__call__(mock_view_func)(self.request)

            mock_get_request_token_info.assert_called_once_with(self.request)
            mock_token_authentication.assert_called_once_with(self.request_token_info)
            mock_token_creation.assert_called_once_with(self.request_token_info)
            mock_view_func.assert_called_once_with(self.request)
            self.assertNotEqual(response.headers, self.request.headers, "Response Headers Should Not Be the Same as the Request Headers")

    def test_wrapper_invalid_token_type(self):
        request_token_info = self.request_token_info
        request_token_info['token_type'] = 'invalid'
        

        with patch.object(self.manager, "get_request_token_info", return_value=request_token_info) as mock_get_request_token_info, \
             patch.object(self.manager, "token_authentication", return_value=None) as mock_token_authentication, \
             patch.object(self.manager, "token_creation", return_value=None) as mock_token_creation:

            mock_view_func = MagicMock()
            mock_view_func.return_value = HttpResponse(status=200)
            response = self.manager.__call__(mock_view_func)(self.request)

            mock_get_request_token_info.assert_called_once_with(self.request)
            mock_token_authentication.assert_not_called()
            mock_token_creation.assert_not_called()
            mock_view_func.assert_called_once_with(self.request)

    #########################################################
    # test get_request_token_info
    #########################################################
    def test_get_request_token_info_returns_dict(self):
        request = self.request
        headers = self.request_headers

        for key, value in headers.items():
            request.META['HTTP_'+key.upper()] = value
        
        with patch.object(TokensManager, "get_user_id", return_value=headers[TokenHeaders.USER_ID.value]) as get_user_id, \
            patch.object(TokensManager, "get_create_token", return_value=False) as get_create_token, \
            patch.object(TokensManager, "get_token_type", return_value=headers[TokenHeaders.TOKEN_TYPE.value]) as get_token_type, \
            patch.object(TokensManager, "get_bearer_token", return_value='key') as get_bearer_token, \
            patch.object(TokensManager, "encode_token_key", return_value=b'new_key') as encode_token_key:

            response = self.manager.get_request_token_info(request)

            get_user_id.assert_called_once_with(headers[TokenHeaders.USER_ID.value])
            get_create_token.assert_called_once_with(headers[TokenHeaders.CREATE_TOKEN.value])
            get_token_type.assert_called_once_with(headers[TokenHeaders.TOKEN_TYPE.value])
            get_bearer_token.assert_called_once_with(headers[TokenHeaders.AUTHORIZATION.value])
            self.assertEqual(encode_token_key.call_count, 2)

            self.assertIn('user_id', response, "User ID Should Be in Response")
            self.assertIn('token_type', response, "Token Type Should Be in Response")
            self.assertIn('authorization', response, "Authorization Should Be in Response")
            self.assertIn('create_token', response, "Create Token Should Be in Response")
            self.assertIn('token_key', response, "Token Key Should Be in Response")
            self.assertIn('new_token_key', response, "New Token Key Should Be in Response")

    #########################################################
    # test format_request_headers
    #########################################################
    def test_format_request_headers(self):
        expected_response = self.request_headers

        response = self.manager.format_request_headers(
            user_id=self.user_id,
            token_type=self.token_type,
            authorization=self.test_token_info["token_pk"],
            create_token=expected_response[TokenHeaders.CREATE_TOKEN.value],
            token_key=self.validation_key_str,
            new_token_key=self.new_validation_key_str)

        self.assertIsInstance(response, dict, "Response Should Be a Dict")
        self.assertEqual(response, expected_response, f"Response Should Be {expected_response} but was {response}")

    #########################################################
    # test token_creation
    #########################################################
    def test_token_creation(self):
        request_token_info = self.request_token_info

        mock_return_value = {
            'success': True,
            'status': 'TOKEN CREATED',
            'token_pk': 'token_pk',
            'expiration_datetime': timezone.now() + timedelta(seconds=self.expiration_seconds),
        }

        with patch.object(SingleUseTokenManager, "create_token", return_value=mock_return_value) as mock_create_token:
            response = self.manager.token_creation(request_token_info)

            mock_create_token.assert_called_once_with(
                request_token_info['user_id'],
                request_token_info['new_token_key'],
                self.manager.scope,
                self.manager.expiration_seconds,
                self.manager.json_data)
            self.assertEqual(response['success'], True, "Success Should Be True")
            self.assertEqual(response['status'], 'TOKEN CREATED', "Status Should Be 'TOKEN CREATED'")
            self.assertIsNone(response['error_message'], "Error Message Should Be None")
            self.assertEqual(response['token_info'], mock_return_value, "Token Info Should Be the Mock Return Value")
            self.assertIsInstance(response['token_info']['expiration_datetime'], str, "Expiration Datetime Should Be a String")

    def test_token_creation_invalid_token_type(self):
        request_token_info = self.request_token_info
        request_token_info['token_type'] = 'invalid'

        with patch.object(SingleUseTokenManager, "create_token", return_value=None) as mock_create_token:
            response = self.manager.token_creation(request_token_info)

            mock_create_token.assert_not_called()
            self.assertFalse(response['success'], "Success Should Be False")
            self.assertIsNone(response['status'], "Status Should Be None")
            self.assertEqual(response['error_message'], f"Invalid token type: {request_token_info['token_type']}", "Error Message Should Be an Invalid Token Type")
            self.assertIsNone(response['token_info'], "Token Info Should Be None")

    def test_token_creation_token_error(self):
        request_token_info = self.request_token_info
        request_token_info['new_token_key'] = 'invalid_token_key'.encode()
        error_message = 'Some Error Message'

        mock_return_value = {
            'success': False,
            'status': error_message,
        }

        with patch.object(SingleUseTokenManager, "create_token", return_value=mock_return_value) as mock_create_token:
            response = self.manager.token_creation(request_token_info)

            mock_create_token.assert_called_once_with(
                request_token_info['user_id'],
                request_token_info['new_token_key'],
                self.manager.scope,
                self.manager.expiration_seconds,
                self.manager.json_data)
            self.assertFalse(response['success'], "Success Should Be False")
            self.assertIsNone(response['status'], "Status Should Be None")
            self.assertEqual(response['error_message'], error_message, f"Error Message Should Be {error_message} but was {response['error_message']}")
            self.assertIsNone(response['token_info'], "Token Info Should Be None")

    def test_token_creation_unknown_error(self):
        request_token_info = self.request_token_info
        error_message = 'Unknown error'

        mock_return_value = {
            'success': False,
            'status': None,
        }

        with patch.object(SingleUseTokenManager, "create_token", return_value=mock_return_value) as mock_create_token:
            response = self.manager.token_creation(request_token_info)

            mock_create_token.assert_called_once_with(
                request_token_info['user_id'],
                request_token_info['new_token_key'],
                self.manager.scope,
                self.manager.expiration_seconds,
                self.manager.json_data)
            self.assertFalse(response['success'], "Success Should Be False")
            self.assertIsNone(response['status'], "Status Should Be None")
            self.assertEqual(response['error_message'], error_message, f"Error Message Should Be {error_message} but was {response['error_message']}")
            self.assertIsNone(response['token_info'], "Token Info Should Be None")


    #########################################################
    # test token_authentication failure cases
    #########################################################
    def test_token_authentication_no_token_id(self):
        request_token_info = self.request_token_info
        request_token_info['authorization'] = None

        response = self.manager.token_authentication(request_token_info)

        self.assertFalse(response['success'], "Success Should Be False")
        self.assertIsNone(response['status'], "Status Should Be None")
        self.assertEqual(response['error_message'], "Authorization and token key are required", "Error Message Should Be 'Authorization and token key are required'")
        self.assertIsNone(response['token_info'], "Token Info Should Be None")
    
    def test_token_authentication_no_token_key(self):
        request_token_info = self.request_token_info
        request_token_info['token_key'] = None

        response = self.manager.token_authentication(request_token_info)

        self.assertFalse(response['success'], "Success Should Be False")
        self.assertIsNone(response['status'], "Status Should Be None")
        self.assertEqual(response['error_message'], "Authorization and token key are required", "Error Message Should Be 'Authorization and token key are required'")
        self.assertIsNone(response['token_info'], "Token Info Should Be None")

    def test_token_authentication_invalid_token_type(self):
        request_token_info = self.request_token_info
        request_token_info['token_type'] = 'invalid'

        response = self.manager.token_authentication(request_token_info)

        self.assertFalse(response['success'], "Success Should Be False")
        self.assertIsNone(response['status'], "Status Should Be None")
        self.assertEqual(response['error_message'], f"Invalid token type: {request_token_info['token_type']}", "Error Message Should Be an Invalid Token Type")
        self.assertIsNone(response['token_info'], "Token Info Should Be None")

    def test_token_authentication_invalid_token_keys(self):
        request_token_info = self.request_token_info
        request_token_info['token_key'] = 'invalid_token_key'
        request_token_info['new_token_key'] = 'invalid_new_token_key'

        response = self.manager.token_authentication(request_token_info)

        self.assertFalse(response['success'], "Success Should Be False")
        self.assertIsNone(response['status'], "Status Should Be None")
        self.assertIsNotNone(response['error_message'], "There should be an error when invalid token keys are provided")
        self.assertIsNone(response['token_info'], "Token Info Should Be None")

    #########################################################
    # test token_authentication success cases
    #########################################################
    def test_token_authentication(self):
        request_token_info = self.request_token_info
        # Make sure we don't accidently validate the backup key
        request_token_info['new_token_key'] = 'invalid_new_token_key'.encode()

        with patch.object(
            SingleUseTokenManager,
            "authenticate_retrieve_token",
            wraps=SingleUseTokenManager.authenticate_retrieve_token
        ) as mock_authenticate_retrieve_token:
            response = self.manager.token_authentication(request_token_info)

            mock_authenticate_retrieve_token.assert_called_once_with(
                request_token_info['authorization'],
                request_token_info['token_key'],
                self.manager.scope)
            self.assertEqual(response['success'], True, "Success Should Be True")
            self.assertEqual(response['status'], 'TOKEN RETRIEVED AND AUTHENTICATED', "Status Should Be 'TOKEN RETRIEVED AND AUTHENTICATED'")
            self.assertIsNone(response['error_message'], "Error Message Should Be None")
            self.assertIsNotNone(response['token_info'], "Token Info Should return a value")
            self.assertIsInstance(response['token_info']['expiration_datetime'], str, "Expiration Datetime Should Be a String")

    def test_token_authentication_first_token_not_found(self):
        request_token_info = self.request_token_info
        request_token_info['authorization'] = 'invalid_token_pk'
        # Swapping values because were testing if a new token was created 
        # with the new key on a previous call (for faulty api connection)

        response = self.manager.token_authentication(request_token_info)

        self.assertTrue(response['success'], "Success Should Be True")
        self.assertEqual(response['status'], 'TOKEN RETRIEVED AND AUTHENTICATED', "Status Should Be 'TOKEN RETRIEVED AND AUTHENTICATED'")
        self.assertIsNone(response['error_message'], "Error Message Should Be None")
        self.assertIsNotNone(response['token_info'], "Token Info Should return a value")

    #########################################################
    # test add_response_token_info_headers
    #########################################################
    def test_add_response_token_info_headers_returns_response(self):
        test_response = self.response
        test_token_response = self.response_token_info
        
        response = self.manager.add_response_token_info_headers(test_response, test_token_response)

        self.assertIsInstance(response, HttpResponse, "Response Should Be an HttpResponse")

    def test_add_response_token_info_headers_returns_headers_added(self):
        test_response = self.response
        test_token_response = self.response_token_info

        expected_headers = {}
        headers_mapping = TokenResponse.HEADERS_MAPPING.get_value()
        for key, value in headers_mapping.items():
            expected_headers[value] = json.dumps(value)

        expected_response_headers = {
            **test_response.headers,
            **expected_headers
        }

        response = self.manager.add_response_token_info_headers(test_response, test_token_response)

        self.assertEqual(response.headers, expected_response_headers, "Response Headers Should {expected_response_headers} but was {response.headers}")

    def test_add_response_token_info_headers_returns_no_empty_headers(self):
        test_response = self.response
        test_token_response = self.response_token_info

        for key, value in test_token_response.items():
            test_token_response[key] = None

        response = self.manager.add_response_token_info_headers(test_response, test_token_response)


    def test_add_response_token_info_headers_returns_no_streaming_headers(self):
        test_response = StreamingHttpResponse()
        test_token_response = self.response_token_info

        expected_response_headers = test_response.headers.copy()

        response = self.manager.add_response_token_info_headers(test_response, test_token_response)

        self.assertEqual(response.headers, expected_response_headers, "Response Headers Should {expected_response_headers} but was {response.headers}")

    def test_add_response_token_info_headers_returns_no_headers(self):
        test_response = self.response
        test_token_response = TokenResponse.TOKEN_RESPONSE.get_value()

        expected_response_headers = test_response.headers.copy()

        response = self.manager.add_response_token_info_headers(test_response, test_token_response)

        self.assertEqual(response.headers, expected_response_headers, "Response Headers Should {expected_response_headers} but was {response.headers}")

class TestTokensManagerHelperFunctions(TestCase):

    def setUp(self):
        self.manager = TokensManager(token_types=[TokenTypes.SINGLE_USE], scope=Scope.BACKUP_ONE_TABLE_TO_S3)

    #########################################################
    # test get_user_id
    #########################################################
    def test_get_user_id_returns_string(self):
        non_string = 1234567890
        
        response = self.manager.get_user_id(non_string)
        
        self.assertIsInstance(response, str, "User ID Should Be a String")
    
    def test_get_user_id_returns_none(self):
        none_value = None
        
        response = self.manager.get_user_id(none_value)
        
        self.assertIsNone(response, "User ID Should Be None")

    def test_get_user_id_raises_value_error(self):
        non_string = {'not a string'}
        
        with self.assertRaisesMessage(ValueError, "User ID Must Be a String, Integer, Float, or None"):
            self.manager.get_user_id(non_string)
        
    #########################################################
    # test get_create_token
    #########################################################
    def test_get_create_token_returns_boolean(self):
        boolean_value = True
        
        response = self.manager.get_create_token(boolean_value)
        
        self.assertIsInstance(response, bool, "Create Token Should Be a Boolean")
    
    def test_get_create_token_returns_none(self):
        none_value = None
        
        response = self.manager.get_create_token(none_value)
        
        self.assertFalse(response, "Create Token Should Be False")

    def test_get_create_token_raises_value_error(self):
        non_boolean = {'not a boolean'}
        
        with self.assertRaisesMessage(ValueError, "Create Token Must Be a Boolean, String, Integer, Float, or None"):
            self.manager.get_create_token(non_boolean)

    #########################################################
    # test get_token_type
    #########################################################
    def test_get_token_type_returns_passed_value(self):
        passed_value = TokenTypes.SINGLE_USE.value
        
        response = self.manager.get_token_type(passed_value)
        
        self.assertEqual(response, passed_value, "Token Type Should Be the Passed Value")

    def test_get_token_type_returns_none(self):
        none_value = None
        
        response = self.manager.get_token_type(none_value)
        
        self.assertIsNone(response, "Token Type Should Be None")


    #########################################################
    # test get_bearer_token
    #########################################################
    def test_get_bearer_token_returns_token(self):
        bearer_token = 'Bearer token'
        
        response = self.manager.get_bearer_token(bearer_token)
        
        self.assertEqual(response, 'token', "Bearer Token Should Be  'Token' after 'Bearer '")

    def test_get_bearer_token_not_string(self):
        non_string = 1234567890
        
        with self.assertRaisesMessage(ValueError, "Authorization Must Be a String or None"):
            self.manager.get_bearer_token(non_string)
    
    def test_get_bearer_token_not_in_format(self):
        non_format = 'token'
        
        with self.assertRaisesMessage(ValueError, "Authorization Must Be in the Format '<name> <token>'"):
            self.manager.get_bearer_token(non_format)
        

    #########################################################
    # test encode_token_key
    #########################################################
    def test_encode_token_key_returns_bytes(self):
        token_key = 'token_key'
        
        response = self.manager.encode_token_key(token_key)
        
        self.assertIsInstance(response, bytes, "Token Key Should Be Encoded to Bytes")
    
    def test_encode_token_key_returns_none(self):
        none_value = None

        response = self.manager.encode_token_key(none_value)
        
        self.assertIsNone(response, "Token Key Should Be None")

    def test_encode_token_key_raises_value_error(self):
        non_string = 1234567890
        
        with self.assertRaisesMessage(ValueError, "Token Key Must Be a String or None"):
            self.manager.encode_token_key(non_string)

