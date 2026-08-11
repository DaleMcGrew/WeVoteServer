# email_outbound/urls.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from . import views_admin
from django.urls import re_path

urlpatterns = [
    re_path(r'^$', views_admin.email_campaign_list_view, name='email_campaign_list', ),
    re_path(r'^audience_builder_drawer_html/$', views_admin.audience_builder_drawer_html_view,
            name='audience_builder_drawer_html'),
    re_path(r'^audience_builder_drawer_preview_html/$', views_admin.audience_builder_drawer_preview_html_view,
            name='audience_builder_drawer_preview_html'),
    re_path(r'^audience_builder_edit/$', views_admin.audience_builder_edit_view, name='audience_builder_edit'),
    re_path(r'^audience_builder_edit_process/$', views_admin.audience_builder_edit_process_view,
            name='audience_builder_edit_process'),
    re_path(r'^audience_builder_list/$', views_admin.audience_builder_list_view, name='audience_builder_list'),
    re_path(r'^audience_builder_list_process/$', views_admin.audience_builder_list_process_view,
            name='audience_builder_list_process'),
    re_path(r'^campaign_analytics/$', views_admin.email_campaign_analytics_view,
            name='email_campaign_analytics'),
    re_path(r'^edit_campaign/$', views_admin.email_campaign_edit_view, name='email_campaign_edit'),
    re_path(r'^audience_builder_recipient_count/$', views_admin.audience_builder_recipient_count_view,
            name='audience_builder_recipient_count'),
    re_path(r'^edit_campaign_process/$', views_admin.email_campaign_edit_process_view,
            name='email_campaign_edit_process'),
    re_path(r'^edit_template/$', views_admin.email_template_edit_view, name='email_template_edit'),
    re_path(r'^email_recipient_list/$', views_admin.email_recipient_list_view, name='email_recipient_list'),
    re_path(r'^edit_template_process/$', views_admin.email_template_edit_process_view,
            name='email_template_edit_process'),
    re_path(r'^email/attachments/upload/$', views_admin.attachment_upload_view,
            name=   'email_attachment_upload'),
    re_path(r'^attachments/(?P<attachment_id>\d+)/delete/$', views_admin.attachment_delete_view,
            name='email_attachment_delete'),
    re_path(r'^attachments/(?P<attachment_id>\d+)/download/$', views_admin.attachment_download_view,
            name='email_attachment_download'),
    re_path(r'^attachments/(?P<template_id>[\w-]+)/(?P<campaign_id>[\w-]+)/(?P<draft_uuid>[\w-]+)/$', views_admin.copy_attachments_to_campaign,
            name='copy_attachments_to_campaign'),
    re_path(r'^attachments/image/upload/$', views_admin.attachment_image_upload_view, name='email_attachment_image_upload'),
    re_path(r'^attachments/render/(?P<attachment_id>\d+)/$', views_admin.attachment_render_view, name='email_attachment_render'),
    re_path(r'^email_template_list/$', views_admin.email_template_list_view, name='email_template_list'),
    re_path(r'^email_template_list_process/$', views_admin.email_template_list_process_view,
            name='email_template_list_process'),
    re_path(r'^template_content/$', views_admin.email_template_content_view, name='email_template_content'),
    re_path(r'^view_recipient_email/(?P<email_recipient_id>[0-9]+)/$',
            views_admin.email_recipient_view, name='view_recipient_email'),
    re_path(r'^view_recipient_email_html/(?P<email_recipient_id>[0-9]+)/$',
            views_admin.email_recipient_view_html_view, name='view_recipient_email_html'),
]
