from time import time
from django.core.cache import cache
import copy
from collections import defaultdict
from functools import wraps
from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

class SpeedStatistics:
    """
    Represents a speed statistics object using timestamps 
    to track how long different parts of the code take to run.

    Terms:
    - Scope: A named group of context stats. An easy way to do it is Scope = Function.
    - Context: A named group of timestamp stats. An easy way to do it is Context = Code Block.
    - Timestamp: A start and end time for a given context.
    - Open/ Open ended timestamp: A context stat that has a start time but no end time.
    - Closed timestamp: A context stat that has a start time and an end time.
    - Snapshot: A timestamp stat that has a start time and an end time.

    Attributes:
        _speed_stats (dict): A dictionary of scope names to a dictionary of context names to a list of timestamp dictionaries.
        _scope (str): The default scope name.

    Methods:
        get_stats_view_display(self) -> dict: Build a template-ready view of all timing stats.
        get_stats(self) -> dict: Return the speed statistics object.
        set_scope(self, scope: str) -> str: Set the default scope name. This is what .start, .end, and .update will default to if no scope is provided.
        get_scope(self) -> str: Return the default scope name.
        start(self, context: str, description: str = None, scope: str = None) -> None: Start a new timestamp for the given context and scope.
        end(self, context: str, scope: str = None) -> None: End the last timestamp for the given context and scope.
        update_end(self, context: str, scope: str = None) -> None: Update the end time of the last timestamp for the given context and scope.
        get_context_stats(self, context: str, scope: str = None) -> dict: Return a deep copy of all the context stats for the given context and scope.
        peek_context_stats(self, context: str, scope: str = None) -> dict: Return a deep copy of the last context stat for the given context and scope.
    """

    def __init__(self, scope: str) -> None:
        if scope == "":
            raise ValueError("Scope cannot be an empty string")

        self._speed_stats = {}
        self._scope = scope

        if scope:
            self.set_scope(scope)

    def get_stats_view_display(self) -> dict:
        """
        Build a template-ready view of all timing stats.
        Returns:
            dict[str, list[dict]]: A mapping of scope name to a flat, sorted list of
            timing snapshots for that scope.
            Each scope's list is built by flattening every context's snapshots from
            the internal structure (scope -> context -> list[snapshot]) into one list.
            {
                "example_scope": [
                    {
                        "context": "ctx_a",
                        "description": "First",
                        "start_time": 100.0,
                        "end_time": 105.5,
                        "time_difference": 5.5,
                    },
                ],
                "example_scope_2": [...],
            }

        Ordering:
            - Snapshots within a scope are sorted by (start_time, end_time) ascending.
            None timestamps sort last.
            - Scopes are sorted by the start_time of their earliest snapshot.
        Notes:
            - Returns deep copies; mutating the result does not affect internal state.
            - Open timers (end_time is None internally) get a display-only end_time here;
            the underlying stats are left unchanged.
        """

        scope_items = []
        default_end_time = time()
        for scope, stats in self._speed_stats.items():
            copy_list = [
                copy.deepcopy(timestamp)
                for timestamp_list in stats.values()
                for timestamp in timestamp_list
            ]

            for stat in copy_list:
                stat["end_time"] = stat["end_time"] if stat["end_time"] is not None else default_end_time

            copy_list.sort(key=lambda x: (
                x["start_time"] if x["start_time"] is not None else float("inf"),
                x["end_time"] if x["end_time"] is not None else float("inf"),
            ))
            scope_items.append((scope, copy_list))

        scope_items.sort(key=lambda item: (
            item[1][0]["start_time"]
            if item[1] and item[1][0]["start_time"] is not None
            else float("inf")
        ))
    
        return dict(scope_items)

    def get_stats(self) -> dict:
        return self._speed_stats

    def set_scope(self, scope: str) -> str:
        """
        Set the default scope of the speed statistics.
        """
        if scope == "":
            raise ValueError("Scope cannot be an empty string")

        self._create_stats_dict(scope)
        self._scope = scope
        return self._scope

    def get_scope(self) -> str:
        return self._scope

    def start(self, context: str, description: str = None, scope: str = None) -> None:
        """
        Append a new open ended time stamp start to the context and scope.
        """
        if not scope:
            scope = self._scope

        # Create a new scope if necessary
        self._create_stats_dict(scope)

        # Make sure there isn't a current open ended timestamp (A start but no end)
        if self._speed_stats[scope][context] and self._speed_stats[scope][context][-1]["end_time"] is None:
            raise ValueError(
                f"Context {context} is currently keeping track of a start time. Use '.end' to add an end time before starting a new time."
                )
        
        self._append_stats_snapshot(scope, context, description, time())

    def end(self, context: str, scope: str = None) -> None:
        """
        Close off a time stamp with an end time.
        """
        scope = self._get_scope(scope)

        if context not in self._speed_stats[scope]:
            raise ValueError(f"Context {context} does not exist in scope {scope}")

        if not self._speed_stats[scope][context]:
            raise ValueError(f"Context {context} has no start times in scope {scope}. Use '.start' instead to add one.")

        if self._speed_stats[scope][context][-1]["end_time"] is not None:
            raise ValueError(f"Context {context} already has an end time in scope {scope}. Use '.update_end' instead.")

        # For stability, it's better to pop the last item 
        # and then append a new one with the new end time
        context_stat = self._speed_stats[scope][context].pop()
        self._append_stats_snapshot(
            scope,
            context,
            context_stat["description"],
            context_stat["start_time"],
            time()
        )

    def update_end(self, context: str, scope: str = None) -> None:
        """
        Update the end time of the last context stat for the given context and scope.
        """
        scope = self._get_scope(scope)

        if context not in self._speed_stats[scope]:
            raise ValueError(f"Context {context} does not exist in scope {scope}")

        if len(self._speed_stats[scope][context]) == 0:
            raise ValueError(f"Context {context} has no start times in scope {scope}. Use '.start' instead to add one.")

        # For stability, it's better to pop the last item 
        # and then append a new one with the new end time
        context_stat = self._speed_stats[scope][context].pop()
        self._append_stats_snapshot(
            scope,
            context,
            context_stat["description"],
            context_stat["start_time"],
            time()
        )

    def get_context_stats(self, context: str, scope: str = None) -> dict:
        """
        Return a deep copy of all the context stats for the given context and scope.
        """
        scope = self._get_scope(scope)

        if context not in self._speed_stats[scope]:
            return None

        return copy.deepcopy(self._speed_stats[scope][context])

    def peek_context_stats(self, context: str, scope: str = None) -> dict:
        scope = self._get_scope(scope)

        if context not in self._speed_stats[scope] or len(self._speed_stats[scope][context]) == 0:
            return None

        return copy.deepcopy(self._speed_stats[scope][context][-1])

    def pop_context_stats(self, context: str, scope: str = None) -> list:
        """
        Remove and return all the context stats for the given context and scope.
        """
        scope = self._get_scope(scope)

        if context not in self._speed_stats[scope]:
            return None

        return self._speed_stats[scope].pop(context, None)

    def pop_context_stat(self, context: str, scope: str = None) -> dict:
        """
        Remove and return the most recent context stat for the given context and scope.
        """
        scope = self._get_scope(scope)

        if context not in self._speed_stats[scope]:
            return None

        if not self._speed_stats[scope][context]:
            return None

        return_stat = self._speed_stats[scope][context].pop()

        if len(self._speed_stats[scope][context]) == 0:
            self._speed_stats[scope].pop(context)

        return return_stat

    def merge_stats(self, other_stats: 'SpeedStatistics') -> None:
        """
        Merge the stats of another SpeedStatistics object into the current object.
        """
        if not isinstance(other_stats, SpeedStatistics):
            raise ValueError("other_stats must be a SpeedStatistics object")

        for scope, stats in other_stats._speed_stats.items():
            if scope not in self._speed_stats:
                self._create_stats_dict(scope)

            for context, stat_list in stats.items():
                if context in self._speed_stats[scope]:
                    # If the incoming context has an open ended timestamp
                    # and the current context has an open ended timestamp
                    # then the incoming timestamp should be removed
                    running_stat = None
                    if  self._speed_stats[scope][context] and self._speed_stats[scope][context][-1]["end_time"] is None:
                        running_stat = self._speed_stats[scope][context].pop()

                    self._speed_stats[scope][context].extend(copy.deepcopy(stat_list))

                    if running_stat and self._speed_stats[scope][context] and \
                        self._speed_stats[scope][context][-1]["end_time"] is None:
                        self._speed_stats[scope][context].pop()

                    if running_stat:
                        self._append_stats_snapshot(
                            scope,
                            context,
                            running_stat["description"],
                            running_stat["start_time"]
                        )

                else:
                    self._speed_stats[scope][context].extend(copy.deepcopy(stat_list))

    def retrieve_merge_stats(self, stats_cache_key: str) -> None:
        """
        Retrieve the stats from the cache and merge them into the current object.
        """
        retrieved_stats = cache.get(stats_cache_key)

        if not retrieved_stats:
            return None

        if not isinstance(retrieved_stats, SpeedStatistics):
            raise ValueError(f"Retrieved stats from cache {stats_cache_key} are not a SpeedStatistics object")

        self.merge_stats(retrieved_stats)

    def pop_merge_stats(self, stats_cache_key: str) -> None:
        """
        Retrieve the stats from the cache and merge them into the current object.
        Then delete the stats from the cache.
        """
        self.retrieve_merge_stats(stats_cache_key)
        cache.delete(stats_cache_key)

    def cache_stats(self, stats_cache_key: str, cache_timeout: int = 60 * 60 * 24) -> None:
        cache.set(stats_cache_key, self, cache_timeout)

    @staticmethod
    def stats_render(speed_statistics: 'SpeedStatistics', request: HttpRequest, *r_args, **r_kwargs) -> HttpResponse:
        """
        Render the template and add the render time to the response.
        """
        # Make sure that the wrapped function passed is a view
        if "context" in r_kwargs:
            context = r_kwargs["context"]
            if context is None:
                context = {}
                r_kwargs["context"] = context

        elif len(r_args) >= 2:
            context = r_args[1]
            if context is None:
                context = {}
                r_args = (r_args[0], context, *r_args[2:])

        else:
            context = {}
            r_kwargs["context"] = context

        # Add the speed statistics display to the context
        context["speed_statistics_display"] = speed_statistics.get_stats_view_display()

        # Run and time the render
        speed_statistics.start("_render", "Render the template", "_render")
        response = render(request, *r_args, **r_kwargs)
        speed_statistics.end("_render", "_render")

        if not isinstance(response, HttpResponse):
            raise ValueError(f"Response is not a HttpResponse object")

        # Add the render time to the response
        response.content += f'<div id="renderLoadTimePlaceholder">{speed_statistics.get_context_stats("_render", "_render")[-1]["time_difference"]:.4f}</div>'.encode('utf-8')

        return response

    def _create_stats_dict(self, scope: str) -> None:
        """
        Create a new stats dictionary for the given scope.
        """
        if not scope:
            raise ValueError("Scope cannot be None")

        if scope not in self._speed_stats:
            self._speed_stats[scope] = defaultdict(list)

    def _append_stats_snapshot(self, scope: str, context: str, description: str = None, start_time: float = None, end_time: float = None) -> None:
        """
        Append a new stats snapshot to the given context and scope.
        """
        self._speed_stats[scope][context].append(self._make_stats_snapshot(context, description, start_time, end_time))

    def _make_stats_snapshot(self, context: str, desc: str = None, start_time: float = None, end_time: float = None) -> dict:
        """
        Make a new stats snapshot for the given context and scope.
        """
        time_difference = end_time - start_time if end_time is not None and start_time is not None else None

        return {
            "context": context,
            "description": desc,
            "start_time": start_time,
            "end_time": end_time,
            "time_difference": time_difference,
        }

    def _get_scope(self, scope: str) -> str:
        """
        Get and validate a scope from the given scope or the default scope.
        """
        if not scope:
            scope = self._scope

        if scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        return scope

        
    

