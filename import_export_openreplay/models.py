# import_export_openreplay/models.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-


#Package requirements error: "Django==5.0.11 djange-bootstrap3==15.0.0 are not satisfied


from django.db import models
import uuid

from numpy.ma.core import true_divide

import wevote_functions.admin
from wevote_functions.functions import convert_to_int, positive_value_exists

# SESSIONS
class OpenReplaySession(models.Model):
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    errors_count = models.PositiveIntegerField(null=True)
    events_count = models.PositiveIntegerField(null=True)
    pages_count = models.PositiveIntegerField(null=True)
    project_id = models.CharField(max_length=255, null=True)
    user_uuid = models.CharField(max_length=36, null=True)
    user_id = models.CharField(max_length=25)
    user_agent = models.TextField(null=True, blank=True, help_text="Full User-Agent string")
    user_os = models.CharField(max_length=100, null=True, blank=True)
    user_browser = models.CharField(max_length=150, null=True, blank=True)
    user_device = models.CharField(max_length=200, null=True, blank=True)
    user_country = models.CharField(max_length=15, null=True, blank=True)
    start_ts = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
# Id INTEGER,
# projectId VARCHAR(255) ,
# sessionId  VARCHAR(255) ,
# userUuid VARCHAR(255) ,
# userId VARCHAR(255) NOT NULL,
# userAgent VARCHAR(255) ,
# userOs VARCHAR(255) ,
# userBrowser VARCHAR(255) ,
# userDevice VARCHAR(255) ,
# userCountry VARCHAR(255) ,
# startTs VARCHAR(255) ,
# duration VARCHAR(255) ,
# eventsCount VARCHAR(255) ,
# pagesCount VARCHAR(255) ,
# errorsCount VARCHAR(255),

    def __str__(self):
        return str(self.session_id)


# EVENTS
class OpenReplayEvent(models.Model):
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(OpenReplaySession, on_delete=models.CASCADE, related_name='events')
    message_id = models.CharField(max_length=255, null=True, blank=True)
    label = models.TextField(null=True)
    value = models.TextField(null=True)
    selector = models.TextField(null=True)
    type = models.CharField(max_length=255, null=True)
    timestamp = models.DateTimeField(null=True, blank=True)  # Use DateTimeField
    host = models.CharField(max_length=255, null=True, blank=True)
    path = models.CharField(max_length=255, null=True, blank=True)
    query = models.TextField(null=True, blank=True)  # Use TextField for potentially long queries
    referrer = models.URLField(null=True, blank=True)  # Use URLField
    base_referrer = models.URLField(null=True, blank=True)  # Use URLField
    dom_building_time = models.DurationField(null=True, blank=True)
    dom_content_loaded_time = models.DurationField(null=True, blank=True)
    load_time = models.DurationField(null=True, blank=True)
    first_paint_time = models.DurationField(null=True, blank=True)
    first_contentful_paint_time = models.DurationField(null=True, blank=True)
    speed_index = models.PositiveIntegerField(null=True, blank=True)  # Consider IntegerField
    visually_complete = models.PositiveIntegerField(null=True, blank=True)  # Consider IntegerField
    time_to_interactive = models.DurationField(null=True, blank=True)
    response_time = models.DurationField(null=True, blank=True)
    response_end = models.DateTimeField(null=True, blank=True)  # Use DateTimeField
    ttfb = models.DurationField(null=True, blank=True)
    value = models.TextField(null=True, blank=True)  # Use TextField for potentially long values
    duration = models.DurationField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)  # Use URLField
    label = models.CharField(max_length=255, null=True, blank=True)
    selector = models.TextField(null=True, blank=True)  # Use TextField
    hesitation = models.DurationField(null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Event: {self.label} (Session: {self.session_id})"
# Id INTEGER,
# sessionId VARCHAR(255),
# messageId  VARCHAR(255) ,
# timestamp VARCHAR(255) ,
# host VARCHAR(255),
# path VARCHAR(255),
# query VARCHAR(255),
# referrer VARCHAR(255),
# baseReferrer VARCHAR(255),
# domBuildingTime VARCHAR(255),
# domContentLoadedTime VARCHAR(255),
# loadTime VARCHAR(255),
# firstPaintTime VARCHAR(255),
# firstContentfulPaintTime VARCHAR(255),
# speedIndex VARCHAR(255),
# visuallyComplete VARCHAR(255),
# timeToInteractive VARCHAR(255),
# responseTime VARCHAR(255),
# responseEnd VARCHAR(255),
# ttfb VARCHAR(255),
# value LONGTEXT,
# duration VARCHAR(255),
# url VARCHAR(255),
# label VARCHAR(255),
# selector LONGTEXT,
# hesitation VARCHAR(255),
# type VARCHAR(255),