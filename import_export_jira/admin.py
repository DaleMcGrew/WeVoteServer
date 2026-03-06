# import_export_jira/admin.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.contrib import admin
from .models import JiraApiCounter


@admin.register(JiraApiCounter)
class JiraApiCounterAdmin(admin.ModelAdmin):
    list_display = ('datetime_of_action', 'kind_of_action')
    list_filter = ('kind_of_action', 'datetime_of_action')
    search_fields = ('kind_of_action',)
    readonly_fields = ('datetime_of_action',)
    ordering = ('-datetime_of_action',)
