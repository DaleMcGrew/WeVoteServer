# Feature: SpeedStatisticsViewWrapper

## 1. Metadata

- **Feature name:** `SpeedStatisticsViewWrapper`
- **Short summary:** A class-based decorator for Django views that creates a per-request `SpeedStatistics` timer, attaches it to the request, optionally merges in cached timing data, and transparently times the view's template render.
- **Status:** Stable
- **Version added:** Unknown
- **Last updated:** Unknown
- **Owners:** Unknown
- **Audience:** application developers writing Django views who want automatic per-request timing
- **Scope type:** class (used as a decorator)
- **Related components:** `SpeedStatistics` (`wevote_functions/speed_statistics/statistics.py`), `django.shortcuts.render`, Django cache framework, `HttpRequest`/`HttpResponse`
- **Tags:** decorator, timing, profiling, django, view, instrumentation, render

## 2. Problem and intent

Timing a Django view by hand means creating a `SpeedStatistics` instance inside every view, remembering to attach it to the request, wiring up render timing, and pulling in any previously cached stats. That is repetitive boilerplate that is easy to get wrong. `SpeedStatisticsViewWrapper` packages all of that setup into a single decorator you put above a view function.

- **Problem statement:** Per-request timing setup (instance creation, request attachment, cache merge, render timing) was repetitive and error-prone to add to each view.
- **Primary goal:** Provide a one-line decorator that fully wires up `SpeedStatistics` for a Django view.
- **Secondary goals:** Let a view inherit timing data stored in the cache by prior requests; automatically capture the template render time.
- **Non-goals:** It does not aggregate or persist results after the response (that is the caller's job via `SpeedStatistics.cache_stats`), and it does not itself measure sub-blocks of your view — you still call `request.speed_statistics.start/end` for those.
- **Target users:** Developers instrumenting Django views.
- **When to use it:** You want automatic, consistent timing setup on a view, and optionally want to seed it from cached stats.
- **When not to use it:** Non-view functions, highly concurrent code paths where the global render monkey-patch is unsafe (see Known limitations), or when you need to time code that is not a Django view.

## 3. Conceptual model

Mental model: this is a **decorator factory**. You create an instance with configuration (`@SpeedStatisticsViewWrapper(scope=..., stats_cache_keys=[...])`), and Python calls that instance on your view function to produce a replacement function. Every time the view is called, the replacement runs a setup/teardown routine around your original code.

```
@SpeedStatisticsViewWrapper(scope="dashboard")   # 1. __init__ stores config
def dashboard_view(request): ...                  # 2. __call__ validates + wraps the view
                                                  # 3. on each request, wrapper() runs:
                                                  #    - build SpeedStatistics
                                                  #    - request.speed_statistics = it
                                                  #    - merge cached stats
                                                  #    - route render() -> stats_render()
                                                  #    - run the view, then restore render
```

The key trick is that during the view call, the wrapper temporarily replaces Django's `render` function so that any `render(...)` the view calls is redirected through `SpeedStatistics.stats_render`, which times the render and injects the timing into the response. When the view returns (or raises), the original `render` is put back.

- **Core concept:** A configurable decorator that instruments a Django view with a per-request `SpeedStatistics` timer.
- **Lifecycle:** construct (store config) → decorate (`__call__`, validate the view once) → per request, `wrapper` builds the timer, patches `render`, runs the view, then always restores `render`.
- **Key entities:** the wrapper instance (config holder), the wrapped `func`, the per-request `SpeedStatistics`, the `request` object, the swapped-in `instrumented_render`.
- **State transitions:** render function: `original render -> instrumented_render (during view) -> original render (restored in finally)`.
- **Relationship to existing features:** It is the intended front-end for `SpeedStatistics`: it constructs the instance, calls `retrieve_merge_stats`, and delegates rendering to `SpeedStatistics.stats_render`.

## 4. Public interface

- **Constructor signature:** `SpeedStatisticsViewWrapper(scope: str = None, stats_cache_keys: list = None)`
- **Primary methods:** `__call__(func: Callable) -> Callable` (makes the instance usable as a decorator)
- **Mutable state:** `_default_scope` (the configured scope, or `None` to fall back to the view's function name) and `_default_stats_cache_keys` (list of cache keys to merge in, or `None`). These are set once at construction and read on each request; the per-request key list is copied so the original is not consumed.

| Name | Kind | Type | Required | Default | Description | Constraints |
|------|------|------|----------|---------|-------------|-------------|
| `scope` | constructor arg | `str` | no | `None` | Scope name for the per-request `SpeedStatistics`; when `None`, the decorated view's `__name__` is used | — |
| `stats_cache_keys` | constructor arg | `list` | no | `None` | Cache keys whose stored stats are merged into the new instance on each request | Consumed in reverse (LIFO) order per request |
| `func` | `__call__` arg | `Callable` | yes | — | The Django view being decorated | Must have at least one parameter, and its first parameter must be named `request` or `http_request` |

## 5. Input contract

Mental model for callers: there are two separate "inputs" here. First, the **decorator configuration** you pass when you write `@SpeedStatisticsViewWrapper(...)`. Second, the **decorated view and its runtime `request`**, which are validated later. Some checks happen once when the decorator is applied (at import time), and others happen on every request.

Rules you must follow (and why):

- **The decorated function must take `request`/`http_request` as its first parameter.** At decoration time the wrapper inspects the function signature; if it has no parameters it raises `TypeError`, and if the first parameter is not named `request` or `http_request` it also raises `TypeError`. This guards against decorating something that is not a Django view, since the wrapper relies on the first argument being the request.
- **The runtime first argument must be an `HttpRequest`.** On each call the wrapper checks `isinstance(request, HttpRequest)` and raises `TypeError` otherwise. It attaches state to the request and passes it to `render`, so a non-request value would break those steps.
- **`stats_cache_keys` must be usable as cache keys and point to `SpeedStatistics` values (or nothing).** Each key is passed to `SpeedStatistics.retrieve_merge_stats`; a missing key is ignored (cache miss returns `None`), but a key holding a non-`SpeedStatistics` value raises `ValueError` from the underlying merge.

Fields and arguments:

- **Accepted input types:** `str` scope, `list` of cache-key strings, a `Callable` view whose first parameter is the request.
- **Validation rules:** view must have ≥1 parameter; first parameter named `request`/`http_request`; runtime request must be an `HttpRequest`.
- **Required fields:** `func` (supplied implicitly by the `@` decorator syntax).
- **Optional fields:** `scope` (defaults to the view name), `stats_cache_keys` (defaults to none).
- **Derived fields:** effective scope = `scope` or `func.__name__`; a per-request copy of the cache-key list.
- **Defaults:** `scope=None` → view function name; `stats_cache_keys=None` → empty list (no merges).
- **Invalid input behavior:** signature and request-type problems raise `TypeError`; a wrong-typed cached value raises `ValueError` (propagated from `SpeedStatistics`).

| Field / Argument | Type | Required | Default | Allowed values / format | Validation notes |
|------------------|------|----------|---------|--------------------------|------------------|
| `scope` | `str` | no | `None` | any string | falls back to `func.__name__` when `None` |
| `stats_cache_keys` | `list` | no | `None` | list of cache-key strings | copied per request; consumed LIFO |
| `func` | `Callable` | yes | — | a Django view | `TypeError` if no params or first param not `request`/`http_request` |
| `request` (runtime) | `HttpRequest` | yes | — | a Django `HttpRequest` | `TypeError` if not an `HttpRequest` |

## 6. Output contract

- **Return type / response shape:** `__call__` returns a wrapped `Callable` (the view replacement). Calling the wrapped view returns whatever the original view returns — normally an `HttpResponse`, with render timing injected when the view uses `render`.
- **Success conditions:** a `SpeedStatistics` instance is created and attached to `request.speed_statistics`; configured cache keys are merged in; the original `render` is always restored after the view runs.
- **Side effects:** sets `request.speed_statistics`; reads the Django cache (via `retrieve_merge_stats`); temporarily reassigns `django.shortcuts.render` and any module-level name in the view's module that referenced it; the injected render adds a `#renderLoadTimePlaceholder` div to the response body.
- **Partial success behavior:** the render patch is undone in a `finally` block, so `render` is restored even if the view raises.
- **Idempotency behavior:** decorating is one-time; each request builds a fresh timer, so repeated requests do not share timing state (unless seeded from the cache).
- **Ordering guarantees:** cache keys are merged in reverse order of the provided list (each `pop()` takes the last element first).
- **Consistency guarantees:** best effort and in-process; the global render swap is not concurrency-safe (see Known limitations).

| Output field / effect | Type | Present when | Description |
|-----------------------|------|--------------|-------------|
| wrapped view | `Callable` | after decoration | Replacement function returned by `__call__` |
| `request.speed_statistics` | `SpeedStatistics` | during each request | Per-request timer attached to the request |
| view return value | `HttpResponse` (typically) | view returns | Passthrough of the original view's result |
| render timing div | HTML in response body | view calls `render` | `#renderLoadTimePlaceholder` added by `stats_render` |
| restored `render` | function | always (finally) | Original `django.shortcuts.render` put back |

## 7. Functions and responsibilities

| Symbol | Kind | Responsibility | Inputs | Outputs | Side effects | Typical caller |
|--------|------|----------------|--------|---------|--------------|----------------|
| `__init__` | method | Stores the default scope and cache keys for later use | `scope`, `stats_cache_keys` | `None` | Sets `_default_scope`, `_default_stats_cache_keys` | Decorator usage |
| `__call__` | method | Validates the view signature and returns the wrapping function | `func` | `Callable` | Raises `TypeError` on bad signature | Python at decoration time |
| `wrapper` (inner) | function | Per-request setup: build timer, attach to request, merge cache, patch render, run view, restore render | `request`, `*args`, `**kwargs` | view result | Attaches `request.speed_statistics`; patches/restores `render`; reads cache | Django on each request |
| `instrumented_render` (inner) | function | Routes a `render` call through `SpeedStatistics.stats_render` | `request`, render args | `HttpResponse` | Times render; annotates response | The view's `render` calls |

## 8. Interaction patterns

- **Basic flow:** decorate a view.
  1. `@SpeedStatisticsViewWrapper()` above a view whose first parameter is `request`.
  2. Inside the view, call `request.speed_statistics.start("...")` / `.end("...")` around blocks you care about.
  3. `return render(request, template, context)` — render timing is captured automatically.
- **Advanced flow:** seed from cached stats and choose a scope.
  1. `@SpeedStatisticsViewWrapper(scope="dashboard", stats_cache_keys=["prewarm_1", "prewarm_2"])`.
  2. On each request the wrapper merges `prewarm_2` then `prewarm_1` (LIFO) into the new instance before running the view.
- **Async flow:** Not applicable (synchronous view wrapping).
- **Error recovery flow:** if decoration raises `TypeError`, rename the view's first parameter to `request`/`http_request` or ensure it takes the request. If a request-time `TypeError` fires, confirm the wrapped callable really is a view receiving an `HttpRequest`. If a `ValueError` bubbles up from a cache key, the cached value is not a `SpeedStatistics` — fix or clear that key. Note that even when the view raises, the original `render` is restored automatically.
- **Integration points:** `SpeedStatistics` (construction, `retrieve_merge_stats`, `stats_render`), Django cache, `django.shortcuts.render`, and the view module's namespace (which is patched so its imported `render` name is redirected).

## 9. Examples

#### Minimal example

```python
from wevote_functions.speed_statistics.wrapper import SpeedStatisticsViewWrapper
from django.shortcuts import render

@SpeedStatisticsViewWrapper()
def home_view(request):
    request.speed_statistics.start("build_page")
    context = {"message": "hello"}
    request.speed_statistics.end("build_page")
    return render(request, "home.html", context)
```

**Expected result**

```text
Normal HttpResponse for home.html, with:
- request.speed_statistics populated (scope "home_view")
- a trailing <div id="renderLoadTimePlaceholder">...</div> in the body
- context["speed_statistics_display"] available to the template
```

#### Realistic example

```python
from wevote_functions.speed_statistics.wrapper import SpeedStatisticsViewWrapper
from django.shortcuts import render

@SpeedStatisticsViewWrapper(scope="dashboard", stats_cache_keys=["dashboard_prewarm"])
def dashboard_view(request):
    stats = request.speed_statistics            # merged with cached "dashboard_prewarm" stats
    stats.start("db_query", "Load dashboard rows")
    data = load_dashboard_data()
    stats.end("db_query")
    return render(request, "dashboard.html", {"data": data})
```

**Expected result**

```text
An HttpResponse whose template context includes speed_statistics_display containing
both the merged cached timings and this request's "db_query" and "_render" snapshots,
and whose body ends with e.g. <div id="renderLoadTimePlaceholder">0.0123</div>.
```

## 10. Error handling

- **User-visible errors:** `TypeError` at decoration time (view has no parameters, or first parameter is not `request`/`http_request`) and `TypeError` at call time (first argument is not an `HttpRequest`).
- **Internal failures:** `ValueError` propagated from `SpeedStatistics.retrieve_merge_stats` when a cache key holds a non-`SpeedStatistics` value; any exception raised by the wrapped view propagates normally.
- **Retryable errors:** none are meaningfully retryable without changing inputs; they signal programming or data problems.
- **Non-retryable errors:** signature/request-type `TypeError`s require fixing the view or caller; the cache `ValueError` requires fixing the cached data.
- **Fallback behavior:** a cache miss is silently ignored (no merge); the original `render` is always restored via `finally`, even when the view raises.

| Error code / exception | Layer | Cause | Retryable | Caller action | Notes |
|------------------------|-------|-------|-----------|---------------|-------|
| `TypeError` | library | Decorated view has no parameters | no | Give the view a `request` parameter | Raised in `__call__` |
| `TypeError` | library | First parameter not `request`/`http_request` | no | Rename the first parameter | Raised in `__call__` |
| `TypeError` | library | Runtime first argument not `HttpRequest` | no | Ensure it is called as a view | Raised in `wrapper` |
| `ValueError` | library (via `SpeedStatistics`) | Cache key holds a non-`SpeedStatistics` value | no | Fix or clear the cache key | From `retrieve_merge_stats` |
| view exception | application | The wrapped view raised | depends | Handle in the view | `render` is still restored |

## 11. Performance characteristics

- **Expected latency:** Unknown; overhead is small relative to the view (one instance creation, a signature inspection at decoration time, and a dictionary scan of the view module to patch `render`).
- **Time complexity:** per request O(m) where m = number of names in the view's module that reference `render` (scanned to patch), plus O(k) for k configured cache keys; decoration-time signature check is O(1).
- **Space complexity:** O(1) extra beyond the `SpeedStatistics` instance and a copied key list.
- **Throughput expectations:** Unknown.
- **Size limits:** Not applicable.
- **Rate limits:** Not applicable.
- **Resource usage:** In-memory; reads the cache once per configured key.

| Metric | Value | Conditions | Notes |
|--------|-------|------------|-------|
| module render-name scan | O(m) | m = names in view module | Runs each request in `wrapper` |
| cache merges | O(k) | k = configured keys | One `retrieve_merge_stats` per key |

## 12. Security and safety

- **Auth requirements:** None (a decorator; it does not perform authentication).
- **Permissions needed:** None.
- **Sensitive inputs:** Cache keys reference cached objects; the whole `SpeedStatistics` from the cache is trusted and merged.
- **Sensitive outputs:** Render timing is written into the HTML response, exposing performance information to clients.
- **Abuse risks:** The global `render` monkey-patch is process-wide during the view; under concurrency this can leak the instrumented render into other requests (correctness and information-exposure risk). A poisoned cache value causes a `ValueError`.
- **Mitigations:** Prefer using it on views where the render swap is acceptable; validate/trust the cache backend; avoid putting sensitive labels in timing contexts. The `finally` block ensures `render` is restored for the current call.
- **Audit events:** None.
- **Safe defaults:** No cache merging unless keys are explicitly configured; scope defaults to the view name.

## 13. Configuration and environment

- **Environment variables:** None specific to this class.
- **Feature flags:** None.
- **External dependencies:** `SpeedStatistics`, `django.shortcuts.render`, Django cache framework (for `stats_cache_keys` merges), `django.http` types, and Python's `inspect`/`functools`/`sys`.
- **Supported environments:** Any environment running the Django project.
- **Compatibility:** Python 3 (type hints, `functools.wraps`); a configured Django cache backend is required only when `stats_cache_keys` is used.

| Setting / dependency | Required | Default | Example | Description |
|----------------------|----------|---------|---------|-------------|
| `scope` | no | `None` (view name) | `"dashboard"` | Scope for the per-request timer |
| `stats_cache_keys` | no | `None` | `["prewarm_1"]` | Cache keys merged in per request |
| Django cache backend | only with cache keys | project default | `Redis`, `LocMemCache` | Backs the `retrieve_merge_stats` calls |

## 14. Observability

- **Logs emitted:** None.
- **Metrics:** None emitted directly; it feeds `SpeedStatistics`, which holds the timing data.
- **Traces:** None.
- **Health signals:** Presence of `request.speed_statistics` inside the view and a `#renderLoadTimePlaceholder` div in the rendered page indicate the wrapper is active.
- **Debug procedure:** Confirm the decorator is applied and the first parameter is `request`/`http_request`; inspect `request.speed_statistics.get_stats()` mid-view; if render timing is missing, verify the view calls `django.shortcuts.render` (the patch targets that function/name).

## 15. Compatibility and migration

- **Backward compatibility:** Unknown (no version history in source).
- **Migration path:** Not applicable.
- **Deprecated behavior:** None identified.
- **Version-specific notes:** Unknown.

## 16. Known limitations

- **Unsupported cases:** Only Django views whose first parameter is `request`/`http_request`; not general functions. Class-based view methods (first parameter `self`) are not directly supported.
- **Operational limits:** The render instrumentation only applies to `django.shortcuts.render`; other rendering paths are not timed.
- **Behavioral caveats:** The wrapper mutates the global `django.shortcuts.render` and module-level `render` references for the duration of the view. This is **not thread-safe** — concurrent requests in the same process can observe each other's patched `render`. It also reassigns `django.shortcuts.render` itself, which is process-global. The cache keys are consumed in reverse (LIFO) order.
- **Open issues:** Unknown.

## 17. Related references

- **Source files:** `wevote_functions/speed_statistics/wrapper.py`, `wevote_functions/speed_statistics/statistics.py`
- **Tests:** Unknown
- **Design docs:** Unknown
- **API references:** `docs/apps/wevote_functions/README_SPEED_STATISTICS.md`
- **Runbooks:** Unknown
- **Issue tracker items:** Unknown
- **Changelog entries:** Unknown

## 18. AI extraction block

```yaml
feature_name: SpeedStatisticsViewWrapper
summary: Class-based decorator that instruments a Django view with a per-request SpeedStatistics timer, optional cached-stats merging, and automatic render timing.
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
  primary_source_location: wevote_functions/speed_statistics/wrapper.py
  secondary_sources:
    - wevote_functions/speed_statistics/statistics.py
  confidence_level: high
entry_points:
  - name: SpeedStatisticsViewWrapper
    kind: class
    signature_or_path: "SpeedStatisticsViewWrapper(scope: str = None, stats_cache_keys: list = None)"
    visibility: public
  - name: __call__
    kind: method
    signature_or_path: "__call__(func: Callable) -> Callable"
    visibility: public
inputs:
  - name: scope
    type: str
    required: false
    default: null
    constraints: falls back to func.__name__
  - name: stats_cache_keys
    type: list
    required: false
    default: null
    constraints: cache-key strings, consumed LIFO
  - name: func
    type: Callable
    required: true
    default: null
    constraints: first parameter must be request or http_request
  - name: request
    type: HttpRequest
    required: true
    default: null
    constraints: must be an HttpRequest at call time
outputs:
  - name: wrapped_view
    type: Callable
    description: Replacement view returned by __call__
  - name: request.speed_statistics
    type: SpeedStatistics
    description: Per-request timer attached to the request
  - name: response
    type: HttpResponse
    description: View result with render timing injected
side_effects:
  - sets request.speed_statistics
  - reads Django cache via retrieve_merge_stats
  - temporarily patches django.shortcuts.render and module-level render names
  - restores render in a finally block
responsibilities:
  - symbol: __init__
    responsibility: Store default scope and cache keys
    typical_caller: decorator usage
  - symbol: __call__
    responsibility: Validate view signature and return the wrapper
    typical_caller: Python at decoration time
  - symbol: wrapper
    responsibility: Per-request setup, render patching, and teardown
    typical_caller: Django on each request
error_modes:
  - code_or_type: TypeError
    retryable: false
    meaning: View has no parameters or first param is not request/http_request, or runtime arg is not HttpRequest
  - code_or_type: ValueError
    retryable: false
    meaning: A configured cache key holds a non-SpeedStatistics value
limits:
  rate_limit: null
  payload_limit: null
  latency_expectation: null
security:
  auth: none
  permissions: none
  sensitive_data: render timing exposed in HTML; global render patch is not thread-safe
relationships:
  depends_on:
    - SpeedStatistics
    - django.shortcuts.render
    - django.core.cache.cache
  emits_to:
    - request.speed_statistics
  called_by:
    - Django view dispatch (as a decorator)
related_components:
  - SpeedStatistics
  - Django cache framework
example_files:
  - wevote_functions/speed_statistics/wrapper.py
unknowns:
  - version_added
  - owners
  - test coverage
```
