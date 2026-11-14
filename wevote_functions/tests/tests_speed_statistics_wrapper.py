# wevote_functions/tests/test_speed_statistics_wrapper.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import django.shortcuts
from unittest.mock import MagicMock, patch, call

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, TestCase

from wevote_functions.speed_statistics.wrapper import SpeedStatisticsViewWrapper

import wevote_functions.tests.tests_speed_statistics_wrapper as wrapper_test_module

render = django.shortcuts.render


class TestSpeedStatisticsViewWrapper(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get("/")
        self.scope = "test_scope"
        self.cache_key = "cache_key_1"
        self.other_cache_key = "cache_key_2"
        wrapper_test_module.render = django.shortcuts.render

    def tearDown(self):
        wrapper_test_module.render = django.shortcuts.render

    def _make_mock_speed_statistics(self):
        mock_instance = MagicMock()
        mock_instance.retrieve_merge_stats = MagicMock()
        return mock_instance

    #########################################################
    # test __init__
    #########################################################
    def test_init_stores_default_scope_and_cache_keys(self):
        wrapper = SpeedStatisticsViewWrapper(
            scope=self.scope,
            stats_cache_keys=[self.cache_key],
        )

        self.assertEqual(wrapper._default_scope, self.scope, "Scope Should Be Stored")
        self.assertEqual(
            wrapper._default_stats_cache_keys,
            [self.cache_key],
            "Cache Keys Should Be Stored",
        )

    def test_init_defaults_are_none(self):
        wrapper = SpeedStatisticsViewWrapper()

        self.assertIsNone(wrapper._default_scope, "Default Scope Should Be None")
        self.assertIsNone(wrapper._default_stats_cache_keys, "Default Cache Keys Should Be None")

    #########################################################
    # test __call__ signature validation
    #########################################################
    def test_call_raises_error_when_view_has_no_parameters(self):
        def bare_view():
            return HttpResponse(b"ok")

        with self.assertRaisesMessage(
            TypeError,
            "bare_view has no parameters; expected request as first arg",
        ):
            SpeedStatisticsViewWrapper()(bare_view)

    def test_call_raises_error_when_first_parameter_is_not_request(self):
        def bad_view(req):
            return HttpResponse(b"ok")

        with self.assertRaisesMessage(
            TypeError,
            "SpeedStatisticsViewWrapper expected first parameter to be 'request' or 'http_request', got 'req'",
        ):
            SpeedStatisticsViewWrapper()(bad_view)

    def test_call_accepts_request_as_first_parameter(self):
        def ok_view(request):
            return HttpResponse(b"ok")

        self.assertTrue(callable(SpeedStatisticsViewWrapper()(ok_view)))

    def test_call_accepts_http_request_as_first_parameter(self):
        def ok_view(http_request):
            return HttpResponse(b"ok")

        self.assertTrue(callable(SpeedStatisticsViewWrapper()(ok_view)))

    #########################################################
    # test wrapper request validation
    #########################################################
    def test_wrapper_raises_error_when_request_is_not_httprequest(self):
        def ok_view(request):
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper()(ok_view)

        with self.assertRaisesMessage(TypeError, "Expected HttpRequest, got str"):
            wrapped("not-a-request")

    #########################################################
    # test SpeedStatistics construction / attachment / scope
    #########################################################
    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_constructs_speed_statistics_with_explicit_scope(self, mock_speed_statistics_cls):
        mock_instance = self._make_mock_speed_statistics()
        mock_speed_statistics_cls.return_value = mock_instance
        seen = {}

        def ok_view(request):
            seen["speed_statistics"] = request.speed_statistics
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(ok_view)
        wrapped(self.request)

        mock_speed_statistics_cls.assert_called_once_with(self.scope)
        self.assertIs(seen["speed_statistics"], mock_instance, "Request Should Get Constructed SpeedStatistics")

    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_uses_function_name_as_scope_when_none_provided(self, mock_speed_statistics_cls):
        mock_speed_statistics_cls.return_value = self._make_mock_speed_statistics()

        def my_named_view(request):
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper()(my_named_view)
        wrapped(self.request)

        mock_speed_statistics_cls.assert_called_once_with("my_named_view")

    #########################################################
    # test retrieve_merge_stats calls
    #########################################################
    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_calls_retrieve_merge_stats_for_each_cache_key(self, mock_speed_statistics_cls):
        mock_instance = self._make_mock_speed_statistics()
        mock_speed_statistics_cls.return_value = mock_instance

        def ok_view(request):
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper(
            scope=self.scope,
            stats_cache_keys=[self.cache_key, self.other_cache_key],
        )(ok_view)
        wrapped(self.request)

        # list.pop() is LIFO, so last key is retrieved first
        self.assertEqual(
            mock_instance.retrieve_merge_stats.call_args_list,
            [call(self.other_cache_key), call(self.cache_key)],
            "retrieve_merge_stats Should Be Called For Each Cache Key",
        )

    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_skips_retrieve_merge_stats_when_no_cache_keys(self, mock_speed_statistics_cls):
        mock_instance = self._make_mock_speed_statistics()
        mock_speed_statistics_cls.return_value = mock_instance

        def ok_view(request):
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(ok_view)
        wrapped(self.request)

        mock_instance.retrieve_merge_stats.assert_not_called()

    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_does_not_mutate_default_cache_keys_list(self, mock_speed_statistics_cls):
        mock_speed_statistics_cls.return_value = self._make_mock_speed_statistics()
        cache_keys = [self.cache_key]

        def ok_view(request):
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper(
            scope=self.scope,
            stats_cache_keys=cache_keys,
        )(ok_view)
        wrapped(self.request)

        self.assertEqual(cache_keys, [self.cache_key], "Default Cache Key List Should Not Be Mutated")

    #########################################################
    # test render patching / restore
    #########################################################
    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_patches_and_restores_django_shortcuts_render(self, mock_speed_statistics_cls):
        mock_speed_statistics_cls.return_value = self._make_mock_speed_statistics()
        original_render = django.shortcuts.render
        seen = {}

        def ok_view(request):
            seen["during"] = django.shortcuts.render
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(ok_view)
        wrapped(self.request)

        self.assertIsNot(seen["during"], original_render, "django.shortcuts.render Should Be Patched During View")
        self.assertIs(django.shortcuts.render, original_render, "django.shortcuts.render Should Be Restored After View")

    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_patches_and_restores_module_level_render_alias(self, mock_speed_statistics_cls):
        mock_speed_statistics_cls.return_value = self._make_mock_speed_statistics()
        original_module_render = wrapper_test_module.render
        seen = {}

        def ok_view(request):
            seen["during"] = wrapper_test_module.render
            return HttpResponse(b"ok")

        ok_view.__module__ = wrapper_test_module.__name__
        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(ok_view)
        wrapped(self.request)

        self.assertIsNot(seen["during"], original_module_render, "Module Render Alias Should Be Patched During View")
        self.assertIs(wrapper_test_module.render, original_module_render, "Module Render Alias Should Be Restored After View")

    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_restores_render_even_when_view_raises(self, mock_speed_statistics_cls):
        mock_speed_statistics_cls.return_value = self._make_mock_speed_statistics()
        original_render = django.shortcuts.render
        original_module_render = wrapper_test_module.render

        def boom_view(request):
            raise RuntimeError("view failed")

        boom_view.__module__ = wrapper_test_module.__name__
        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(boom_view)

        with self.assertRaisesMessage(RuntimeError, "view failed"):
            wrapped(self.request)

        self.assertIs(django.shortcuts.render, original_render, "django.shortcuts.render Should Be Restored After Error")
        self.assertIs(wrapper_test_module.render, original_module_render, "Module Render Alias Should Be Restored After Error")

    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_returns_view_response(self, mock_speed_statistics_cls):
        mock_speed_statistics_cls.return_value = self._make_mock_speed_statistics()
        expected = HttpResponse(b"view-body")

        def ok_view(request):
            return expected

        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(ok_view)
        response = wrapped(self.request)

        self.assertIs(response, expected, "Wrapper Should Return View Response")

    #########################################################
    # test instrumented render -> stats_render
    #########################################################
    @patch("wevote_functions.speed_statistics.wrapper.SpeedStatistics")
    def test_wrapper_instrumented_render_calls_stats_render(self, mock_speed_statistics_cls):
        mock_instance = self._make_mock_speed_statistics()
        mock_speed_statistics_cls.return_value = mock_instance
        fake_response = HttpResponse(b"<html></html>")
        template = "test_template.html"
        context = {"k": "v"}

        def ok_view(request):
            return django.shortcuts.render(request, template, context=context)

        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(ok_view)

        with patch.object(
            mock_speed_statistics_cls,
            "stats_render",
            return_value=fake_response,
        ) as mock_stats_render:
            response = wrapped(self.request)

        self.assertIs(response, fake_response, "Instrumented Render Should Return stats_render Response")
        mock_stats_render.assert_called_once_with(
            mock_instance, self.request, template, context=context
        )

    #########################################################
    # test wraps metadata
    #########################################################
    def test_wrapper_preserves_wrapped_function_metadata(self):
        def documented_view(request):
            """Original docstring."""
            return HttpResponse(b"ok")

        wrapped = SpeedStatisticsViewWrapper(scope=self.scope)(documented_view)

        self.assertEqual(wrapped.__name__, "documented_view")
        self.assertEqual(wrapped.__doc__, "Original docstring.")