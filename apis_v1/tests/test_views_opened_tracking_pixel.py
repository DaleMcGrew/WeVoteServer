# apis_v1/tests/test_views_opened_tracking_pixel.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.test import TestCase
from django.urls import reverse

from email_outbound.models import EmailCampaignRecipient


class WeVoteAPIsV1TestsOpenedTrackingPixel(TestCase):
    databases = ["default", "readonly"]

    def setUp(self):
        self.recipient = EmailCampaignRecipient.objects.create(
            email_campaign_id=1,
            open_tracking_code="test_open_code_123",
            open_tracking_count=0,
            open_tracking_first_open=None,
            open_tracking_last_open=None,
        )
        self.url = reverse(
            "apis_v1:opened_tracking_pixel",
            kwargs={"open_tracking_code": self.recipient.open_tracking_code},
        )

    def test_opened_tracking_pixel_updates_fields(self):
        # First hit
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/gif")

        self.recipient.refresh_from_db()
        first_open = self.recipient.open_tracking_first_open
        last_open = self.recipient.open_tracking_last_open

        self.assertEqual(self.recipient.open_tracking_count, 1)
        self.assertIsNotNone(first_open)
        self.assertIsNotNone(last_open)

        # Second hit increments count and last_open, first_open stays same
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.open_tracking_count, 2)
        self.assertEqual(self.recipient.open_tracking_first_open, first_open)
        self.assertNotEqual(self.recipient.open_tracking_last_open, last_open)

    def test_opened_tracking_pixel_unknown_code(self):
        response = self.client.get(
            reverse("apis_v1:opened_tracking_pixel", kwargs={"open_tracking_code": "nope"})
        )
        self.assertEqual(response.status_code, 204)