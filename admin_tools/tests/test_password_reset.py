# admin_tools/tests/test_password_reset.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

"""
Tests for the WeVoteServer password reset flow (staff, developers and volunteers).
See admin_tools/views_password_reset.py.

These lean on the behavior we actually care about: an attacker must not be able to learn which
email addresses have accounts, a reset link must only work once, and nobody gets signed in
without typing the new password.
"""

import re

from django.contrib.auth import authenticate
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from unittest import mock

from admin_tools import views_password_reset
from admin_tools.views_password_reset import generate_suggested_password
from voter.models import Voter

TEST_EMAIL = 'wv4734_tester@example.com'
OLD_PASSWORD = 'OldPassw0rd!xyz'
NEW_PASSWORD = 'Str0ng-New-Pass!42'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetFlowTests(TestCase):
    databases = '__all__'

    def setUp(self):
        cache.clear()
        mail.outbox = []
        # Do not actually sleep during tests.
        self._original_delay = views_password_reset.DELIBERATE_DELAY_SECONDS
        self._original_target = views_password_reset.RESET_RESPONSE_TARGET_SECONDS
        views_password_reset.DELIBERATE_DELAY_SECONDS = 0
        views_password_reset.RESET_RESPONSE_TARGET_SECONDS = 0
        self.voter = Voter(email=TEST_EMAIL, is_active=True, is_verified_volunteer=True)
        self.voter.set_password(OLD_PASSWORD)
        self.voter.save()

    def tearDown(self):
        views_password_reset.DELIBERATE_DELAY_SECONDS = self._original_delay
        views_password_reset.RESET_RESPONSE_TARGET_SECONDS = self._original_target
        cache.clear()

    def request_reset(self, email):
        return self.client.post(reverse('password_reset'), {'email': email})

    def get_set_password_page(self):
        """Walk from the emailed link to the form where the new password is typed."""
        reset_path = re.search(r'/password_reset/confirm/[^\s]+', mail.outbox[0].body).group(0).rstrip('.')
        response = self.client.get(reset_path)
        return reset_path, response['Location']

    def test_request_page_loads_and_offers_no_signup(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        # Account creation is deliberately not part of this flow.
        self.assertNotIn(b'sign up', response.content.lower())
        self.assertNotIn(b'signup', response.content.lower())

    def test_unknown_email_is_indistinguishable_from_known_email(self):
        """The whole point: no user enumeration."""
        self.request_reset('nobody-here@example.com')
        unknown_page = self.client.get(reverse('password_reset_done')).content
        self.assertEqual(len(mail.outbox), 0)

        cache.clear()
        self.request_reset(TEST_EMAIL)
        known_page = self.client.get(reverse('password_reset_done')).content
        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(unknown_page, known_page)

    def test_reset_email_contains_a_working_link(self):
        self.request_reset(TEST_EMAIL)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password_reset/confirm/', mail.outbox[0].body)

        _, set_password_url = self.get_set_password_page()
        response = self.client.get(set_password_url)
        self.assertEqual(response.status_code, 200)
        page = response.content.decode('utf-8')
        self.assertIn('new_password1', page)
        self.assertIn('new_password2', page)

    @override_settings(ALLOWED_HOSTS=['*'])
    def test_reset_link_ignores_forged_host_header(self):
        # WV-4734 FIX 1: even if a forged Host is accepted, the emailed link must point at our
        # configured server, not the attacker's domain, so the token cannot be stolen.
        self.client.post(
            reverse('password_reset'), {'email': TEST_EMAIL}, HTTP_HOST='evil.example.com')
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertNotIn('evil.example.com', body)
        canonical = views_password_reset.canonical_link_email_context()
        if canonical:
            self.assertIn(canonical['domain'], body)

    def test_set_password_page_offers_a_suggested_password(self):
        self.request_reset(TEST_EMAIL)
        _, set_password_url = self.get_set_password_page()
        page = self.client.get(set_password_url).content.decode('utf-8')
        self.assertIsNotNone(re.search(r'id="suggested_password"\s+value="[^"]+"', page))

    def test_weak_password_is_rejected(self):
        self.request_reset(TEST_EMAIL)
        _, set_password_url = self.get_set_password_page()
        response = self.client.post(set_password_url, {'new_password1': '123', 'new_password2': '123'})
        self.assertEqual(response.status_code, 200)  # redisplayed with errors
        self.assertIsNotNone(authenticate(username=TEST_EMAIL, password=OLD_PASSWORD))

    def test_mismatched_passwords_are_rejected(self):
        self.request_reset(TEST_EMAIL)
        _, set_password_url = self.get_set_password_page()
        response = self.client.post(
            set_password_url, {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD + 'zz'})
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(authenticate(username=TEST_EMAIL, password=OLD_PASSWORD))

    def test_successful_reset_redirects_to_login_without_signing_in(self):
        self.request_reset(TEST_EMAIL)
        _, set_password_url = self.get_set_password_page()
        response = self.client.post(
            set_password_url, {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith('/login/'))
        self.assertIsNotNone(authenticate(username=TEST_EMAIL, password=NEW_PASSWORD))
        self.assertIsNone(authenticate(username=TEST_EMAIL, password=OLD_PASSWORD))
        # The person must sign in with the new password, so no session should exist yet.
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_reset_link_only_works_once(self):
        self.request_reset(TEST_EMAIL)
        reset_path, set_password_url = self.get_set_password_page()
        self.client.post(set_password_url, {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})

        response = self.client.get(reset_path)
        if response.status_code == 302:
            response = self.client.get(response['Location'])
        self.assertIn(b'no longer valid', response.content)

    def test_send_suppression_sends_only_one_email(self):
        # Two quick requests for the same email: suppression lets only the first send.
        self.request_reset(TEST_EMAIL)
        self.request_reset(TEST_EMAIL)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_flood_still_leaves_owner_a_working_link(self):
        # The anti-lockout guarantee. An attacker hammers the victim's address. Suppression means
        # only one email goes out, it goes to the victim's own inbox, and its link still works, so
        # the victim is never blocked from resetting their own password.
        for _ in range(15):
            self.request_reset(TEST_EMAIL)
        self.assertEqual(len(mail.outbox), 1)
        _, set_password_url = self.get_set_password_page()
        response = self.client.post(
            set_password_url, {'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(authenticate(username=TEST_EMAIL, password=NEW_PASSWORD))

    def test_going_over_ip_limit_bans_the_source(self):
        with mock.patch.object(views_password_reset, 'RESET_REQUESTS_PER_IP', 2):
            for _ in range(4):
                self.request_reset('someone-else@example.com')
        self.assertTrue(views_password_reset.is_banned('request', '127.0.0.1'))

    def test_rate_limited_request_still_looks_normal(self):
        # A throttled or banned request must not look different, or it becomes an oracle.
        with mock.patch.object(views_password_reset, 'RESET_REQUESTS_PER_IP', 2):
            for _ in range(5):
                response = self.request_reset(TEST_EMAIL)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response['Location'].endswith('/password_reset/sent/'))

    def test_cascading_ban_escalates_and_resets(self):
        ip_address = '203.0.113.9'
        offense_key = 'password_reset_offense_request_' + views_password_reset._hashed(ip_address)
        self.assertFalse(views_password_reset.is_banned('request', ip_address))

        views_password_reset.register_offense('request', ip_address)
        self.assertTrue(views_password_reset.is_banned('request', ip_address))
        first_level = cache.get(offense_key)

        views_password_reset.register_offense('request', ip_address)
        self.assertEqual(cache.get(offense_key), first_level + 1)

        # Bans are per scope: a request ban does not touch the confirm endpoint.
        self.assertFalse(views_password_reset.is_banned('confirm', ip_address))

    def test_confirm_endpoint_is_rate_limited(self):
        # Hammering the confirm endpoint with guessed links eventually gets a generic throttle page.
        with mock.patch.object(views_password_reset, 'CONFIRM_ATTEMPTS_PER_IP', 3):
            last_response = None
            for _ in range(5):
                last_response = self.client.get(
                    '/password_reset/confirm/MQ/abc12-0123456789abcdef0123456789abcd/')
            self.assertEqual(last_response.status_code, 429)
            self.assertIn(b'Too Many Attempts', last_response.content)

    def test_inactive_account_gets_no_email(self):
        self.voter.is_active = False
        self.voter.save()
        self.request_reset(TEST_EMAIL)
        self.assertEqual(len(mail.outbox), 0)

    def test_account_without_usable_password_gets_no_email(self):
        """Regular voters sign in with emailed codes and have no password to reset."""
        self.voter.set_unusable_password()
        self.voter.save()
        self.request_reset(TEST_EMAIL)
        self.assertEqual(len(mail.outbox), 0)


class ResponseDeadlineTests(TestCase):
    """
    The reset request runs to a fixed total time so a real account (which sends an email) cannot be
    told apart from a nonexistent one by timing. These check the padding math without real sleeping.
    """
    def test_deadline_pads_short_requests(self):
        with mock.patch.object(views_password_reset, 'RESET_RESPONSE_TARGET_SECONDS', 1.0), \
                mock.patch.object(views_password_reset.time, 'monotonic', return_value=0.3), \
                mock.patch.object(views_password_reset.time, 'sleep') as fake_sleep:
            views_password_reset.sleep_until_deadline(0.0)  # 0.3s elapsed of a 1.0s budget
            fake_sleep.assert_called_once()
            self.assertAlmostEqual(fake_sleep.call_args[0][0], 0.7, places=3)

    def test_deadline_does_not_sleep_when_already_over(self):
        with mock.patch.object(views_password_reset, 'RESET_RESPONSE_TARGET_SECONDS', 0.1), \
                mock.patch.object(views_password_reset.time, 'monotonic', return_value=5.0), \
                mock.patch.object(views_password_reset.time, 'sleep') as fake_sleep:
            views_password_reset.sleep_until_deadline(0.0)  # 5.0s elapsed, past the budget
            fake_sleep.assert_not_called()


class SuggestedPasswordTests(TestCase):
    databases = '__all__'

    def test_suggested_password_is_strong_and_varies(self):
        first = generate_suggested_password()
        second = generate_suggested_password()
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 20)
        self.assertTrue(any(character.islower() for character in first))
        self.assertTrue(any(character.isupper() for character in first))
        self.assertTrue(any(character.isdigit() for character in first))
        self.assertTrue(any(not character.isalnum() for character in first))

    def test_suggested_password_avoids_confusable_characters(self):
        for _ in range(20):
            password = generate_suggested_password()
            for character in '0O1lI':
                self.assertNotIn(character, password)
