from time import time
from django.core.cache import cache
import copy
from collections import defaultdict
from functools import wraps
from typing import Callable
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

class SpeedStatistics:
    def __init__(self, scope: str = None) -> None:
        self._speed_stats = {}
        self._scope = scope

        if scope:
            self.set_scope(scope)

    def get_stats_view_display(self) -> dict:
        scope_items = []
        default_end_time = time.now()
        for scope, stats in self._speed_stats.items():
            copy_list = [ copy.deepcopy(stat) for stat in stats.values() ]

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
        self._create_stats_dict(scope)
        self._scope = scope
        return self._scope

    def get_scope(self) -> str:
        return self._scope

    def start(self, context: str, desc: str = None, scope: str = None) -> None:
        if not scope:
            scope = self._scope

        # Create a new scope if necessary
        self._create_stats_dict(scope)

        if self._speed_stats[scope][context] and self._speed_stats[scope][context][-1]["end_time"] is None:
            raise ValueError(
                f"Context {context} is currently keeping track of a start time. Use '.end' to add an end time before starting a new time."
                )
        
        self._append_stats_snapshot(scope, context, desc, time())

    def end(self, context: str, scope: str = None) -> None:
        if not scope: 
            scope = self._scope

        if scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        if context not in self._speed_stats[scope]:
            raise ValueError(f"Context {context} does not exist in scope {scope}")

        if not self._speed_stats[scope][context]:
            raise ValueError(f"Context {context} has no start times in scope {scope}. Use '.start' instead to add one.")

        if self._speed_stats[scope][context][-1]["end_time"] is not None:
            raise ValueError(f"Context {context} already has an end time in scope {scope}. Use '.update_end' instead.")

        # Mutate the field directly
        context_stat = self._speed_stats[scope][context].pop()
        self._append_stats_snapshot(
            context,
            context_stat["description"],
            context_stat["start_time"],
            time()
        )

    def update_end(self, context: str, scope: str = None) -> None:
        if not scope:
            scope = self._scope

        if scope and scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        if context not in self._speed_stats[scope]:
            raise ValueError(f"Context {context} does not exist in scope {scope}")

        if len(self._speed_stats[scope][context]) == 0:
            raise ValueError(f"Context {context} has no start times in scope {scope}. Use '.start' instead to add one.")

        # Mutate the field directly
        context_stat = self._speed_stats[scope][context].pop()
        self._append_stats_snapshot(
            context,
            context_stat["description"],
            context_stat["start_time"],
            time()
        )

    def get_context_stats(self, context: str, scope: str = None) -> dict:
        if not scope:
            scope = self._scope

        if scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        if context not in self._speed_stats[scope]:
            return None

        if self._speed_stats[scope][context]:
            return  copy.deepcopy(self._speed_stats[scope][context][-1])
        else:
            return None

    def peek_context_stats(self, context: str, scope: str = None) -> dict:
        if not scope:
            scope = self._scope

        if scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        if context not in self._speed_stats[scope] or len(self._speed_stats[scope][context]) == 0:
            return None

        return copy.deepcopy(self._speed_stats[scope][context][-1])

    def pop_context_stats(self, context: str, scope: str = None) -> list:
        """
        Remove and return all the context stats for the given context and scope.
        """
        if not scope:
            scope = self._scope

        if scope and scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        return self._speed_stats[scope].pop(context, None)

    def pop_context_stat(self, context: str, scope: str = None) -> dict:
        """
        Remove and return the most recent context stat for the given context and scope.
        """
        if not scope:
            scope = self._scope

        if scope not in self._speed_stats:
            raise ValueError(f"Scope {scope} does not exist")

        if context not in self._speed_stats[scope]:
            return None

        return_stat = self._speed_stats[scope][context].pop()

        if len(self._speed_stats[scope][context]) == 0:
            self._speed_stats[scope].pop(context)

        return return_stat

    def merge_stats(self, other_stats: 'SpeedStatistics') -> None:
        if not isinstance(other_stats, SpeedStatistics):
            raise ValueError("other_stats must be a SpeedStatistics object")

        for scope, stats in other_stats._speed_stats.items():
            if scope not in self._speed_stats:
                self._create_stats_dict(scope)

            for context, stat_list in stats.items():
                if context in self._speed_stats[scope]:
                    running_stat = None
                    if  self._speed_stats[scope][context] and self._speed_stats[scope][context][-1]["end_time"] is None:
                        running_stat = self._speed_stats[scope][context].pop()

                    self._speed_stats[scope][context].extend(copy.deepcopy(stat_list))

                    if running_stat and self._speed_stats[scope][context][-1]["end_time"] is None:
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
        retrieved_stats = cache.get(stats_cache_key)

        if retrieved_stats:
            self.merge_stats(retrieved_stats)
        else:
            raise Warning(f"Stats cache key {stats_cache_key} does not exist")

    def pop_merge_stats(self, stats_cache_key: str) -> None:
        self.retrieve_merge_stats(stats_cache_key)
        cache.delete(stats_cache_key)

    def cache_stats(self, stats_cache_key: str, cache_timeout: int = 60 * 60 * 24) -> None:
        cache.set(stats_cache_key, self, cache_timeout)

    def stats_render(self, request: HttpRequest, *r_args, **r_kwargs) -> HttpResponse:
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


        context["speed_statistics_display"] = self.get_stats_view_display()

        self.start("render", "Render the template", "render")
        response = render(request, *r_args, **r_kwargs)
        self.end("render", "render")
        # Modify response for render time
        response.content += f'<div id="renderLoadTimePlaceholder">{self.get_context_stats("render", "render")["time_difference"]:.4f}</>'.encode('utf-8')

        return response

    def _create_stats_dict(self, scope: str) -> None:
        if not scope:
            raise ValueError("Scope cannot be None")

        if scope not in self._speed_stats:
            self._speed_stats[scope] = defaultdict(list)
    
    def _append_stats_snapshot(self, scope: str, context: str, desc: str = None, start_time: float = None, end_time: float = None) -> None:
        self._speed_stats[scope][context].append(self._make_stats_snapshot(context, desc, start_time, end_time))

    def _make_stats_snapshot(self, context: str, desc: str = None, start_time: float = None, end_time: float = None) -> dict:
        time_difference = end_time - start_time if end_time is not None and start_time is not None else None

        return {
            "context": context,
            "description": desc,
            "start_time": start_time,
            "end_time": end_time,
            "time_difference": time_difference,
        }


    

