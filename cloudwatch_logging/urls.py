# urls.py
from django.urls import re_path
from .views_admin import cloudwatch_log_form_view

urlpatterns = [
    re_path(r'^$', cloudwatch_log_form_view, name='cloudwatch_log_form', ),
]
