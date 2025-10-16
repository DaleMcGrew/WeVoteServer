# email_outbound/urls.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from . import views_admin
from django.urls import re_path

urlpatterns = [
    re_path(r'^$', views_admin.email_campaign_list_view, name='email_campaign_list', ),
    re_path(r'^edit_template/$', views_admin.email_template_edit_view, name='email_template_edit'),
]
