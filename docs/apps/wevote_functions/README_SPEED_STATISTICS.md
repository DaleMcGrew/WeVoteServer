# Feature: SpeedStatistics

## 1. Metadata

- **Feature name:** `SpeedStatistics`
- **Short summary:** An in-memory collector that records how long different parts of your code take by pairing start/end timestamps, grouped by scope and context, and can render those timings into a Django template.
- **Status:** Stable
- **Version added:** Unknown
- **Last updated:** 7/21/2026
- **Owners:** Marcel Jacquot
- **Audience:** application developers (Django view authors) adding timing instrumentation
- **Scope type:** class
- **Related components:** `SpeedStatisticsViewWrapper` (`wevote_functions/speed_statistics/wrapper.py`), Django cache framework (`django.core.cache.cache`), `django.shortcuts.render`
- **Tags:** timing, profiling, instrumentation, performance, django, cache

## 2. Problem and intent

Before this class, timing a block of code meant sprinkling `time()` calls around and manually subtracting them, with no shared structure for organizing the results or displaying them. `SpeedStatistics` gives you a single object that holds many named timers, keeps their raw start/end times, and can merge results collected across different requests or processes.

- **Primary goal:** Make it easy to record and organize elapsed-time measurements for named blocks of code.
- **Secondary goals:** Allow timing data to be cached and merged across requests/processes; produce a template-ready view of the timings for display.
- **Non-goals:** It is not a statistical profiler (no sampling, no call-graph), does not persist data on its own beyond an explicit cache write, and does not measure CPU/memory — only wall-clock time.
- **Target users:** Developers instrumenting Django views or code blocks who want lightweight, structured timing.
- **When to use it:** You want to measure specific, named sections of code ("db_query", "render") and optionally show the numbers on a page.
- **When not to use it:** You need low-overhead sampling profiling, production-grade metrics/tracing, or timing across threads sharing one instance (it is not thread-safe).

## 3. Conceptual model

Mental model: think of the data as three nested layers.

```
scope (e.g. a view or page)
  └── context (a named timer, e.g. "db_query")
        └── list of snapshots (each snapshot = one start/end measurement)
```

A **snapshot** is a plain dictionary describing one measurement:

```python
{
    "context": "db_query",
    "description": "Load the user row",
    "start_time": 100.0,       # from time()
    "end_time": 105.5,          # None while still running
    "time_difference": 5.5,     # end_time - start_time, or None if open
}
```

A snapshot is **open** when it has a `start_time` but `end_time` is still `None` (the timer is running). It becomes **closed** once you set an `end_time` — a closed snapshot is a completed measurement. You start a timer with `start(...)` and stop it with `end(...)`. Because each context holds a *list* of snapshots, you can time the same block many times and get one snapshot per run.

- **Core concept:** A structured, in-memory store of start/end time measurements grouped as scope → context → snapshots.
- **Lifecycle:** create with a scope → `start` a context (adds an open snapshot) → `end` it (closes that snapshot) → optionally `cache_stats` and later `merge_stats`/`retrieve_merge_stats` into another instance → `get_stats_view_display` to render.
- **Key entities:** `SpeedStatistics` instance, scope (str), context (str), snapshot (dict).
- **State transitions:** snapshot: `open (start_time set, end_time None) -> closed (end_time set)`.
- **Relationship to existing features:** `SpeedStatisticsViewWrapper` creates an instance per request, attaches it to `request.speed_statistics`, merges any cached stats, and routes Django's `render` through `stats_render` so page render time is captured automatically.

## 4. Public interface

- **Constructor signature:** `SpeedStatistics(scope: str)`
- **Primary methods:** `start`, `end`, `update_end`, `set_scope`, `get_scope`, `get_stats`, `get_stats_view_display`, `get_context_stats`, `peek_context_stats`, `pop_context_stats`, `pop_context_stat`, `merge_stats`, `retrieve_merge_stats`, `pop_merge_stats`, `cache_stats`, `stats_render` (static)
- **Mutable state:** `_speed_stats` (dict of scope → `defaultdict(list)` of context → list of snapshot dicts) and `_scope` (the default scope string). Invariant: within a context's list, at most the last snapshot may be open; you must close it before starting another.

| Name | Kind | Type | Required | Default | Description | Constraints |
|------|------|------|----------|---------|-------------|-------------|
| `scope` | constructor arg | `str` | yes | — | Default scope name for the instance | Must be non-empty |
| `context` | method arg | `str` | yes | — | Name of the timer within a scope | Used as a dict key |
| `description` | method arg (`start`) | `str` | no | `None` | Human-readable label stored on the snapshot | — |
| `scope` | method arg | `str` | no | `None` | Scope to act on; falls back to the instance default when omitted | For read/close methods the scope must already exist |
| `other_stats` | method arg (`merge_stats`) | `SpeedStatistics` | yes | — | Another instance whose data is merged in | Must be a `SpeedStatistics` |
| `stats_cache_key` | method arg | `str` | yes | — | Django cache key for stored stats | — |
| `cache_timeout` | method arg (`cache_stats`) | `int` | no | `86400` (24h) | Cache TTL in seconds | — |
| `speed_statistics` | static arg (`stats_render`) | `SpeedStatistics` | yes | — | Instance used to time and annotate the render | — |
| `request` | static arg (`stats_render`) | `HttpRequest` | yes | — | Request passed through to `render` | — |

## 5. Input contract

Mental model for callers: you always operate inside a **scope** and on a named **context**. Most methods let you omit `scope`, in which case the instance's default scope is used. There is an important asymmetry: `start` will *create* a scope that does not exist yet, but the read/close methods (`end`, `update_end`, `get_context_stats`, `peek_context_stats`, `pop_context_stats`, `pop_context_stat`) require the scope to already exist and will raise if it does not.

Rules you must follow (and why):

- **Scope cannot be empty.** `__init__` and `set_scope` reject `""`. An empty scope key would make timings impossible to group or look up.
- **Do not `start` a context whose last snapshot is still open.** Call `end` (or `update_end`) first. Violating this raises `ValueError`.
- **Do not `end` a context that has no matching open snapshot.** `end` raises if the context does not exist, has no snapshots, or its last snapshot is already closed (in the already-closed case, use `update_end` instead to overwrite the end time).
- **`merge_stats` requires a real `SpeedStatistics` instance.** Merging arbitrary objects (or cached values of the wrong type) is rejected with `ValueError` to avoid corrupting the internal structure.

Fields and arguments:

- **Accepted input types:** `str` scope/context/description, `SpeedStatistics` for merges, `str` cache keys, `int` timeout.
- **Validation rules:** scope must be non-empty; `start` forbids opening over an already-open snapshot; `end` requires an existing open snapshot; `merge_stats`/`retrieve_merge_stats` require a `SpeedStatistics` object.
- **Required fields:** `scope` (constructor), `context` (timer methods).
- **Optional fields:** `description` (defaults `None`), `scope` on methods (defaults to instance scope), `cache_timeout` (defaults `86400`).
- **Derived fields:** `time_difference` is computed as `end_time - start_time`, or `None` while open.
- **Defaults:** omitted `scope` → instance default; omitted `description` → `None`; omitted `cache_timeout` → 24 hours.
- **Invalid input behavior:** most violations raise `ValueError`; missing-context reads/pops and a cache miss in `retrieve_merge_stats` return `None` instead of raising.

| Field / Argument | Type | Required | Default | Allowed values / format | Validation notes |
|------------------|------|----------|---------|--------------------------|------------------|
| `scope` (constructor) | `str` | yes | — | non-empty string | `""` raises `ValueError` |
| `context` | `str` | yes | — | any string key | must exist for close/read methods |
| `description` | `str` | no | `None` | any string | stored verbatim on the snapshot |
| `scope` (methods) | `str` | no | `None` | non-empty string | falls back to instance scope; must exist for read/close |
| `other_stats` | `SpeedStatistics` | yes | — | a `SpeedStatistics` instance | wrong type raises `ValueError` |
| `stats_cache_key` | `str` | yes | — | any cache key | missing key → `None` (no error) |
| `cache_timeout` | `int` | no | `86400` | seconds | passed straight to Django cache |

## 6. Output contract

- **Return type / response shape:** timers (`start`, `end`, `update_end`, `set_scope` aside) return `None`; readers return snapshot dicts or lists (or `None` when absent); `get_stats_view_display` and `get_stats` return dicts; `stats_render` returns an `HttpResponse`.
- **Success conditions:** for timers, the internal `_speed_stats` structure is updated; for readers, a deep copy of the requested data is returned so callers cannot mutate internal state by accident.
- **Side effects:** mutates in-memory `_speed_stats`; `cache_stats`/`retrieve_merge_stats`/`pop_merge_stats` read/write/delete the Django cache; `stats_render` calls Django `render` and appends HTML to the response body.
- **Partial success behavior:** `merge_stats` merges scope-by-scope and context-by-context; if the current object already has an open snapshot for a context, that running timer is preserved at the end of the list and a duplicate incoming open snapshot is dropped.
- **Idempotency behavior:** `start`/`end` are not idempotent (each `start` appends a new snapshot). `update_end` is effectively idempotent for setting the end time (it overwrites the last snapshot's end time with the current time).
- **Ordering guarantees:** `get_stats_view_display` sorts snapshots within a scope by `(start_time, end_time)` ascending (with `None` sorting last) and sorts scopes by their earliest snapshot's `start_time`.
- **Consistency guarantees:** best effort, in-process only; no locking, so it is not safe to share one instance across threads.

| Output field / effect | Type | Present when | Description |
|-----------------------|------|--------------|-------------|
| snapshot dict | `dict` | reader finds data | `{context, description, start_time, end_time, time_difference}` (deep copy) |
| `get_stats_view_display` result | `dict[str, list[dict]]` | always | scope → sorted, flattened list of snapshots; open timers get a display-only `end_time` |
| `get_stats` result | `dict` | always | the live internal structure (not a copy) |
| `None` | `None` | context/scope data absent or cache miss | signals "nothing found" instead of raising |
| annotated `HttpResponse` | `HttpResponse` | `stats_render` succeeds | response body gains a `#renderLoadTimePlaceholder` div with render seconds |

## 7. Functions and responsibilities

| Symbol | Kind | Responsibility | Inputs | Outputs | Side effects | Typical caller |
|--------|------|----------------|--------|---------|--------------|----------------|
| `__init__` | method | Creates the instance and registers the default scope | `scope` | `None` | Initializes `_speed_stats`, `_scope` | Instantiating code / wrapper |
| `get_stats_view_display` | method | Builds a template-ready, sorted, deep-copied view; fills open timers with a display end time | — | `dict[str, list[dict]]` | None (copies) | `stats_render`, templates |
| `get_stats` | method | Returns the live internal stats dict | — | `dict` | None | Debugging, advanced callers |
| `set_scope` | method | Sets and creates the default scope | `scope` | `str` (new scope) | Mutates `_scope`, adds scope | Callers switching scope |
| `get_scope` | method | Returns the current default scope | — | `str` | None | Callers |
| `start` | method | Appends a new open snapshot for a context | `context`, `description`, `scope` | `None` | Adds snapshot; creates scope if missing | Instrumentation code |
| `end` | method | Closes the last open snapshot for a context | `context`, `scope` | `None` | Replaces last snapshot with a closed one | Instrumentation code |
| `update_end` | method | Overwrites the last snapshot's end time with now | `context`, `scope` | `None` | Replaces last snapshot | Callers correcting an end time |
| `get_context_stats` | method | Deep-copies all snapshots for a context | `context`, `scope` | `list` or `None` | None | Readers, `stats_render` |
| `peek_context_stats` | method | Deep-copies the most recent snapshot for a context | `context`, `scope` | `dict` or `None` | None | Readers |
| `pop_context_stats` | method | Removes and returns all snapshots for a context | `context`, `scope` | `list` or `None` | Removes the context | Callers draining data |
| `pop_context_stat` | method | Removes and returns the most recent snapshot | `context`, `scope` | `dict` or `None` | Removes snapshot; removes context if now empty | Callers draining data |
| `merge_stats` | method | Merges another instance's data into this one | `other_stats` | `None` | Mutates `_speed_stats` | Aggregation across requests |
| `retrieve_merge_stats` | method | Loads stats from cache and merges them | `stats_cache_key` | `None` | Reads cache; mutates state | Wrapper on request start |
| `pop_merge_stats` | method | Merges cached stats, then deletes the cache key | `stats_cache_key` | `None` | Reads + deletes cache; mutates state | One-shot aggregation |
| `cache_stats` | method | Stores this instance in the cache | `stats_cache_key`, `cache_timeout` | `None` | Writes cache | Handing off to another request |
| `stats_render` | staticmethod | Times a Django render and appends the render time to the response | `speed_statistics`, `request`, render args | `HttpResponse` | Calls `render`; mutates response body | `SpeedStatisticsViewWrapper` |
| `_create_stats_dict` | internal method | Creates the per-scope `defaultdict(list)` if absent | `scope` | `None` | Mutates `_speed_stats` | Internal only |
| `_append_stats_snapshot` | internal method | Builds and appends a snapshot | `scope`, `context`, `description`, `start_time`, `end_time` | `None` | Mutates `_speed_stats` | Internal only |
| `_make_stats_snapshot` | internal method | Constructs a snapshot dict and computes `time_difference` | `context`, `desc`, `start_time`, `end_time` | `dict` | None | Internal only |
| `_get_scope` | internal method | Resolves and validates a scope, raising if it does not exist | `scope` | `str` | None | Internal only |

## 8. Interaction patterns

- **Basic flow:** time one block.
  1. `stats = SpeedStatistics("my_view")`
  2. `stats.start("db_query", "Load rows")`
  3. run the code you want to measure
  4. `stats.end("db_query")`
  5. `stats.get_context_stats("db_query")` to read the result.
- **Advanced flow:** aggregate across requests.
  1. In request A, collect timings and `stats.cache_stats("run_42")`.
  2. In request B, create a new instance and `stats_b.retrieve_merge_stats("run_42")` (or `pop_merge_stats` to also clear it).
  3. `stats_b.get_stats_view_display()` for the combined view.
- **Async flow:** Not applicable (synchronous, single-process).
- **Error recovery flow:** if `start` raises "currently keeping track of a start time", the previous snapshot is still open — call `end` (to close it normally) or `update_end` (to force its end time to now) before retrying `start`. If `end` raises "already has an end time", call `update_end` instead. If a reader returns `None`, the context/scope simply has no data yet — decide whether that is expected before dereferencing.
- **Integration points:** `SpeedStatisticsViewWrapper` (per-request setup and render routing), Django cache, `django.shortcuts.render`, and the template variable `speed_statistics_display`.

## 9. Examples

#### Minimal example

```python
from wevote_functions.speed_statistics.statistics import SpeedStatistics

stats = SpeedStatistics("checkout")
stats.start("total")
# ... work ...
stats.end("total")

print(stats.peek_context_stats("total"))
```

**Expected result**

```text
{'context': 'total', 'description': None, 'start_time': 1712345678.12,
 'end_time': 1712345678.20, 'time_difference': 0.08}
```

#### Realistic example

```python
from wevote_functions.speed_statistics.wrapper import SpeedStatisticsViewWrapper

@SpeedStatisticsViewWrapper(scope="dashboard")
def dashboard_view(request):
    request.speed_statistics.start("db_query", "Load dashboard data")
    data = load_dashboard_data()
    request.speed_statistics.end("db_query")
    # render() is transparently routed through stats_render, which
    # times the render and injects speed_statistics_display into the context
    return render(request, "dashboard.html", {"data": data})
```

**Expected result**

```text
An HttpResponse whose body ends with e.g.:
<div id="renderLoadTimePlaceholder">0.0123</div>
and whose template context contains speed_statistics_display:
{"dashboard": [{"context": "db_query", ...}, {"context": "_render", ...}]}
```

## 10. Error handling

- **User-visible errors:** `ValueError` for empty scope, starting over an open snapshot, ending without a matching open snapshot, ending an already-closed snapshot, merging a non-`SpeedStatistics`, or a non-`HttpResponse` result inside `stats_render`.
- **Internal failures:** `_get_scope` raises `ValueError` when the requested scope does not exist; a cache holding the wrong type raises `ValueError` in `retrieve_merge_stats`.
- **Retryable errors:** the "context is currently keeping track of a start time" and "already has an end time" errors are recoverable — close/update the snapshot, then retry.
- **Non-retryable errors:** empty-scope and wrong-type errors require the caller to fix the argument, not retry.
- **Fallback behavior:** missing context in `get_context_stats`, `peek_context_stats`, `pop_context_stats`, `pop_context_stat`, and a cache miss in `retrieve_merge_stats` return `None` rather than raising.

| Error code / exception | Layer | Cause | Retryable | Caller action | Notes |
|------------------------|-------|-------|-----------|---------------|-------|
| `ValueError` | library | Scope is `""` | no | Pass a non-empty scope | `__init__`, `set_scope` |
| `ValueError` | library | `start` while last snapshot open | yes | Call `end`/`update_end` first | Prevents losing a measurement |
| `ValueError` | library | `end` on missing/empty context | no | Call `start` first | Nothing to close |
| `ValueError` | library | `end` when last snapshot already closed | yes | Use `update_end` | Overwrite the end time |
| `ValueError` | library | Scope does not exist (`_get_scope`) | no | Create/select an existing scope | Read/close methods |
| `ValueError` | library | `merge_stats` arg not a `SpeedStatistics` | no | Pass a valid instance | Also guards cached values |
| `ValueError` | library | `stats_render` result not `HttpResponse` | no | Ensure the view returns a response | — |
| `None` (no exception) | library | Missing context or cache miss | n/a | Check for `None` before use | Intentional soft failure |

## 11. Performance characteristics

- **Expected latency:** Unknown (dominated by the code being measured, not the collector).
- **Time complexity:** `start`/`end`/`peek` are O(1) amortized; `get_stats_view_display` is O(n log n) in the number of snapshots due to sorting; `merge_stats` is O(n) in incoming snapshots.
- **Space complexity:** O(n) in the total number of snapshots retained in memory.
- **Throughput expectations:** Unknown.
- **Size limits:** Unknown; bounded only by available memory since all snapshots are kept until popped.
- **Rate limits:** Not applicable.
- **Resource usage:** In-memory dictionaries; `cache_stats` serializes the whole instance into the Django cache.

| Metric | Value | Conditions | Notes |
|--------|-------|------------|-------|
| `get_stats_view_display` | O(n log n) | n = snapshots in scope | Sorting cost |
| `start`/`end` | O(1) amortized | per call | List append/pop |
| memory | O(n) | n = retained snapshots | Grows until popped/cleared |

## 12. Security and safety

- **Auth requirements:** None (a plain in-memory helper).
- **Permissions needed:** None.
- **Sensitive inputs:** `description` and `context` strings could contain sensitive labels if the caller puts them there; the class does not sanitize them.
- **Sensitive outputs:** `stats_render` writes a render-time value directly into the HTML response body, exposing timing to the client.
- **Abuse risks:** Unbounded growth if snapshots are never popped or the instance is never discarded; timing values embedded in pages can leak performance information.
- **Mitigations:** Pop/clear contexts when done; use cache TTLs (`cache_timeout`) to bound cached data; avoid placing secrets in `context`/`description`.
- **Audit events:** None.
- **Safe defaults:** Cache entries expire after 24 hours by default.

## 13. Configuration and environment

- **Environment variables:** None specific to this class.
- **Feature flags:** None.
- **External dependencies:** Django cache framework (`django.core.cache.cache`) for `cache_stats`/`retrieve_merge_stats`/`pop_merge_stats`; `django.shortcuts.render` and `django.http` types for `stats_render`.
- **Supported environments:** Any environment running the Django project.
- **Compatibility:** Python 3 (uses type hints, f-strings); requires a configured Django cache backend for the cache-related methods.

| Setting / dependency | Required | Default | Example | Description |
|----------------------|----------|---------|---------|-------------|
| Django cache backend | for cache methods only | project default | `LocMemCache`, `Redis` | Backs `cache_stats`/`retrieve_merge_stats`/`pop_merge_stats` |
| `cache_timeout` | no | `86400` | `3600` | TTL (seconds) for cached stats |

## 14. Observability

- **Logs emitted:** None.
- **Metrics:** None emitted directly; the class *is* the timing data source.
- **Traces:** None.
- **Health signals:** A populated `get_stats_view_display()` result and the `#renderLoadTimePlaceholder` div in rendered pages indicate timing is being captured.
- **Debug procedure:** Inspect `get_stats()` for the raw internal structure, or `get_stats_view_display()` for the sorted view; verify each context's last snapshot has an `end_time` (a lingering `None` means a timer was never closed).

## 15. Compatibility and migration

- **Backward compatibility:** Unknown (no version history available in source).
- **Migration path:** Not applicable.
- **Deprecated behavior:** None identified.
- **Version-specific notes:** Unknown.

## 16. Known limitations

- **Unsupported cases:** Not thread-safe; sharing one instance across concurrent threads can corrupt the snapshot lists.
- **Operational limits:** Memory grows with retained snapshots until popped or the instance is discarded.
- **Behavioral caveats:** `get_stats` returns the live internal dict (mutable), whereas the `get_*_stats`/`peek_*` readers return deep copies. `get_stats_view_display` assigns a display-only `end_time` to open timers without changing the stored data. `stats_render` temporarily monkey-patches `django.shortcuts.render` (via the wrapper) for the duration of the view.
- **Open issues:** Unknown.

## 17. Related references

- **Source files:** `wevote_functions/speed_statistics/statistics.py`, `wevote_functions/speed_statistics/wrapper.py`
- **Tests:** Unknown
- **Design docs:** Unknown
- **API references:** Not applicable
- **Runbooks:** Unknown
- **Issue tracker items:** Unknown
- **Changelog entries:** Unknown

## 18. AI extraction block

```yaml
feature_name: SpeedStatistics
summary: In-memory collector that records elapsed-time measurements grouped as scope -> context -> snapshots, with cache-backed merging and Django render timing.
status: Stable
scope_type: class
version_added: null
owners:
  - Unknown
audience:
  - application developers
source_handoff:
  documentation_mode: AI-generated
  primary_source_type: class code
  primary_source_location: wevote_functions/speed_statistics/statistics.py
  secondary_sources:
    - wevote_functions/speed_statistics/wrapper.py
  confidence_level: high
entry_points:
  - name: SpeedStatistics
    kind: class
    signature_or_path: SpeedStatistics(scope: str)
    visibility: public
  - name: start
    kind: method
    signature_or_path: "start(context: str, description: str = None, scope: str = None) -> None"
    visibility: public
  - name: end
    kind: method
    signature_or_path: "end(context: str, scope: str = None) -> None"
    visibility: public
  - name: get_stats_view_display
    kind: method
    signature_or_path: "get_stats_view_display() -> dict"
    visibility: public
  - name: stats_render
    kind: method
    signature_or_path: "stats_render(speed_statistics, request, *r_args, **r_kwargs) -> HttpResponse"
    visibility: public
inputs:
  - name: scope
    type: str
    required: true
    default: null
    constraints: non-empty string
  - name: context
    type: str
    required: true
    default: null
    constraints: must exist for close/read methods
  - name: description
    type: str
    required: false
    default: null
    constraints: null
  - name: cache_timeout
    type: int
    required: false
    default: "86400"
    constraints: seconds
outputs:
  - name: snapshot
    type: dict
    description: "{context, description, start_time, end_time, time_difference}"
  - name: view_display
    type: dict[str, list[dict]]
    description: scope -> sorted flattened list of snapshots
  - name: response
    type: HttpResponse
    description: render response annotated with render time div
side_effects:
  - mutates in-memory _speed_stats
  - reads/writes/deletes Django cache
  - appends HTML to render response body
responsibilities:
  - symbol: start
    responsibility: Append a new open snapshot for a context
    typical_caller: instrumentation code
  - symbol: end
    responsibility: Close the last open snapshot for a context
    typical_caller: instrumentation code
  - symbol: merge_stats
    responsibility: Merge another instance's data into this one
    typical_caller: aggregation across requests
  - symbol: stats_render
    responsibility: Time a Django render and annotate the response
    typical_caller: SpeedStatisticsViewWrapper
error_modes:
  - code_or_type: ValueError
    retryable: false
    meaning: Empty scope, missing scope, wrong merge type, or non-HttpResponse render result
  - code_or_type: ValueError
    retryable: true
    meaning: Start over an open snapshot, or end an already-closed snapshot (recover with end/update_end)
  - code_or_type: "null"
    retryable: false
    meaning: Missing context or cache miss returns None instead of raising
limits:
  rate_limit: null
  payload_limit: null
  latency_expectation: null
security:
  auth: none
  permissions: none
  sensitive_data: render timing exposed in HTML; context/description not sanitized
relationships:
  depends_on:
    - django.core.cache.cache
    - django.shortcuts.render
  emits_to:
    - template context variable speed_statistics_display
  called_by:
    - SpeedStatisticsViewWrapper
related_components:
  - SpeedStatisticsViewWrapper
  - Django cache framework
example_files:
  - wevote_functions/speed_statistics/wrapper.py
unknowns:
  - version_added
  - owners
  - test coverage
```
