## Plan

**Approach:**
Capture active W3C trace context (`traceparent`) and correlation ID at enqueue time via helper functions in `src/observability/tasks.py` and `src/core/context.py`, propagating them as optional keyword arguments on all Huey task signatures. On the worker side, wrap each task's `asyncio.run()` boundary in a `restore_task_context` context manager that attaches any incoming `traceparent` (or starts a new root span/trace if none is provided or for periodic tasks), synchronizes `request_id`, and safely cleans up on completion or early returns. This builds directly on the unified request/trace context from F-OBS-T03 and SDK bootstrap from F-OBS-T02 without altering task business signatures, retries, or error semantics.

(Rejected alternative: Overriding Huey's internal `TaskWrapper` to automatically inject kwargs was rejected because task functions with explicit signatures would fail with `TypeError` on unexpected keyword arguments if third-party or unmigrated tasks are invoked.)

**Files:**
- `src/core/context.py` — modify: Add `get_traceparent()` helper to retrieve current W3C traceparent string if an active span exists.
- `src/observability/tasks.py` — create: Add `capture_task_context()` helper for enqueue call sites and `restore_task_context()` context manager for worker execution.
- `src/observability/__init__.py` — modify: Re-export `capture_task_context` and `restore_task_context`.
- `src/integration/task.py` — modify: Add `traceparent: str | None = None` to `sync_account_positions_task`, wrapping its `asyncio.run()` with `restore_task_context`.
- `src/account/task.py` — modify: Add `request_id: str | None = None` and `traceparent: str | None = None` to `recalculate_all_account_totals_task`, wrapping its `asyncio.run()` with `restore_task_context`.
- `src/market/task.py` — modify: Add `traceparent` to `generate_note_title_task`, `check_and_dispatch_price_alerts`, and `alert_email_dispatch_task`; wrap periodic tasks (`daily_price_update`, `hourly_intraday_price_update`) and task execution with `restore_task_context`; pass `**capture_task_context()` when enqueuing downstream tasks.
- `src/integration/api.py` — modify: Update `sync_account_positions_task` call site to pass `**capture_task_context()`.
- `src/integration/router.py` — modify: Update `sync_account_positions_task` call site to pass `**capture_task_context()`.
- `src/market/router.py` — modify: Update `generate_note_title_task` call sites (note creation and update) to pass `**capture_task_context()`.
- `tests/routers/test_notes.py` — modify: Update `mock_task.assert_called_once_with` assertions to accept propagated `traceparent` kwargs.
- `tests/test_huey_trace_propagation.py` — create: Unit and integration tests for trace continuity across enqueue, worker execution, periodic tasks, un-instrumented fallbacks, explicit `request_id` handling, and registry-none early returns with `MemoryHuey` and `InMemorySpanExporter`.

**Steps:**
1. In `src/core/context.py`, implement `get_traceparent() -> str | None` using `opentelemetry.propagate.inject` into an empty carrier dict, returning `carrier.get("traceparent")`. Export it in `__all__`.
2. In `src/observability/tasks.py`, implement `capture_task_context(request_id: str | None = None) -> dict[str, str | None]` (returning `request_id` and `traceparent`) and `@contextmanager def restore_task_context(task_name: str, request_id: str | None = None, traceparent: str | None = None)` which extracts and attaches `traceparent` if present, starts span `tracer.start_as_current_span(task_name)`, binds `request_id` via `set_request_id`, sets span attributes, and safely detaches context/resets tokens in `finally`.
3. In `src/observability/__init__.py`, re-export `capture_task_context` and `restore_task_context` and add them to `__all__`.
4. Update `src/integration/task.py`: add `traceparent: str | None = None` kwarg to `sync_account_positions_task` and wrap `asyncio.run(_sync_account_positions_task(...))` with `with restore_task_context("sync_account_positions_task", request_id=request_id, traceparent=traceparent):`.
5. Update `src/account/task.py`: add `request_id: str | None = None` and `traceparent: str | None = None` to `recalculate_all_account_totals_task` and wrap `asyncio.run(_recalculate_all_account_totals())` with `with restore_task_context("recalculate_all_account_totals_task", request_id=request_id, traceparent=traceparent):`.
6. Update `src/market/task.py`:
   - Add `traceparent: str | None = None` to `generate_note_title_task`, `check_and_dispatch_price_alerts`, and `alert_email_dispatch_task`, wrapping each `asyncio.run()` with `restore_task_context`.
   - Wrap `daily_price_update` and `hourly_intraday_price_update` with `restore_task_context` (rooting new traces).
   - In `_hourly_intraday_price_update`, pass `**capture_task_context()` when enqueuing `recalculate_all_account_totals_task` and `check_and_dispatch_price_alerts`.
   - In `_check_and_dispatch_price_alerts`, pass `**capture_task_context()` when enqueuing `alert_email_dispatch_task`.
7. Update enqueue call sites in routers and APIs:
   - `src/integration/api.py`: pass `**capture_task_context()` in `IntegrationAccountApi.sync_account_positions`.
   - `src/integration/router.py`: pass `**capture_task_context()` in `import_accounts`.
   - `src/market/router.py`: pass `**capture_task_context()` in note create and update handlers.
8. Update `tests/routers/test_notes.py`: adjust `mock_task.assert_called_once_with` to verify `traceparent=ANY` alongside `request_id=ANY`.
9. Create `tests/test_huey_trace_propagation.py` covering:
   - Trace continuity across enqueue and worker execution with `InMemorySpanExporter` and `MemoryHuey`.
   - Explicit `request_id` preservation and consistency with active trace id.
   - Enqueue with no ambient context starts a fresh root trace.
   - Periodic tasks (`daily_price_update`, `hourly_intraday_price_update`) root their own traces.
   - Chained tasks (`hourly_intraday_price_update` -> `check_and_dispatch_price_alerts` -> `alert_email_dispatch_task`) propagate trace ID across all stages.
   - Early returns when `huey.svcs_registry is None` safely clean up spans and context tokens.
   - Task exceptions record error status on span and cleanly reset context.
10. Run pre-flight linting, type checks, and targeted test suites with `./scripts/agent-test`.

**Verification:**
- Run targeted propagation tests:
  `./scripts/agent-test tests/test_huey_trace_propagation.py`
  Verify all assertions pass (trace id matches across boundary, root traces generated when ambient context empty, periodic tasks root new traces).
- Run integration task suite:
  `./scripts/agent-test tests/tasks/test_integration.py tests/tasks/test_account.py tests/tasks/test_market.py`
  Verify existing task logic, error paths, and mocks continue to pass.
- Run notes router test suite:
  `./scripts/agent-test tests/routers/test_notes.py`
  Verify note title task enqueue assertions pass.
- Run Gate 0 check:
  `./scripts/agent-test --gate0-only`
  Verify Ruff lint/format and Pyright type checking pass with 0 errors.

**Risks / watch-outs:**
- **Registry None in tests**: Tasks like `_generate_note_title` and `_check_and_dispatch_price_alerts` return early if `huey.svcs_registry is None`. `restore_task_context` uses a context manager with `finally` so the span ends and tokens reset even on early exit or unhandled exceptions.
- **Immediate mode in conftest**: `tests/conftest.py` sets `huey.immediate = True`. `restore_task_context` handles both immediate execution (running synchronously inside the active thread) and deferred dequeue execution (unmarshaling `traceparent` from task kwargs).
- **Test mock sensitivity**: `tests/routers/test_notes.py` specifically asserts keyword arguments on `generate_note_title_task`. Step 8 ensures test assertions accommodate the new `traceparent` argument.
