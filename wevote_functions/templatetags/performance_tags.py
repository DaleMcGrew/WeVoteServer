# wevote_functions/templatetags/performance_tags.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django import template
from wevote_functions.functions import get_performance_total

register = template.Library()

@register.filter
def performance_total(performance_dict):
    return get_performance_total(performance_dict)