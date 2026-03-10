# import_export_jira/models.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.db import models
from wevote_functions.functions import convert_to_int


class JiraApiCounterManager(models.Manager):
    """
    Manager for JiraApiCounter model to track JIRA API calls.
    """
    def create_counter_entry(self, kind_of_action):
        """
        Create an entry that records that a call to the Jira API was made.

        Args:
            kind_of_action: String describing the type of JIRA API call made

        Returns:
            dict with 'success' (bool) and 'status' (str) keys
        """
        try:
            self.create(kind_of_action=kind_of_action)
            success = True
            status = 'ENTRY_SAVED'
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create JiraApiCounter entry: {e}")
            success = False
            status = 'SOME_ERROR'

        results = {
            'success': success,
            'status': status,
        }
        return results


class JiraApiCounter(models.Model):
    """
    Model to track and log all JIRA API calls made by the application.
    """
    datetime_of_action = models.DateTimeField(verbose_name='date and time of action', null=False, auto_now=True)
    kind_of_action = models.CharField(verbose_name="kind of call to jira", max_length=50, null=True, blank=True)

    objects = JiraApiCounterManager()

    class Meta:
        db_table = 'jira_api_counter'
        verbose_name = 'JIRA API Counter'
        verbose_name_plural = 'JIRA API Counters'

    def __str__(self):
        return f"{self.kind_of_action} at {self.datetime_of_action}"
