import inspect
from django.http import HttpRequest, HttpResponse
import django.shortcuts
from typing import Callable
from wevote_functions.speed_statistics.statistics import SpeedStatistics
from functools import wraps
import sys

class SpeedStatisticsViewWrapper:
    def __init__(self, scope: str = None, stats_cache_keys: list = None) -> None:
        self._default_scope = scope
        self._default_stats_cache_keys = stats_cache_keys

    def __call__(self, func: Callable) -> Callable:
        func_signature = inspect.signature(func)
        params = list(func_signature.parameters.values())

        if not params:
            raise TypeError(f"{func.__name__} has no parameters; expected request as first arg")

        first_param = params[0].name
        if first_param not in ("request", "http_request"):
            raise TypeError(
                f"SpeedStatisticsViewWrapper expected first parameter to be 'request' or 'http_request', got '{first_param}'"
            )

        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:

            if not isinstance(request, HttpRequest):
                raise TypeError(f"Expected HttpRequest, got {type(request).__name__}")

            scope = self._default_scope or func.__name__
            stats_cache_keys = list(self._default_stats_cache_keys or [])

            speed_statistics = SpeedStatistics(scope)

            request.speed_statistics = speed_statistics

            while stats_cache_keys:
                speed_statistics.retrieve_merge_stats(stats_cache_keys.pop())

            def instrumented_render(request: HttpRequest, *r_args, **r_kwargs) -> HttpResponse:
                return SpeedStatistics.stats_render(speed_statistics, request, *r_args, **r_kwargs)

            view_module = sys.modules[func.__module__]
            originals = {}
            for name, value in list(view_module.__dict__.items()):
                if value is django.shortcuts.render:
                    originals[name] = value
                    view_module.__dict__[name] = instrumented_render

            original_django_render = django.shortcuts.render
            django.shortcuts.render = instrumented_render

            try:
                return func(request, *args, **kwargs)
            finally:
                django.shortcuts.render = original_django_render
                view_module.__dict__.update(originals)

        return wrapper