# wevote_functions/tests/test_speed_statistics.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import copy
from collections import defaultdict
from unittest.mock import patch

from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from wevote_functions.speed_statistics.statistics import SpeedStatistics

LOC_MEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "speed_statistics_tests",
    }
}


class TestSpeedStatistics(SimpleTestCase):
    def setUp(self):
        self.speed_stats = SpeedStatistics(self.scope)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scope = "test_scope"
        cls.other_scope = "other_scope"
        cls.context = "test_context"
        cls.description = "Test description"
        cls.start_time = 100.0
        cls.end_time = 105.5

    def _make_snapshot(self, context=None, description=None, start_time=None, end_time=None):
        if context is None:
            context = self.context
        if description is None:
            description = self.description
        if start_time is None:
            start_time = self.start_time
        return {
            "context": context,
            "description": description,
            "start_time": start_time,
            "end_time": end_time,
            "time_difference": end_time - start_time if end_time is not None and start_time is not None else None,
        }

    def _stats_render_time_side_effect(self, render_start=None, render_end=None, display_time=999.0):
        if render_start is None:
            render_start = self.start_time
        if render_end is None:
            render_end = self.end_time
        return [display_time, render_start, render_end]

    #########################################################
    # test __init__
    #########################################################
    def test_init_empty_scope_raises_error(self):
        with self.assertRaisesMessage(ValueError, "Scope cannot be an empty string"):
            SpeedStatistics("")

    def test_init_creates_object_with_passed_scope(self):
        speed_stats = SpeedStatistics(self.scope)

        self.assertEqual(speed_stats.get_scope(), self.scope, "Scope Should Be Set From Constructor")
        self.assertIn(self.scope, speed_stats.get_stats(), "Scope Should Exist in Stats Dict")

    #########################################################
    # test get_stats_view_display
    #########################################################
    def test_get_stats_view_display_returns_sorted_scope_items(self):
        ctx_a_start = 100.0
        ctx_a_end = 105.5
        ctx_b_start = 200.0
        ctx_b_end = 205.0

        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[ctx_b_start, ctx_b_end, ctx_a_start, ctx_a_end, 999.0],
        ):
            self.speed_stats.start("ctx_b", "Second", self.scope)
            self.speed_stats.end("ctx_b", self.scope)
            self.speed_stats.start("ctx_a", "First", self.scope)
            self.speed_stats.end("ctx_a", self.scope)
            display = self.speed_stats.get_stats_view_display()

        expected_display = {
            self.scope: [
                self._make_snapshot(
                    context="ctx_a",
                    description="First",
                    start_time=ctx_a_start,
                    end_time=ctx_a_end,
                ),
                self._make_snapshot(
                    context="ctx_b",
                    description="Second",
                    start_time=ctx_b_start,
                    end_time=ctx_b_end,
                ),
            ]
        }

        self.assertEqual(display, expected_display, "Display Should Match Expected Sorted Snapshots")

    def test_get_stats_view_display_empty_object_does_not_error(self):
        empty_stats = SpeedStatistics("empty_scope")

        display = empty_stats.get_stats_view_display()

        self.assertEqual(display, {'empty_scope': []}, "Empty Stats Should Return Empty Display Dict")

    def test_get_stats_view_display_fills_open_timestamps_with_current_time(self):
        display_time = 150.0

        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, display_time],
        ):
            self.speed_stats.start(self.context, self.description, self.scope)
            display = self.speed_stats.get_stats_view_display()

        self.assertEqual(
            display[self.scope][0]["end_time"],
            display_time,
            "Open Snapshot End Time Should Be Filled for Display",
        )
        self.assertIsNone(
            self.speed_stats._speed_stats[self.scope][self.context][0]["end_time"],
            "Internal Open Snapshot Should Remain Unclosed",
        )

    def test_get_stats_view_display_sorts_scopes_by_first_snapshot_start_time(self):
        early_scope = "early_scope"
        late_scope = "late_scope"
        early_start = 50.0
        early_end = 55.0
        late_start = 200.0
        late_end = 205.0

        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[late_start, late_end, early_start, early_end, 999.0],
        ):
            self.speed_stats.start("late_ctx", "Late", late_scope)
            self.speed_stats.end("late_ctx", late_scope)
            self.speed_stats.start("early_ctx", "Early", early_scope)
            self.speed_stats.end("early_ctx", early_scope)
            display = self.speed_stats.get_stats_view_display()

        self.assertEqual(
            list(display.keys()),
            [early_scope, late_scope, self.scope],
            "Scopes Should Be Sorted by Earliest Snapshot Start Time",
        )

    def test_get_stats_view_display_returns_deep_copy(self):
        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, self.end_time, 999.0],
        ):
            self.speed_stats.start(self.context, self.description, self.scope)
            self.speed_stats.end(self.context, self.scope)
            display = self.speed_stats.get_stats_view_display()

        display[self.scope][0]["description"] = "mutated"

        self.assertNotEqual(
            self.speed_stats._speed_stats[self.scope][self.context][0]["description"],
            "mutated",
            "Mutating Display Should Not Affect Internal State",
        )

    #########################################################
    # test get_stats
    #########################################################
    def test_get_stats_returns_internal_stats_dict(self):
        response = self.speed_stats.get_stats()

        self.assertIs(response, self.speed_stats._speed_stats, "get_stats Should Return Internal Stats Dict")

    #########################################################
    # test set_scope
    #########################################################
    def test_set_scope_changes_scope_and_creates_stats_dict(self):
        with patch.object(self.speed_stats, "_create_stats_dict") as mock_create_stats_dict:
            response = self.speed_stats.set_scope(self.other_scope)

            mock_create_stats_dict.assert_called_once_with(self.other_scope)
            self.assertEqual(response, self.other_scope, "set_scope Should Return New Scope")
            self.assertEqual(self.speed_stats.get_scope(), self.other_scope, "Scope Should Be Updated")

    def test_set_scope_empty_string_raises_error(self):
        with self.assertRaisesMessage(ValueError, "Scope cannot be an empty string"):
            self.speed_stats.set_scope("")

    #########################################################
    # test get_scope
    #########################################################
    def test_get_scope_returns_current_scope(self):
        self.assertEqual(self.speed_stats.get_scope(), self.scope, "get_scope Should Return Current Scope")

    #########################################################
    # test start
    #########################################################
    def test_start_uses_object_scope_when_none_passed(self):
        with patch.object(self.speed_stats, "_create_stats_dict") as mock_create_stats_dict, \
             patch.object(self.speed_stats, "_append_stats_snapshot") as mock_append_stats_snapshot, \
             patch("wevote_functions.speed_statistics.statistics.time", return_value=self.start_time):

            self.speed_stats.start(self.context, self.description)

            mock_create_stats_dict.assert_called_once_with(self.scope)
            mock_append_stats_snapshot.assert_called_once_with(
                self.scope, self.context, self.description, self.start_time)

    def test_start_creates_snapshot_in_explicit_scope(self):
        with patch("wevote_functions.speed_statistics.statistics.time", return_value=self.start_time):
            self.speed_stats.start(self.context, self.description, self.other_scope)

        self.assertIn(self.other_scope, self.speed_stats.get_stats(), "Explicit Scope Should Be Created")
        stats = self.speed_stats.get_context_stats(self.context, self.other_scope)

        self.assertEqual(len(stats), 1, "Start Should Append Snapshot to Explicit Scope")
        self.assertEqual(stats[0]["start_time"], self.start_time, "Start Time Should Be Set in Explicit Scope")

    def test_start_raises_error_when_open_timestamp_exists(self):
        self.speed_stats.start(self.context, self.description, self.scope)

        with self.assertRaisesMessage(
            ValueError,
            f"Context {self.context} is currently keeping track of a start time. Use '.end' to add an end time before starting a new time."
        ):
            self.speed_stats.start(self.context, self.description, self.scope)

    def test_start_happy_path_appends_open_snapshot(self):
        with patch("wevote_functions.speed_statistics.statistics.time", return_value=self.start_time):
            self.speed_stats.start(self.context, self.description, self.scope)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 1, "Start Should Append One Snapshot")
        self.assertEqual(stats[0]["start_time"], self.start_time, "Start Time Should Be Set")
        self.assertIsNone(stats[0]["end_time"], "End Time Should Be None on Start")

    def test_start_after_end_appends_second_snapshot(self):
        second_start = 200.0

        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, self.end_time, second_start],
        ):
            self.speed_stats.start(self.context, self.description, self.scope)
            self.speed_stats.end(self.context, self.scope)
            self.speed_stats.start(self.context, "Second run", self.scope)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 2, "Second Start Should Append Another Snapshot")
        self.assertIsNotNone(stats[0]["end_time"], "First Snapshot Should Be Closed")
        self.assertEqual(stats[1]["start_time"], second_start, "Second Snapshot Start Time Should Be Set")
        self.assertIsNone(stats[1]["end_time"], "Second Snapshot Should Be Open")

    #########################################################
    # test end
    #########################################################
    def test_end_raises_error_for_incorrect_context(self):
        with self.assertRaisesMessage(ValueError, f"Context missing does not exist in scope {self.scope}"):
            self.speed_stats.end("missing", self.scope)

    def test_end_raises_error_when_no_timestamps(self):
        self.speed_stats._speed_stats[self.scope][self.context] = []

        with self.assertRaisesMessage(
            ValueError,
            f"Context {self.context} has no start times in scope {self.scope}. Use '.start' instead to add one."
        ):
            self.speed_stats.end(self.context, self.scope)

    def test_end_raises_error_when_timestamp_already_closed(self):
        self.speed_stats._speed_stats[self.scope][self.context] = [
            self._make_snapshot(end_time=self.end_time)
        ]

        with self.assertRaisesMessage(
            ValueError,
            f"Context {self.context} already has an end time in scope {self.scope}. Use '.update_end' instead."
        ):
            self.speed_stats.end(self.context, self.scope)

    def test_end_appends_closed_snapshot(self):
        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, self.end_time],
        ):
            self.speed_stats.start(self.context, self.description, self.scope)
            self.speed_stats.end(self.context, self.scope)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 1, "End Should Leave One Closed Snapshot")
        self.assertEqual(stats[0]["start_time"], self.start_time, "Start Time Should Be Set")
        self.assertEqual(stats[0]["end_time"], self.end_time, "End Time Should Be Set")
        self.assertEqual(
            stats[0]["time_difference"],
            self.end_time - self.start_time,
            "Time Difference Should Be Calculated",
        )

    def test_end_uses_object_scope_when_none_passed(self):
        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, self.end_time],
        ):
            self.speed_stats.start(self.context, self.description)
            self.speed_stats.end(self.context)

        stats = self.speed_stats.get_context_stats(self.context)

        self.assertEqual(len(stats), 1, "End Should Work With Default Scope")
        self.assertEqual(stats[0]["end_time"], self.end_time, "End Time Should Be Set With Default Scope")

    #########################################################
    # test update_end
    #########################################################
    def test_update_end_raises_error_for_incorrect_context(self):
        with self.assertRaisesMessage(ValueError, f"Context missing does not exist in scope {self.scope}"):
            self.speed_stats.update_end("missing", self.scope)

    def test_update_end_raises_error_when_no_timestamps(self):
        self.speed_stats._speed_stats[self.scope][self.context] = []

        with self.assertRaisesMessage(
            ValueError,
            f"Context {self.context} has no start times in scope {self.scope}. Use '.start' instead to add one."
        ):
            self.speed_stats.update_end(self.context, self.scope)

    def test_update_end_appends_closed_snapshot(self):
        self.speed_stats._speed_stats[self.scope][self.context] = [
            self._make_snapshot(end_time=101.0)
        ]

        with patch("wevote_functions.speed_statistics.statistics.time", return_value=self.end_time):
            self.speed_stats.update_end(self.context, self.scope)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 1, "update_end Should Leave One Snapshot")
        self.assertEqual(stats[0]["start_time"], self.start_time, "update_end Should Preserve Start Time")
        self.assertEqual(stats[0]["end_time"], self.end_time, "update_end Should Replace End Time")
        self.assertEqual(
            stats[0]["time_difference"],
            self.end_time - self.start_time,
            "Time Difference Should Be Calculated",
        )

    def test_update_end_closes_open_snapshot(self):
        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, self.end_time],
        ):
            self.speed_stats.start(self.context, self.description, self.scope)
            self.speed_stats.update_end(self.context, self.scope)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 1, "update_end Should Leave One Snapshot")
        self.assertEqual(stats[0]["start_time"], self.start_time, "update_end Should Preserve Start Time")
        self.assertEqual(stats[0]["end_time"], self.end_time, "update_end Should Set End Time on Open Snapshot")
        self.assertEqual(
            stats[0]["time_difference"],
            self.end_time - self.start_time,
            "Time Difference Should Be Calculated for Open Snapshot",
        )

    def test_update_end_uses_object_scope_when_none_passed(self):
        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[self.start_time, self.end_time],
        ):
            self.speed_stats.start(self.context, self.description)
            self.speed_stats.update_end(self.context)

        stats = self.speed_stats.get_context_stats(self.context)

        self.assertEqual(stats[0]["end_time"], self.end_time, "update_end Should Work With Default Scope")

    #########################################################
    # test get_context_stats
    #########################################################
    def test_get_context_stats_returns_none_on_empty_context(self):
        response = self.speed_stats.get_context_stats("missing_context", self.scope)

        self.assertIsNone(response, "Missing Context Should Return None")

    def test_get_context_stats_returns_deep_copy(self):
        self.speed_stats.start(self.context, self.description, self.scope)

        response = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertIsNot(response, self.speed_stats._speed_stats[self.scope][self.context], "Should Return a Deep Copy")
        self.assertEqual(response, self.speed_stats._speed_stats[self.scope][self.context], "Copy Should Match Original")

        response[0]["description"] = "mutated"
        self.assertNotEqual(
            self.speed_stats._speed_stats[self.scope][self.context][0]["description"],
            "mutated",
            "Mutating Returned Copy Should Not Affect Internal State"
        )

    def test_get_context_stats_uses_object_scope_when_none_passed(self):
        self.speed_stats.start(self.context, self.description)

        response = self.speed_stats.get_context_stats(self.context)

        self.assertEqual(len(response), 1, "get_context_stats Should Work With Default Scope")
        self.assertEqual(response[0]["context"], self.context, "Default Scope Should Return Expected Context")

    #########################################################
    # test peek_context_stats
    #########################################################
    def test_peek_context_stats_returns_none_on_no_context_stats(self):
        response = self.speed_stats.peek_context_stats("missing_context", self.scope)

        self.assertIsNone(response, "Missing Context Should Return None")

    def test_peek_context_stats_returns_deep_copy_of_last_stat(self):
        first_snapshot = self._make_snapshot(start_time=90.0, end_time=95.0)
        second_snapshot = self._make_snapshot(start_time=100.0, end_time=None)
        self.speed_stats._speed_stats[self.scope][self.context] = [first_snapshot, second_snapshot]

        response = self.speed_stats.peek_context_stats(self.context, self.scope)

        self.assertEqual(response, second_snapshot, "peek_context_stats Should Return Last Snapshot")
        self.assertIsNot(response, second_snapshot, "peek_context_stats Should Return a Deep Copy")

    def test_peek_context_stats_uses_object_scope_when_none_passed(self):
        self.speed_stats.start(self.context, self.description)

        response = self.speed_stats.peek_context_stats(self.context)

        self.assertEqual(response["context"], self.context, "peek_context_stats Should Work With Default Scope")

    #########################################################
    # test pop_context_stats
    #########################################################
    def test_pop_context_stats_returns_none_when_context_not_in_speed_stats(self):
        response = self.speed_stats.pop_context_stats("missing_context", self.scope)

        self.assertIsNone(response, "Missing Context Should Return None")

    def test_pop_context_stats_returns_empty_list_when_context_exists_but_empty(self):
        self.speed_stats._speed_stats[self.scope][self.context] = []

        response = self.speed_stats.pop_context_stats(self.context, self.scope)

        self.assertEqual(response, [], "Empty Context List Should Return Empty List")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Key Should Be Removed")

    def test_pop_context_stats_returns_all_snapshots_and_removes_context(self):
        first_snapshot = self._make_snapshot(start_time=90.0, end_time=95.0)
        second_snapshot = self._make_snapshot(start_time=100.0, end_time=105.0)
        self.speed_stats._speed_stats[self.scope][self.context] = [first_snapshot, second_snapshot]

        response = self.speed_stats.pop_context_stats(self.context, self.scope)

        self.assertEqual(response, [first_snapshot, second_snapshot], "pop_context_stats Should Return All Snapshots")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Key Should Be Removed")

    def test_pop_context_stats_happy_path(self):
        self.speed_stats.start(self.context, self.description, self.scope)

        response = self.speed_stats.pop_context_stats(self.context, self.scope)

        self.assertEqual(len(response), 1, "pop_context_stats Should Return One Snapshot on Happy Path")
        self.assertEqual(response[0]["context"], self.context, "Returned Snapshot Should Match Context")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Should Be Removed After Pop")

    def test_pop_context_stats_uses_object_scope_when_none_passed(self):
        self.speed_stats.start(self.context, self.description)

        response = self.speed_stats.pop_context_stats(self.context)

        self.assertEqual(len(response), 1, "pop_context_stats Should Work With Default Scope")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Should Be Removed After Pop")

    #########################################################
    # test pop_context_stat
    #########################################################
    def test_pop_context_stat_returns_none_when_context_not_in_speed_stats(self):
        response = self.speed_stats.pop_context_stat("missing_context", self.scope)

        self.assertIsNone(response, "Missing Context Should Return None")

    def test_pop_context_stat_returns_none_on_empty_speed_stats(self):
        self.speed_stats._speed_stats[self.scope][self.context] = []

        response = self.speed_stats.pop_context_stat(self.context, self.scope)

        self.assertIsNone(response, "Empty Context List Should Return None")

    def test_pop_context_stat_removes_last_context_stat(self):
        first_snapshot = self._make_snapshot(start_time=90.0, end_time=95.0)
        second_snapshot = self._make_snapshot(start_time=100.0, end_time=105.0)
        self.speed_stats._speed_stats[self.scope][self.context] = [first_snapshot, second_snapshot]

        response = self.speed_stats.pop_context_stat(self.context, self.scope)

        self.assertEqual(response, second_snapshot, "pop_context_stat Should Return Last Snapshot")
        self.assertEqual(len(self.speed_stats._speed_stats[self.scope][self.context]), 1, "One Snapshot Should Remain")

    def test_pop_context_stat_removes_context_when_last_item_removed(self):
        self.speed_stats._speed_stats[self.scope][self.context] = [self._make_snapshot(end_time=self.end_time)]

        response = self.speed_stats.pop_context_stat(self.context, self.scope)

        self.assertEqual(response["context"], self.context, "pop_context_stat Should Return Removed Snapshot")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Key Should Be Removed When Empty")

    def test_pop_context_stat_happy_path(self):
        self.speed_stats.start(self.context, self.description, self.scope)

        response = self.speed_stats.pop_context_stat(self.context, self.scope)

        self.assertIsNotNone(response, "pop_context_stat Should Return Snapshot on Happy Path")
        self.assertEqual(response["context"], self.context, "Returned Snapshot Should Match Context")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Should Be Removed After Last Pop")

    def test_pop_context_stat_uses_object_scope_when_none_passed(self):
        self.speed_stats.start(self.context, self.description)

        response = self.speed_stats.pop_context_stat(self.context)

        self.assertEqual(response["context"], self.context, "pop_context_stat Should Work With Default Scope")
        self.assertNotIn(self.context, self.speed_stats._speed_stats[self.scope], "Context Should Be Removed After Pop")

    #########################################################
    # test merge_stats
    #########################################################
    def test_merge_stats_raises_error_for_non_speed_statistics(self):
        with self.assertRaisesMessage(ValueError, "other_stats must be a SpeedStatistics object"):
            self.speed_stats.merge_stats({"not": "speed statistics"})

    def test_merge_stats_merges_speed_statistics(self):
        other_stats = SpeedStatistics(self.other_scope)
        other_stats.start("other_context", "Other", self.other_scope)
        other_stats.end("other_context", self.other_scope)

        self.speed_stats.start(self.context, self.description, self.scope)
        self.speed_stats.end(self.context, self.scope)

        self.speed_stats.merge_stats(other_stats)

        self.assertIn(self.scope, self.speed_stats.get_stats(), "Original Scope Should Remain")
        self.assertIn(self.other_scope, self.speed_stats.get_stats(), "Incoming Scope Should Be Merged")
        self.assertEqual(len(self.speed_stats.get_stats()[self.other_scope]["other_context"]), 1, "Incoming Context Should Be Merged")

    def test_merge_stats_removes_incoming_open_timestamp_on_conflict(self):
        self.speed_stats.start(self.context, "Running on self", self.scope)

        other_stats = SpeedStatistics(self.scope)
        other_stats.start(self.context, "Incoming open", self.scope)

        self.speed_stats.merge_stats(other_stats)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 1, "Only One Snapshot Should Remain After Conflict Resolution")
        self.assertEqual(stats[0]["description"], "Running on self", "Self Open Timestamp Should Be Preserved")
        self.assertIsNone(stats[0]["end_time"], "Preserved Snapshot Should Still Be Open")

    def test_merge_stats_preserves_self_open_when_incoming_closed_only(self):
        self.speed_stats.start(self.context, "Running on self", self.scope)

        other_stats = SpeedStatistics(self.scope)
        other_stats.start(self.context, "Incoming closed", self.scope)
        other_stats.end(self.context, self.scope)

        self.speed_stats.merge_stats(other_stats)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 2, "Incoming Closed and Self Open Snapshots Should Both Remain")
        self.assertIsNotNone(stats[0]["end_time"], "Incoming Snapshot Should Be Closed")
        self.assertEqual(stats[0]["description"], "Incoming closed", "Incoming Snapshot Should Be First")
        self.assertIsNone(stats[1]["end_time"], "Self Open Snapshot Should Be Preserved")
        self.assertEqual(stats[1]["description"], "Running on self", "Self Open Snapshot Should Be Re-Appended")

    def test_merge_stats_incoming_open_lands_when_self_closed(self):
        self.speed_stats.start(self.context, "Self closed", self.scope)
        self.speed_stats.end(self.context, self.scope)

        other_stats = SpeedStatistics(self.scope)
        other_stats.start(self.context, "Incoming open", self.scope)

        self.speed_stats.merge_stats(other_stats)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 2, "Self Closed and Incoming Open Snapshots Should Both Remain")
        self.assertIsNotNone(stats[0]["end_time"], "Self Snapshot Should Be Closed")
        self.assertEqual(stats[0]["description"], "Self closed", "Self Snapshot Should Be First")
        self.assertIsNone(stats[1]["end_time"], "Incoming Snapshot Should Be Open")
        self.assertEqual(stats[1]["description"], "Incoming open", "Incoming Open Snapshot Should Be Appended")

    def test_merge_stats_concatenates_when_both_closed(self):
        self.speed_stats.start(self.context, "First", self.scope)
        self.speed_stats.end(self.context, self.scope)

        other_stats = SpeedStatistics(self.scope)
        other_stats.start(self.context, "Second", self.scope)
        other_stats.end(self.context, self.scope)

        self.speed_stats.merge_stats(other_stats)

        stats = self.speed_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(len(stats), 2, "Both Closed Snapshots Should Be Concatenated")
        self.assertEqual(stats[0]["description"], "First", "First Snapshot Should Remain First")
        self.assertEqual(stats[1]["description"], "Second", "Second Snapshot Should Be Appended")

    def test_merge_stats_deep_copy_isolates_source(self):
        other_stats = SpeedStatistics(self.scope)
        other_stats.start(self.context, "Other", self.scope)
        other_stats.end(self.context, self.scope)

        self.speed_stats.merge_stats(other_stats)

        merged = self.speed_stats.get_context_stats(self.context, self.scope)
        merged[0]["description"] = "mutated"

        source = other_stats.get_context_stats(self.context, self.scope)

        self.assertEqual(source[0]["description"], "Other", "Mutating Merged Data Should Not Affect Source")

    def test_merge_stats_resulting_shape_is_correct(self):
        other_stats = SpeedStatistics(self.other_scope)
        other_stats.start("ctx_1", "desc", self.other_scope)
        other_stats.end("ctx_1", self.other_scope)

        self.speed_stats.merge_stats(other_stats)

        merged = self.speed_stats.get_stats()

        self.assertIsInstance(merged[self.other_scope], defaultdict, "Merged Scope Should Be defaultdict")
        self.assertIsInstance(merged[self.other_scope]["ctx_1"], list, "Merged Context Should Be a List")
        self.assertEqual(
            set(merged[self.other_scope]["ctx_1"][0].keys()),
            {"context", "description", "start_time", "end_time", "time_difference"},
            "Merged Snapshot Should Have Expected Keys"
        )

    #########################################################
    # test stats_render
    #########################################################
    def test_stats_render_raises_error_when_render_returns_non_httpresponse(self):
        request = RequestFactory().get("/")
        template = "test_template.html"

        with patch(
            "wevote_functions.speed_statistics.statistics.render",
            return_value="not a response",
        ):
            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(),
            ):
                with self.assertRaisesMessage(ValueError, "Response is not a HttpResponse object"):
                    SpeedStatistics.stats_render(
                        self.speed_stats, request, template, context={}
                    )

    def test_stats_render_uses_context_from_kwargs(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        context = {"existing_key": "existing_value"}

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(b"<html></html>")

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(),
            ):
                response = SpeedStatistics.stats_render(
                    self.speed_stats, request, template, context=context
                )

            mock_render.assert_called_once_with(request, template, context=context)
            self.assertEqual(context["existing_key"], "existing_value")
            self.assertIn("speed_statistics_display", context)
            self.assertIsInstance(response, HttpResponse)

    def test_stats_render_uses_context_from_positional_args(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        context = {"from_positional": True}

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(b"<html></html>")

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(),
            ):
                SpeedStatistics.stats_render(
                    self.speed_stats, request, template, context
                )

            mock_render.assert_called_once_with(request, template, context)

    def test_stats_render_creates_context_when_not_provided(self):
        request = RequestFactory().get("/")
        template = "test_template.html"

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(b"<html></html>")

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(),
            ):
                SpeedStatistics.stats_render(self.speed_stats, request, template)

            _, call_kwargs = mock_render.call_args
            self.assertEqual(
                call_kwargs["context"],
                {"speed_statistics_display": {self.scope: []}},
                "Context Should Be Created With Speed Statistics Display",
            )

    def test_stats_render_replaces_none_context_in_kwargs(self):
        request = RequestFactory().get("/")
        template = "test_template.html"

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
              mock_render.return_value = HttpResponse(b"<html></html>")

              with patch(
                  "wevote_functions.speed_statistics.statistics.time",
                  side_effect=self._stats_render_time_side_effect(),
              ):
                  SpeedStatistics.stats_render(
                      self.speed_stats, request, template, context=None
                  )

              _, call_kwargs = mock_render.call_args
              self.assertEqual(
                  call_kwargs["context"],
                  {"speed_statistics_display": {self.scope: []}},
                  "None Context in Kwargs Should Be Replaced With Display Dict",
              )

    def test_stats_render_replaces_none_context_in_positional_args(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        extra_arg = "extra"

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(b"<html></html>")

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(),
            ):
                SpeedStatistics.stats_render(
                    self.speed_stats, request, template, None, extra_arg
                )

            mock_render.assert_called_once_with(
                request,
                template,
                {"speed_statistics_display": {self.scope: []}},
                extra_arg,
            )

    def test_stats_render_kwargs_context_takes_precedence_over_positional(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        kwargs_context = {"source": "kwargs"}
        positional_context = {"source": "positional"}

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(b"<html></html>")

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(),
            ):
                SpeedStatistics.stats_render(
                    self.speed_stats,
                    request,
                    template,
                    positional_context,
                    context=kwargs_context,
                )

            mock_render.assert_called_once_with(
                request, template, positional_context, context=kwargs_context
            )
            self.assertIn("speed_statistics_display", kwargs_context)
            self.assertNotIn("speed_statistics_display", positional_context)

    def test_stats_render_injects_speed_statistics_display(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        context = {}

        with patch(
            "wevote_functions.speed_statistics.statistics.time",
            side_effect=[
                self.start_time,
                self.end_time,
                *self._stats_render_time_side_effect(),
            ],
        ):
            self.speed_stats.start(self.context, self.description, self.scope)
            self.speed_stats.end(self.context, self.scope)

            expected_display = {
                self.scope: [
                    self._make_snapshot(
                        start_time=self.start_time,
                        end_time=self.end_time,
                    )
                ]
            }

            with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
                mock_render.return_value = HttpResponse(b"<html></html>")
                SpeedStatistics.stats_render(
                    self.speed_stats, request, template, context=context
                )

        self.assertEqual(
            context["speed_statistics_display"],
            expected_display,
            "Speed Statistics Display Should Be Injected Before Render",
        )

    def test_stats_render_records_render_scope_timing(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        render_start = 300.0
        render_end = 305.25

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(b"<html></html>")

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(render_start, render_end),
            ):
                SpeedStatistics.stats_render(
                    self.speed_stats, request, template, context={}
                )

        render_stats = self.speed_stats.get_context_stats("_render", "_render")

        self.assertEqual(len(render_stats), 1, "Render Should Record One Snapshot")
        self.assertEqual(render_stats[0]["context"], "_render")
        self.assertEqual(render_stats[0]["description"], "Render the template")
        self.assertEqual(render_stats[0]["start_time"], render_start)
        self.assertEqual(render_stats[0]["end_time"], render_end)
        self.assertEqual(render_stats[0]["time_difference"], render_end - render_start)

    def test_stats_render_appends_render_load_time_placeholder(self):
        request = RequestFactory().get("/")
        template = "test_template.html"
        render_start = 400.0
        render_end = 401.2345
        base_content = b"<html>base</html>"

        with patch("wevote_functions.speed_statistics.statistics.render") as mock_render:
            mock_render.return_value = HttpResponse(base_content)

            with patch(
                "wevote_functions.speed_statistics.statistics.time",
                side_effect=self._stats_render_time_side_effect(render_start, render_end),
            ):
                response = SpeedStatistics.stats_render(
                    self.speed_stats, request, template, context={}
                )

        expected_suffix = (
            f'<div id="renderLoadTimePlaceholder">{render_end - render_start:.4f}</div>'
        ).encode("utf-8")

        self.assertTrue(
            response.content.endswith(expected_suffix),
            "Response Should Append Render Load Time Placeholder",
        )
        self.assertTrue(
            response.content.startswith(base_content),
            "Original Response Content Should Be Preserved",
        )

    #########################################################
    # test _create_stats_dict
    #########################################################
    def test_create_stats_dict_raises_error_for_incorrect_scope(self):
        with self.assertRaisesMessage(ValueError, "Scope cannot be None"):
            self.speed_stats._create_stats_dict(None)

    def test_create_stats_dict_creates_defaultdict_for_new_scope(self):
        self.speed_stats._create_stats_dict(self.other_scope)

        self.assertIn(self.other_scope, self.speed_stats._speed_stats, "New Scope Should Be Created")
        self.assertIsInstance(self.speed_stats._speed_stats[self.other_scope], defaultdict, "New Scope Should Be defaultdict")

    def test_create_stats_dict_does_not_reset_existing_scope(self):
        self.speed_stats.start(self.context, self.description, self.scope)
        original_scope_dict = self.speed_stats._speed_stats[self.scope]

        self.speed_stats._create_stats_dict(self.scope)

        self.assertIs(
            self.speed_stats._speed_stats[self.scope],
            original_scope_dict,
            "Existing Scope Dict Should Not Be Replaced",
        )
        self.assertEqual(
            len(self.speed_stats.get_context_stats(self.context, self.scope)),
            1,
            "Existing Scope Data Should Be Preserved",
        )

    #########################################################
    # test _append_stats_snapshot
    #########################################################
    def test_append_stats_snapshot_appends_expected_snapshot(self):
        snapshot = self._make_snapshot()

        with patch.object(self.speed_stats, "_make_stats_snapshot", return_value=snapshot) as mock_make_stats_snapshot:
            self.speed_stats._append_stats_snapshot(
                self.scope, self.context, self.description, self.start_time, self.end_time)

            mock_make_stats_snapshot.assert_called_once_with(
                self.context, self.description, self.start_time, self.end_time)
            self.assertEqual(
                self.speed_stats._speed_stats[self.scope][self.context][-1],
                snapshot,
                "Appended Snapshot Should Match _make_stats_snapshot Return Value"
            )

    #########################################################
    # test _make_stats_snapshot
    #########################################################
    def test_make_stats_snapshot_calculates_time_difference(self):
        response = self.speed_stats._make_stats_snapshot(
            self.context, self.description, self.start_time, self.end_time)

        self.assertEqual(response["time_difference"], self.end_time - self.start_time, "Time Difference Should Be Calculated")

    def test_make_stats_snapshot_returns_expected_format(self):
        response = self.speed_stats._make_stats_snapshot(
            self.context, self.description, self.start_time, None)

        self.assertEqual(
            response,
            {
                "context": self.context,
                "description": self.description,
                "start_time": self.start_time,
                "end_time": None,
                "time_difference": None,
            },
            "Snapshot Should Have Expected Format"
        )

    #########################################################
    # test _get_scope
    #########################################################
    def test_get_scope_uses_default_scope_when_none_passed(self):
        response = self.speed_stats._get_scope(None)

        self.assertEqual(response, self.scope, "None Scope Should Fall Back to Object Scope")

    def test_get_scope_raises_error_when_scope_not_in_speed_stats(self):
        with self.assertRaisesMessage(ValueError, f"Scope {self.other_scope} does not exist"):
            self.speed_stats._get_scope(self.other_scope)

    def test_get_scope_returns_passed_scope(self):
        self.speed_stats.set_scope(self.other_scope)

        response = self.speed_stats._get_scope(self.other_scope)

        self.assertEqual(response, self.other_scope, "Passed Scope Should Be Returned")

@override_settings(CACHES=LOC_MEM_CACHES)
class TestSpeedStatisticsCache(SimpleTestCase):

    def setUp(self):
        self.scope = "test_scope"
        self.other_scope = "other_scope"
        self.speed_stats = SpeedStatistics(self.scope)
        self.cache_key = "speed_statistics_test_cache_key"
        cache.clear()

    def tearDown(self):
        cache.delete(self.cache_key)

    #########################################################
    # test retrieve_merge_stats
    #########################################################
    def test_retrieve_merge_stats_raises_error_for_incorrect_cache_value(self):
        cache.set(self.cache_key, {"not": "SpeedStatistics"}, timeout=300)

        with self.assertRaisesMessage(
            ValueError,
            f"Retrieved stats from cache {self.cache_key} are not a SpeedStatistics object"
        ):
            self.speed_stats.retrieve_merge_stats(self.cache_key)

    def test_retrieve_merge_stats_merges_cached_object(self):
        cached_stats = SpeedStatistics(self.other_scope)
        cached_stats.start("cached_context", "Cached", self.other_scope)
        cached_stats.end("cached_context", self.other_scope)
        cache.set(self.cache_key, cached_stats, timeout=300)

        self.speed_stats.retrieve_merge_stats(self.cache_key)

        self.assertIn(self.other_scope, self.speed_stats.get_stats(), "Cached Stats Should Be Merged")

    #########################################################
    # test pop_merge_stats
    #########################################################
    def test_pop_merge_stats_removes_cached_object(self):
        cached_stats = SpeedStatistics(self.other_scope)
        cache.set(self.cache_key, cached_stats, timeout=300)

        self.speed_stats.pop_merge_stats(self.cache_key)

        self.assertIsNone(cache.get(self.cache_key), "Cached Object Should Be Removed")
        self.assertIn(self.other_scope, self.speed_stats.get_stats(), "Cached Stats Should Still Be Merged Before Delete")

    def test_pop_merge_stats_merges_cached_stats_with_data(self):
        cached_stats = SpeedStatistics(self.other_scope)
        cached_stats.start("cached_context", "Cached", self.other_scope)
        cached_stats.end("cached_context", self.other_scope)
        cache.set(self.cache_key, cached_stats, timeout=300)

        self.speed_stats.pop_merge_stats(self.cache_key)

        self.assertIsNone(cache.get(self.cache_key), "Cached Object Should Be Removed")
        stats = self.speed_stats.get_context_stats("cached_context", self.other_scope)

        self.assertEqual(len(stats), 1, "Cached Stats With Data Should Be Merged")
        self.assertEqual(stats[0]["description"], "Cached", "Merged Cached Snapshot Should Match Source")