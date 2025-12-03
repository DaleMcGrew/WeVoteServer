
from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.test import RequestFactory
from wevote_tokens.models.single_use_tokens import SingleUseTokenManager, Scope
from wevote_tokens.enums import TokenUsage
from apis_v1.views.views_retrieve_tables import backup_one_table_to_s3_view
import json

class TestBackupOneTableToS3Tokens(TestCase):
    def setUp(self):
        self.scope = Scope.BACKUP_ONE_TABLE_TO_S3
        self.host = 'localhost:8000'
        self.url = f'{self.host}/apis/v1/backupOneTableToS3/'
        self.request = RequestFactory().get(
            self.url,
            {'table_name': 'table_name',
            'voter_api_device_id': ''}
            )
    
    @classmethod
    def setUpTestData(cls):
        cls.validation_key = SingleUseTokenManager.generate_encryption_key()
        cls.scope = Scope.BACKUP_ONE_TABLE_TO_S3
        cls.user_id = 'user_id'
        cls.test_token_info = SingleUseTokenManager.create_token(
            user_id=cls.user_id,
            validation_key=cls.validation_key,
            scope=cls.scope,
            expiration_seconds=1200,
            json_data=None
        )
        # Convert bytes to string for testing, in production headers are strings
        cls.validation_key_str = cls.validation_key.decode('utf-8')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Start patches at class level
        cls.mock_get_voter_api_device_id = patch(
            'apis_v1.views.views_retrieve_tables.get_voter_api_device_id',
            return_value=''
        ).start()
        
        cls.mock_backup_one_table_to_s3_controller = patch(
            'apis_v1.views.views_retrieve_tables.backup_one_table_to_s3_controller',
            return_value={
                'success': True,
                'status': '',
                'aws_s3_file_url': 'https://example.com/aws_s3_file_url'
            }
        ).start()
    
    @classmethod
    def tearDownClass(cls):
        patch.stopall()
        super().tearDownClass()

    def _assert_equal(self, values_dict, keys_to_check, expected_value, reason):
        for i, key in enumerate(keys_to_check):
            self.assertEqual(values_dict[key], expected_value[i], f"'{key}' Should Be {expected_value[i]} on {reason} but was {values_dict[key]}")


    def test_auth_token_and_new_key(self):
        request = self.request
        request.META['HTTP_AUTHORIZATION'] = f'Token {self.test_token_info["token_pk"]}'
        request.META['HTTP_X_SINGLE_USE_TOKEN_KEY'] = self.validation_key_str
        request.META['HTTP_X_SINGLE_USE_TOKEN_NEW_KEY'] = SingleUseTokenManager.generate_encryption_key().decode('utf-8')
        message_addon = "Valid Auth Token and New Key"

        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)

        # breakpoint()

        self.assertEqual(response.status_code, 200)
        self._assert_equal(response_json['token_info'], ['success'], [True], message_addon)
        self.assertIsNotNone(response_json['token_info']['token_pk'])
        self.assertNotEqual(response_json['token_info']['token_pk'], self.test_token_info['token_pk'])

    def test_auth_token_and_no_new_key(self):
        request = self.request
        request.META['HTTP_AUTHORIZATION'] = f'Token {self.test_token_info["token_pk"]}'
        request.META['HTTP_X_SINGLE_USE_TOKEN_KEY'] = self.validation_key_str
        message_addon = "Valid Auth Token and No New Key"

        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)
        

        self.assertEqual(response.status_code, 200)
        self._assert_equal(
            response_json['token_info'],
            ['success', 'scope', 'scope_display', 'token_user'],
            [True, self.scope, self.scope.label, self.user_id], 
            message_addon)

    
    def test_bad_token(self):
        request = self.request
        request.META['HTTP_AUTHORIZATION'] = f'Token {self.test_token_info["token_pk"] + 99999999999999999}'
        request.META['HTTP_X_SINGLE_USE_TOKEN_KEY'] = self.validation_key_str
        message_addon = "Bad Token"

        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)
        
        self.assertEqual(response.status_code, 200)
        self._assert_equal(
            response_json['token_info'],
            ['success'],
            [False],
            message_addon)
    
    def test_bad_token_key(self):
        request = self.request
        request.META['HTTP_AUTHORIZATION'] = f'Token {self.test_token_info["token_pk"]}'
        request.META['HTTP_X_SINGLE_USE_TOKEN_KEY'] = 'invalid_token_key'
        message_addon = "Bad Token Key"

        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)
        
        self.assertEqual(response.status_code, 200)
        self._assert_equal(
            response_json['token_info'],
            ['success'],
            [False],
            message_addon)

    def test_no_auth_token(self):
        request = self.request
        request.META['HTTP_X_SINGLE_USE_TOKEN_KEY'] = self.validation_key_str
        message_addon = "No Auth Token"
        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)
        
        self.assertEqual(response.status_code, 200)
        self._assert_equal(
            response_json['token_info'],
            ['success', 'status'],
            [False, 'Authorization token and key are required'],
            message_addon)

    def test_no_token_key(self):
        request = self.request
        request.META['HTTP_AUTHORIZATION'] = f'Token {self.test_token_info["token_pk"]}'
        message_addon = "No Token Key"
        
        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)
        
        self.assertEqual(response.status_code, 200)
        self._assert_equal(
            response_json['token_info'],
            ['success', 'status'],
            [False, 'Authorization token and key are required'],
            message_addon)

    def test_invalid_token_new_key(self):
        request = self.request
        request.META['HTTP_AUTHORIZATION'] = f'Token {self.test_token_info["token_pk"] + 99999999999999999}'
        request.META['HTTP_X_SINGLE_USE_TOKEN_KEY'] = self.validation_key_str
        request.META['HTTP_X_SINGLE_USE_TOKEN_NEW_KEY'] = SingleUseTokenManager.generate_encryption_key().decode('utf-8')
        message_addon = "Invalid Token New Key"
        response = backup_one_table_to_s3_view(request)
        response_json = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self._assert_equal(
            response_json['token_info'],
            ['success'],
            [False],
            message_addon)