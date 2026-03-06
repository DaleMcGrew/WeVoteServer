# import_export_jira/urls.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.urls import re_path
from . import views_admin

urlpatterns = [
    re_path(r'^import_jira_elections/$', views_admin.jira_import_view, name='jira_import_elections'),
]
