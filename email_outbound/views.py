# email_outbound/views.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

# See also email_outbound/views_admin.py for views used in the admin area

from django.db.models import F
from django.http import HttpResponse
from django.utils import timezone
from email_outbound.models import EmailCampaignRecipient
from wevote_functions.functions import positive_value_exists

# 1x1 transparent GIF bytes
PIXEL_GIF_BYTES = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
    b'\x00\x00\x02\x02D\x01\x00;'
)


def opened_tracking_pixel_view(request, open_tracking_code):
    if not positive_value_exists(open_tracking_code):
        return HttpResponse(status=204)
    # Try to get the recipient by the open tracking code
    try:
        recipient = EmailCampaignRecipient.objects.get(open_tracking_code=open_tracking_code)
    # If the recipient does not exist, return a 204 response
    except EmailCampaignRecipient.DoesNotExist:
        return HttpResponse(status=204)

    now = timezone.now()
    # Update the recipient's open tracking information
    EmailCampaignRecipient.objects.filter(id=recipient.id).update(
        open_tracking_count=F("open_tracking_count") + 1,
        open_tracking_last_open=now,
        open_tracking_first_open=recipient.open_tracking_first_open or now,
    )

    # Return the tracking pixel
    response = HttpResponse(PIXEL_GIF_BYTES, content_type="image/gif")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Expires"] = "0"
    return response
