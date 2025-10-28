# wevote_functions/templatetags/performance_tags.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django import template

register = template.Library()

@register.filter
def performance_total(performance_dict):
    total = 0
    for time in performance_dict:
        time_diff = time.get('time_difference') if isinstance(time, dict) else getattr(time, 'time_difference', 0)
        if time_diff:
            total += time_diff
    return total
