## Plan

**Approach:** Extend the existing logging filter (`RequestIdFilter`), context accessors (`src/core/context.py`), and HTTP middleware (`RequestIdMiddleware` in `src/core/middleware.py`) to unify correlation IDs by exposing the active OpenTelemetry trace ID as `request_id` whenever an active span or inbound W3C `traceparent` context is present. In `RequestIdFilter` and `JsonFormatter`, stamp `trace_id` (the 32-hex trace ID or `"-"`), `request_id` (unified with `trace_id` when inside an active span, or falling back to the existing contextvar / generated ID), and `deploy_id` (`settings.deploy_id`) onto every JSON record, while preserving `[%(request_id)s]` rendering for dev rich logging. In `RequestIdMiddleware`, safely extract inbound W3C `traceparent` context and attach it when no outer server span exists, honour and echo inbound `X-Request-ID` on the response header (falling back to trace ID or UUID when missing), and preserve the single access-log line contract without duplicate logging.

*Alternative rejected:* Creating a separate OTel-specific logging filter and parallel context variable was rejected because existing request logging, Huey task correlation, and WebSocket routers already rely on `request_id_ctx_var` and `RequestIdFilter`; extending the existing mechanism maintains backwards compatibility and prevents split-brain correlation IDs across subsystems.

**Files:**
- `src/core/context.py` — modify: Implement `get_trace_id() -> str | None` to read the active OTel span context and return the 32-character hex trace ID if valid, or `None` if inactive; update `get_request_id() -> str | None` to prefer `get_trace_id()` before falling back to `request_id_ctx_var.get()`.
- `src/config/logging.py` — modify: Extend `RequestIdFilter.filter()` to inject `record.trace_id` (active trace ID or `"-"`), `record.request_id` (unified with `trace_id` under an active span, or falling back to contextvar / `"-"`), and `record.deploy_id` (`settings.deploy_id`). Update `JsonFormatter.format()` to output `trace_id` and `deploy_id` on every JSON log record. Add `RequestIdFilter` to the root logger in `init_logging()` so all handlers (including test log captures) receive correlation attributes.
- `src/core/middleware.py` — modify: Update `RequestIdMiddleware.dispatch()` to extract inbound W3C `traceparent` via `opentelemetry.propagate.extract(request.headers)` and attach the context if no outer span is active; resolve `request_id` prioritizing inbound `X-Request-ID`, then active trace ID, then generated UUID; set `request_id_ctx_var`; echo `request_id` on `response.headers["X-Request-ID"]`; and detach the OTel context and reset `request_id_ctx_var` in `finally`.
- `tests/test_logging.py` — modify: Add tests asserting `JsonFormatter` carries `trace_id` and `deploy_id` in formatted JSON, `RequestIdFilter` unifies `request_id == trace_id` under an active span, falls back cleanly to `"-"` when inactive, and dev mode `FallbackRichHandler` renders without errors.
- `tests/test_request_id.py` — modify: Add tests verifying inbound W3C `traceparent` extraction and response header echoing, preservation of custom `X-Request-ID` alongside `traceparent`, unified `request_id == trace_id` in logs under active server spans, UUID generation when headers are omitted, and single access-log emission.

**Steps:**
1. In `src/core/context.py`, import `trace` from `opentelemetry`. Implement `get_trace_id() -> str | None` which retrieves `trace.get_current_span().get_span_context()` and returns `trace.format_trace_id(ctx.trace_id)` if `ctx.is_valid` else `None`. Update `get_request_id() -> str | None` to return `get_trace_id() or request_id_ctx_var.get()`. Ensure `__all__` exports `get_request_id`, `get_trace_id`, `request_id_ctx_var`, and `set_request_id`.
2. In `src/config/logging.py`, import `get_trace_id` from `src.core.context`. In `RequestIdFilter.filter(record)`:
   - Check `trace_id = get_trace_id()`.
   - If `trace_id` is present, set `record.trace_id = trace_id` and `record.request_id = trace_id`.
   - If `trace_id` is absent, set `record.trace_id = getattr(record, "trace_id", "-")` and `record.request_id = get_request_id() or getattr(record, "request_id", "-")`.
   - Set `record.deploy_id = getattr(record, "deploy_id", settings.deploy_id)`.
   In `JsonFormatter.format(record)`:
   - Add `"trace_id": getattr(record, "trace_id", "-")` and `"deploy_id": getattr(record, "deploy_id", settings.deploy_id)` to `log_dict`.
   In `init_logging()`:
   - Add `RequestIdFilter()` to `logging.getLogger().addFilter(RequestIdFilter())` to guarantee all log handlers receive the stamped fields.
3. In `src/core/middleware.py`, import `context`, `propagate`, and `trace` from `opentelemetry`. In `RequestIdMiddleware.dispatch()`:
   - Check `current_span = trace.get_current_span()` and `span_ctx = current_span.get_span_context()`.
   - If `not span_ctx.is_valid`, extract inbound trace context using `extracted_ctx = propagate.extract(request.headers)`; if `trace.get_current_span(extracted_ctx).get_span_context().is_valid`, attach with `otel_token = context.attach(extracted_ctx)` and update `span_ctx`.
   - Compute `active_trace_id = trace.format_trace_id(span_ctx.trace_id) if span_ctx.is_valid else None`.
   - Extract `header_request_id = (request.headers.get("X-Request-ID") or "").strip() or None`.
   - Set `request_id = header_request_id or active_trace_id or str(uuid.uuid4())`.
   - Store `request.state.request_id = request_id` and `token = set_request_id(request_id)`.
   - In response handling, set `response.headers["X-Request-ID"] = request_id`.
   - In `finally`: reset `request_id_ctx_var.reset(token)` and conditionally detach `if otel_token is not None: context.detach(otel_token)`.
4. In `tests/test_logging.py`, add tests:
   - `test_json_formatter_carries_trace_id_and_deploy_id`: verifies `JsonFormatter` outputs `trace_id` and `deploy_id` fields.
   - `test_request_id_filter_unifies_with_active_span`: starts a span via `get_tracer().start_as_current_span()`, filters a record, and verifies `record.trace_id == record.request_id == active_trace_id` and `record.deploy_id == settings.deploy_id`.
   - `test_request_id_filter_fallback_without_span`: verifies `record.trace_id == "-"` and `record.deploy_id == settings.deploy_id` when no span is active.
   - `test_dev_rich_handler_with_unified_trace_id`: verifies `FallbackRichHandler` renders a log record containing a unified trace ID cleanly.
5. In `tests/test_request_id.py`, add tests:
   - `test_request_id_inbound_traceparent_propagation`: sends `traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01` to `/api/ping` and asserts `response.headers["X-Request-ID"] == "4bf92f3577b34da6a3ce929d0e0e4736"`.
   - `test_request_id_inbound_x_request_id_honoured_with_traceparent`: sends `X-Request-ID: custom-req-id` and `traceparent`, asserting `response.headers["X-Request-ID"] == "custom-req-id"` while caplog logs carry `request_id == "4bf92f3577b34da6a3ce929d0e0e4736"`.
   - `test_request_id_under_active_server_span`: runs `/api/ping` within `tracer.start_as_current_span("server.request")`, asserting response `X-Request-ID` and access log `request_id` match the span trace ID.
   - `test_single_access_log_line_per_request`: asserts exactly one access log line is emitted from `src.core.middleware` for a request.
6. Run verification suite:
   - Run `./scripts/agent-test --gate0-only` to ensure Ruff linting and Ty typing pass with 0 errors.
   - Run `./scripts/agent-test tests/test_request_id.py tests/test_logging.py tests/test_observability.py`.
   - Run `./scripts/agent-test --backend` for full regression pass.

**Verification:**
- `./scripts/agent-test --gate0-only`: Ruff lint and Ty type checks pass cleanly with zero errors.
- `./scripts/agent-test tests/test_logging.py`: Targeted unit tests verify that `JsonFormatter` outputs `trace_id` and `deploy_id` on every record, `RequestIdFilter` unifies `request_id` with `trace_id` under an active span, falls back cleanly to contextvar or `"-"` when inactive, and dev rich output renders without formatting errors.
- `./scripts/agent-test tests/test_request_id.py`: Targeted tests verify that:
  1. Requests handled inside an active span produce JSON access logs where `request_id == trace_id`.
  2. Inbound `X-Request-ID` is honoured and returned on the response header.
  3. Inbound W3C `traceparent` is parsed and returned on `X-Request-ID` when `X-Request-ID` is omitted.
  4. Exactly one access-log line per request is emitted.
  5. Requests without correlation headers continue to generate and return a valid UUID.
- `./scripts/agent-test --backend`: Full backend regression suite passes under `ENVIRONMENT=test` with zero socket/network activity and no broken contracts.

**Risks / watch-outs:**
- **Context detachment leak prevention**: Any attached OTel token in `RequestIdMiddleware` must be detached in a `finally` block guarded by `if otel_token is not None:` to prevent context bleeding across asyncio tasks.
- **Outer server span coexistence**: In preparation for F-OBS-T05 (FastAPI auto-instrumentation), `RequestIdMiddleware` must check whether a server span is already active before extracting/attaching inbound headers so it never overwrites the server span with its parent context.
- **Hermetic test isolation**: `opentelemetry.propagate` and `trace.get_current_span()` are in-memory operations and do not trigger network I/O. Under `ENVIRONMENT=test`, OTel exporters remain disabled via `is_telemetry_enabled()`.
- **Dev format string compatibility**: `format="[%(request_id)s] %(message)s"` requires `request_id` to be present on all log records. `RequestIdFilter` guarantees `record.request_id` is always set (`active_trace_id`, contextvar value, or `"-"`), avoiding `KeyError` in dev logs.
