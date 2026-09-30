## Plan

**Approach:**
Implement sink-agnostic OpenTelemetry exception capture via a dedicated `capture_exception()` helper in `src/observability/exceptions.py` that records standard OpenTelemetry exception events (`record_exception`) and error status on spans tagged with `service.name`, `deploy_id`, `release` (derived from `deploy_id`), unified `trace_id`, `task_name`/`task_id` for workers, and sanitized `user_id`. Integrate this directly into FastAPI's existing unhandled exception handlers (`catch_all_exception_handler` and `cors_exception_middleware` safety net in `src/main.py`) and Huey's task error hook (`@huey.signal(signals.SIGNAL_ERROR)` in `src/worker.py`), ensuring defense-in-depth sanitization through `RedactingSpanProcessor` and strict short-circuiting under `ENVIRONMENT=test` to prevent network calls and keep tests hermetic.

**Files:**
- `src/observability/exceptions.py` — create: Implement `capture_exception()`, `should_capture_telemetry()`, `get_parent_context()`, and safe `user_id` / task metadata extraction helpers. Handles both active recording spans and standalone error spans linked to incoming trace context or request IDs.
- `src/observability/__init__.py` — modify: Export `capture_exception` and `should_capture_telemetry` from the observability package.
- `src/main.py` — modify: Hook `capture_exception(exc, service_name="backend", request=request)` into `catch_all_exception_handler` and the `cors_exception_middleware` safety net with deduplication guard.
- `src/worker.py` — modify: Register a `@huey.signal(signals.SIGNAL_ERROR)` signal receiver (`capture_worker_task_error`) that extracts task metadata and calls `capture_exception(exc, service_name="worker", task=task)`.
- `tests/test_exception_capture.py` — create: Unit and integration tests covering unhandled backend exceptions, failing Huey tasks, trace ID correlation (traceparent and request_id), sensitive payload redaction (tokens, JWTs, broker sessions, emails), the test-environment kill switch (`ENVIRONMENT=test` no-op / zero network egress), and failure recovery.

**Steps:**
1. Create `src/observability/exceptions.py` with:
   - `is_safe_user_id(user_id: Any) -> str | None`: verifies user ID is non-empty, numeric or UUID/alphanumeric, and does not contain sensitive tokens, whitespace, or `@` email characters; returns string or `None`.
   - `get_parent_context(trace_id_str: str | None = None, headers: Mapping[str, str] | None = None) -> Context | None`: if headers contain valid W3C `traceparent`, extracts context via `propagate.extract(headers)`; if `trace_id_str` (32 hex characters or 36 char UUID) is valid, constructs a remote sampled `SpanContext` in a new `Context` to unify trace correlation.
   - `should_capture_telemetry(settings: Settings | None = None) -> bool`: returns `True` if `is_telemetry_enabled(settings)` is True; in test mode (`settings.environment == "test"`), returns `True` only if an explicit non-redacting span processor (e.g. `InMemorySpanExporter` in tests) is attached to the active `TracerProvider`, otherwise returns `False` (kill switch / hermetic test guard).
   - `capture_exception(exc: BaseException, *, service_name: str = "backend", request: Request | None = None, task: Any | None = None, user_id: Any | None = None, extra_attributes: Mapping[str, Any] | None = None, settings: Settings | None = None) -> None`:
     - Short-circuits immediately if `not should_capture_telemetry(settings)` or if `getattr(exc, "_otel_captured", False)`.
     - Marks `setattr(exc, "_otel_captured", True)` for idempotency.
     - Resolves `task_name` and `task_id` from `task` if present.
     - Resolves `safe_user_id` from `user_id`, `request.state.user_id`, or `task.kwargs/task.args`.
     - Resolves `trace_id` and parent context from active span, `request.state.request_id`, request headers, `task.kwargs.get("request_id")`, or contextvar `get_request_id()`.
     - Builds attributes dictionary: `service`, `service.name`, `deploy_id`, `release` (set to `settings.deploy_id`), `trace_id`, optional `task_name`, `task.name`, `task_id`, `task.id`, and `user_id`. Applies `redact_event_fields()`.
     - Checks `current_span = trace.get_current_span()`. If recording, sets attributes, calls `current_span.record_exception(exc, attributes=attributes)`, and sets status to `StatusCode.ERROR`. If not recording, starts span with `tracer.start_as_current_span(name=span_name, context=parent_context)` using `get_tracer("src.observability.exceptions")`, sets attributes, records exception, sets error status, and ends span.
     - Wraps entire function body in `try...except Exception:` to guarantee exception capture never throws secondary errors or masks application exceptions.
2. In `src/observability/__init__.py`, import and re-export `capture_exception` and `should_capture_telemetry` in `__all__`.
3. In `src/main.py`:
   - Import `capture_exception` from `src.observability`.
   - In `catch_all_exception_handler(request: Request, exc: Exception)`: call `capture_exception(exc, service_name="backend", request=request)`.
   - In `cors_exception_middleware(request: Request, call_next: Any)`: in the `except Exception as exc:` block, call `capture_exception(exc, service_name="backend", request=request)`.
4. In `src/worker.py`:
   - Import `signals` from `huey`.
   - Import `capture_exception` from `src.observability`.
   - Register `@huey.signal(signals.SIGNAL_ERROR)` receiver `capture_worker_task_error(signal, task, exc=None)`. If `exc is not None`, calls `capture_exception(exc, service_name="worker", task=task)`. If `exc is None`, inspects `sys.exc_info()[1]` (or constructs a fallback `RuntimeError`) and captures it.
5. In `tests/test_exception_capture.py`, implement tests:
   - `test_unhandled_backend_exception_captured_with_metadata`: creates test app with route raising `RuntimeError`, triggers request with `traceparent`, and asserts finished span has `service.name == "backend"`, `deploy_id == settings.deploy_id`, `release == settings.deploy_id`, matching `trace_id`, and `exception` event with type, message, and stack trace.
   - `test_failing_huey_task_captured_with_task_name_and_trace_id`: sets up Huey task raising error with `request_id` in kwargs, emits `SIGNAL_ERROR` / executes task, and asserts finished span has `service.name == "worker"`, `task_name`, `task_id`, and matching `trace_id`.
   - `test_exception_payload_redaction`: verifies that exceptions containing Bearer tokens, JWT strings, broker session tokens, passwords, API keys, and email addresses in exception message and stack trace are thoroughly scrubbed with `[REDACTED]` mask.
   - `test_user_id_safe_capture_and_email_rejection`: asserts numeric and UUID user IDs are recorded as `user_id` attribute, whereas email strings are not captured as user_id.
   - `test_test_env_kill_switch_no_capture_and_no_egress`: under `ENVIRONMENT=test` with no test processor attached, asserts `should_capture_telemetry()` returns `False` and `capture_exception()` does not create or export spans.
   - `test_otel_sdk_disabled_kill_switch`: asserts `capture_exception()` is inert when `OTEL_SDK_DISABLED=1`.
   - `test_exception_capture_resilience`: verifies that passing malformed inputs to `capture_exception` swallows errors gracefully without re-raising.
6. Run Gate 0 pre-flight and regression test suite:
   - Run `./scripts/agent-test --gate0-only` to ensure Ruff lint and Ty type checks pass.
   - Run `./scripts/agent-test tests/test_exception_capture.py tests/test_observability.py tests/test_redaction.py tests/test_main.py`.
   - Run `./scripts/agent-test --backend` for full regression pass.

**Verification:**
- `./scripts/agent-test --gate0-only`: Ruff lint and Ty type checks pass with 0 errors.
- `./scripts/agent-test tests/test_exception_capture.py`: Targeted tests verify:
  1. Backend unhandled exceptions appear in the error inbox (OTel span event) with `service.name="backend"`, `deploy_id`, `release`, and unified `trace_id` (AC1).
  2. Failing Huey tasks appear in the error inbox with `service.name="worker"`, `task_name`, `task_id`, and unified `trace_id` (AC2).
  3. Redaction boundary scrubs Bearer tokens, JWTs, broker sessions, API keys, passwords, and email addresses from `exception.message`, `exception.stacktrace`, and attributes (AC3).
  4. Under `ENVIRONMENT=test` (default), no spans are captured or exported, no sockets are opened, and no network calls are made (AC4).
- `./scripts/agent-test tests/test_main.py tests/test_observability.py tests/test_redaction.py`: Ensures existing main error logging, observability bootstrap, and redaction tests continue to pass without regression.
- `./scripts/agent-test --backend`: Full backend regression suite passes under `ENVIRONMENT=test` (AC5).
- Live ClickStack verification (optional manual verification runbook):
  1. Start observability overlay: `docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d`
  2. Configure `.env`: `OTEL_EXPORTER_OTLP_ENDPOINT=http://clickstack:4318`
  3. Trigger test error: hit an unhandled endpoint or trigger a failing worker task.
  4. Query ClickHouse: `docker compose exec clickstack clickhouse-client --query "SELECT Timestamp, ServiceName, SpanName, StatusCode, Events.Name, Events.Attributes['exception.type'], Events.Attributes['deploy_id'], Events.Attributes['trace_id'] FROM otel_traces WHERE StatusCode = 'STATUS_CODE_ERROR' LIMIT 5 FORMAT Vertical"` -> Verify presence of exception record with expected tags.

**Risks / watch-outs:**
- **Test hermeticity**: In pytest, `ENVIRONMENT=test`. If `capture_exception()` did not short-circuit when unconfigured, it could attempt network egress or slow down test execution. Guarding with `should_capture_telemetry()` ensures zero network activity during standard test execution.
- **Idempotency across middleware and exception handlers**: In FastAPI, both `catch_all_exception_handler` and `cors_exception_middleware` handle errors. Tagging the exception with `_otel_captured = True` prevents double-recording if an exception passes through both handlers.
- **Trace context continuity**: Worker tasks may execute asynchronously without an active ambient span. Linking the task exception span to the parent trace context via `task.kwargs["request_id"]` ensures worker errors correlate directly to the user HTTP request that enqueued them.
- **Exception capture safety**: Error handling code must never raise secondary exceptions. `capture_exception()` wraps all its internal operations in a catch-all `try...except Exception:` to ensure the primary HTTP response or worker cleanup always proceeds undisturbed.
