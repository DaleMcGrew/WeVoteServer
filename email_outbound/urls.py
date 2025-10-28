# email_outbound/urls.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from . import views_admin
from django.urls import re_path

urlpatterns = [
    re_path(r'^$', views_admin.email_campaign_list_view, name='email_campaign_list', ),
    re_path(r'^edit_campaign/$', views_admin.email_campaign_edit_view, name='email_campaign_edit'),
    re_path(r'^edit_campaign_process/$', views_admin.email_campaign_edit_process_view,
            name='email_campaign_edit_process'),
    re_path(r'^edit_template/$', views_admin.email_template_edit_view, name='email_template_edit'),
    re_path(r'^edit_template_process/$', views_admin.email_template_edit_process_view,
            name='email_template_edit_process'),
    re_path(r'^edit_template_folder/$', views_admin.email_template_folder_edit_view, name='email_template_folder_edit'),
    re_path(r'^edit_template_folder_process/$', views_admin.email_template_folder_edit_process_view,
            name='email_template_folder_edit_process'),
    re_path(r'^email_template_list/$', views_admin.email_template_list_view, name='email_template_list'),
    re_path(r'^email_template_list_process/$', views_admin.email_template_list_process_view,
            name='email_template_list_process'),
]
