import inspect
from django.http import HttpRequest, HttpResponse
import django.shortcuts

class SpeedStatisticsViewWrapper:
    def __init__(self, scope: str = None, stats_cache_keys: list = None, template_name: str = None) -> None:
        self._speed_statistics = SpeedStatistics(scope)
        self._stats_cache_keys = stats_cache_keys
        self._template_name = template_name

    def __call__(self, func: Callable) -> None:
        func_signature = inspect.signature(func)
        params = list(func_signature.parameters.values())

        if not params:
            raise TypeError(f"{func.__name__} has no parameters; expected request as first arg")

        first_param = params[0].name
        if first_param not in ("request", "http_request"):
            raise TypeError(
                f"SpeedStatisticsViewWrapper expected first parameter to be 'request' or 'http_request', got '{first_param}'"
            )

        if not self._speed_statistics.get_scope():
            self._speed_statistics.set_scope(func.__name__)

        @wraps(func)
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:

            if not isinstance(request, HttpRequest):
                raise TypeError(f"Expected HttpRequest, got {type(request).__name__}")

            request.speed_statistics = self._speed_statistics

            if self._stats_cache_keys:
                while self._stats_cache_keys:
                    self._speed_statistics.retrieve_merge_stats(self._stats_cache_keys.pop())

            original_render = django.shortcuts.render
            def instrumented_render(request: HttpRequest, *r_args, **r_kwargs) -> HttpResponse:
                return self._speed_statistics.stats_render(request, *r_args, **r_kwargs)

            django.shortcuts.render = instrumented_render

            try:
                return func(request, *args, **kwargs)
            finally:
                django.shortcuts.render = original_render

        return wrapper