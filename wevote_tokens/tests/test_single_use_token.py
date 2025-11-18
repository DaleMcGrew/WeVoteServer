from django.test import TestCase
from voter.models import VoterManager
from wevote_tokens.models.single_use_tokens import SingleUseToken, SingleUseTokenManager
from cryptography.fernet import Fernet
import json
from datetime import timedelta
from django.utils import timezone
import time

# Only used to test SingleUseToken model
class TestSingleUseToken(TestCase):
    def setUp(self):
        self.test_voter = VoterManager().create_voter(email='test@example.com', password='testpassword')['voter']
        self.test_validation_key = Fernet.generate_key()
        self.test_cipher = Fernet(self.test_validation_key)
    
    def test_single_use_token_creation(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        expiration = 300
        json_data = {'test': 'test'}

        token = SingleUseToken()
        token.save(user=voter, validation_key=validation_key, expiration_seconds=expiration, json_data=json_data)

        self.assertEqual(
            token._user,
            voter,
            "_user Not Set Correctly")
        self.assertEqual(
            self.test_cipher.decrypt(token._validation),
            validation_key,
            "_validation Not Set Correctly")
        self.assertEqual(
            json.loads(self.test_cipher.decrypt(token._json_data_encrypted).decode('utf-8')),
            json_data, 
            "_json_data_encrypted Not Set Correctly")
        self.assertLessEqual(
            (timezone.now() + timedelta(seconds=expiration)) - token._expiration_datetime,
            timedelta(seconds=1),
            "_expiration_datetime Not Set Correctly")

    def test_single_use_token_creation_with_invalid_validation_key(self):
        voter = self.test_voter
        invalid_validation_key = 'invalid'

        token = SingleUseToken()
        with self.assertRaisesMessage(ValueError, "Validation key must be a bytes object."):
            token.save(user=voter, validation_key=invalid_validation_key)

    def test_single_use_token_creation_with_invalid_json_data(self):
        voter = self.test_voter
        invalid_json_data = 1

        token = SingleUseToken()
        with self.assertRaisesMessage(ValueError, "JSON data must be a dictionary or None."):
            token.save(user=voter, validation_key=self.test_validation_key, json_data=invalid_json_data)
    
    def test_single_use_token_creation_with_large_json_data(self):
        voter = self.test_voter
        large_json_data = {'test': 'test' * 10000}
        large_json_data_size = len(bytes(json.dumps(large_json_data), "utf-8"))

        token = SingleUseToken()
        with self.assertRaisesMessage(ValueError, f"Json Data must be <= 8kb, currently {large_json_data_size} bytes."):
            token.save(user=voter, validation_key=self.test_validation_key, json_data=large_json_data)
    
    def test_single_use_token_creation_with_default_expiration(self):
        voter = self.test_voter
        default_expiration = 300
        validation_key = self.test_validation_key

        token = SingleUseToken()
        token.save(user=voter, validation_key=validation_key)

        self.assertLessEqual(
            (timezone.now() + timedelta(seconds=default_expiration)) - token._expiration_datetime,
            timedelta(seconds=1),
            "_expiration_datetime Not Set With Correct Default Expiration")

    def test_single_use_token_creation_with_invalid_expiration(self):
        voter = self.test_voter
        invalid_expiration = 'invalid'
        validation_key = self.test_validation_key

        token = SingleUseToken()
        with self.assertRaisesMessage(ValueError, "Expiration time must be an integer or float, in seconds."):
            token.save(user=voter, validation_key=validation_key, expiration_seconds=invalid_expiration)

    def test_single_use_token_creation_with_negative_expiration(self):
        voter = self.test_voter
        negative_expiration = -1
        validation_key = self.test_validation_key

        token = SingleUseToken()
        with self.assertRaisesMessage(ValueError, "Expiration Seconds must be a positive value."):
            token.save(user=voter, validation_key=validation_key, expiration_seconds=negative_expiration)

    def test_single_use_token_creation_with_large_expiration(self):
        voter = self.test_voter
        large_expiration = 1801
        validation_key = self.test_validation_key

        token = SingleUseToken()
        with self.assertRaisesMessage(ValueError, "Expiration Seconds must be <= 1800."):
            token.save(user=voter, validation_key=validation_key, expiration_seconds=large_expiration)


class TestSingleUseTokenManager(TestCase):

    def setUp(self):
        self.test_voter = VoterManager().create_voter(email='test@example.com', password='testpassword')['voter']
        self.test_validation_key = Fernet.generate_key()
        self.test_cipher = Fernet(self.test_validation_key)

    def test_generate_encryption_key(self):
        
        encryption_key = SingleUseTokenManager.generate_encryption_key()

        self.assertEqual(len(encryption_key), len(Fernet.generate_key()), "Encryption Key Length Not Correct")
        self.assertIsInstance(encryption_key, bytes, "Encryption Key Not a bytes object")
        self.assertIsNotNone(encryption_key, "Encryption Key Should Not Be None")

    def test_create_token(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        expiration = 300

        token_info = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, expiration_seconds=expiration)

        self.assertEqual(token_info['success'], True, "Token Creation Failed")
        self.assertEqual(token_info['status'], "TOKEN CREATED", "Token Creation Status Not Correct")
        self.assertNotEqual(token_info['token_pk'], None, "Token PK Should Be Set")
        self.assertLessEqual(
            (timezone.now() + timedelta(seconds=expiration)) - token_info['expiration_datetime'],
            timedelta(seconds=1),
            "Expiration Datetime Not Set Correctly")
        self.assertEqual(token_info['token_user'], voter, "Token User Not Correct")

    def test_create_token_failure(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        expiration = 300

        token_info = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, expiration_seconds='invalid')
        
        self.assertEqual(token_info['success'], False, "Token Creation Should Have Failed")
        self.assertEqual(
            token_info['status'],
            "TOKEN SAVE FAILED: Expiration time must be an integer or float, in seconds.",
            "Token Creation Status Not Correct")
        self.assertEqual(token_info['token_pk'], None, "Token PK Should Not Be Set On Save Failure")
        self.assertEqual(token_info['expiration_datetime'], None, "Expiration Datetime Should Not Be Set On Save Failure")
        self.assertEqual(token_info['token_user'], None, "Token User Should Not Be Set On Save Failure")
        
    def test_authenticate_retrieve_token(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        json_data = {'test': 'test'}

        token_pk = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, json_data=json_data)['token_pk']

        token_info = SingleUseTokenManager.authenticate_retrieve_token(token_pk, validation_key)

        print(token_info)
        self.assertTrue(token_info['success'], "Token Authentication Should Have Succeeded")
        self.assertEqual(token_info['status'], "TOKEN RETRIEVED AND AUTHENTICATED", "Token Authentication Status Not Correct")
        self.assertIsNotNone(token_info['expiration_datetime'], "Expiration Datetime Should Be Retrieved")
        self.assertEqual(token_info['json_data'], {'test': 'test'}, "JSON Data Should Be Retrieved")
        self.assertEqual(token_info['token_user'], voter, "Token User Should Be Retrieved")
        self.assertFalse(token_info['expired'], "Token Should Not Be Marked As Expired On Authentication")
        self.assertFalse(SingleUseToken.objects.filter(pk=token_pk).exists(), "Token Should Be Deleted After Authentication")

    def test_authenticate_retrieve_token_invalid_pk(self):
        invalid_pk = 999999
        voter = self.test_voter
        validation_key = self.test_validation_key
        json_data = {'test': 'test'}


        token_pk = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, json_data=json_data)['token_pk']
        token_info = SingleUseTokenManager.authenticate_retrieve_token(invalid_pk, validation_key)

        self.assertFalse(token_info['success'], "Token Retrieval Should Have Failed")
        self.assertEqual(token_info['status'], "TOKEN NOT FOUND: SingleUseToken matching query does not exist.", "Token Retrieval Status Not Correct")
        self.assertIsNone(token_info['expiration_datetime'], "Expiration Datetime Should Not Be Retrieved On Not Found")
        self.assertIsNone(token_info['token_user'], "Token User Should Not Be Retrieved On Not Found")
        self.assertIsNone(token_info['json_data'], "JSON Data Should Not Be Retrieved On Not Found")
        self.assertFalse(token_info['expired'], "Token Should Not Be Marked As Expired On Not Found")
        self.assertTrue(SingleUseToken.objects.filter(pk=token_pk).exists(), "Token Should Still Exist After Retrieval Failure")
    
    def test_authenticate_retrieve_token_invalid_validation_key(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        invalid_validation_key = Fernet.generate_key()
        json_data = {'test': 'test'}

        token_pk = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, json_data=json_data)['token_pk']
        token_info = SingleUseTokenManager.authenticate_retrieve_token(token_pk, invalid_validation_key)

        self.assertFalse(token_info['success'], "Token Authentication Should Have Failed")
        self.assertEqual(token_info['status'], "VALIDATION DECRYPTION ERROR: Invalid Key", "Token Authentication Status Not Correct")
        self.assertIsNone(token_info['expiration_datetime'], "Expiration Datetime Should Not Be Retrieved On Invalid Validation Key")
        self.assertIsNone(token_info['token_user'], "Token User Should Not Be Retrieved On Invalid Validation Key")
        self.assertIsNone(token_info['json_data'], "JSON Data Should Not Be Retrieved On Invalid Validation Key")
        self.assertFalse(token_info['expired'], "Token Should Not Be Marked As Expired On Invalid Validation Key")
        self.assertTrue(SingleUseToken.objects.filter(pk=token_pk).exists(), "Token Should Still Exist After Authentication Failure")

    def test_authenticate_retrieve_token_expired(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        expiration = 0
        json_data = {'test': 'test'}

        token_pk = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, expiration_seconds=expiration, json_data=json_data)['token_pk']
        time.sleep(1)
        token_info = SingleUseTokenManager.authenticate_retrieve_token(token_pk, validation_key)

        self.assertFalse(token_info['success'], "Token Authentication Should Have Failed")
        self.assertEqual(token_info['status'], "TOKEN EXPIRED", "Token Authentication Status Not Correct")
        self.assertIsNotNone(token_info['expiration_datetime'], "Expiration Datetime Should Be Retrieved On Expired Token")
        self.assertIsNone(token_info['json_data'], "JSON Data Should Not Be Retrieved On Expired Token")
        self.assertIsNone(token_info['token_user'], "Token User Should Not Be Retrieved On Expired Token")
        self.assertTrue(token_info['expired'], "Token Should Be Marked As Expired")
        self.assertFalse(SingleUseToken.objects.filter(pk=token_pk).exists(), "Token Should Not Exist After Expiration")

    def test_authenticate_retrieve_token_with_json_data(self):
        voter = self.test_voter
        validation_key = self.test_validation_key
        json_data = {'test': 'test'}

        token_pk = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key, json_data=json_data)['token_pk']
        token_info = SingleUseTokenManager.authenticate_retrieve_token(token_pk, validation_key)

        self.assertTrue(token_info['success'], "Token Authentication Should Have Succeeded")
        self.assertEqual(token_info['status'], "TOKEN RETRIEVED AND AUTHENTICATED", "Token Authentication Status Not Correct")
        self.assertIsNotNone(token_info['expiration_datetime'], "Expiration Datetime Should Be Retrieved On Valid Token")
        self.assertEqual(token_info['json_data'], json_data, "JSON Data Should Be Retrieved On Valid Token With JSON Data")
        self.assertEqual(token_info['token_user'], voter, "Token User Should Be Retrieved On Valid Token")
        self.assertFalse(token_info['expired'], "Token Should Not Be Marked As Expired On Valid Token")
        self.assertFalse(SingleUseToken.objects.filter(pk=token_pk).exists(), "Token Should Not Exist After Authentication")
    
    def test_authenticate_retrieve_token_with_no_json_data(self):
        voter = self.test_voter
        validation_key = self.test_validation_key

        token_pk = SingleUseTokenManager.create_token(user=voter, validation_key=validation_key)['token_pk']
        token_info = SingleUseTokenManager.authenticate_retrieve_token(token_pk, validation_key)

        self.assertTrue(token_info['success'], "Token Authentication Should Have Succeeded")
        self.assertEqual(token_info['status'], "TOKEN RETRIEVED AND AUTHENTICATED", "Token Authentication Status Not Correct")
        self.assertIsNotNone(token_info['expiration_datetime'], "Expiration Datetime Should Be Retrieved On Valid Token")
        self.assertIsNone(token_info['json_data'], "No Data Should Be Retrieved On Valid Token With No Json Data")
        self.assertEqual(token_info['token_user'], voter, "Token User Should Be Retrieved On Valid Token")
        self.assertFalse(token_info['expired'], "Token Should Not Be Marked As Expired On Valid Token")
        self.assertFalse(SingleUseToken.objects.filter(pk=token_pk).exists(), "Token Should Not Exist After Authentication")