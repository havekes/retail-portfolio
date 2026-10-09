## Plan

**Approach:** Implement the wide-event emitter as OpenTelemetry Span-based records (`src/observability/events.py`) exported through the existing `TracerProvider` and `RedactingSpanProcessor` pipeline established in F-OBS-T02/T04. Each `emit_event(name, **fields)` call starts and immediately finishes an event span carrying the standardized envelope (`event.name`, `trace_id`, `span_id`, `service.name`, `deploy_id`, `environment`, `timestamp`), linking to the active trace context if present, redacting all sensitive fields/patterns, and recording an event marker on the parent span. (Rejected alternative: OTLP Log Records, because OpenTelemetry Collector tail-sampling in F-OBS-T16 only operates on traces, Go emitters in F-OBS-T09/T10 are span-based, and the Python SDK tracing pipeline and in-memory exporter are already bootstrapped).

**Files:**
- `src/observability/events.py` — create: Define `CATALOG_EVENTS` constant set, `EventEnvelope` dataclass, and `emit_event(name, **fields)` function. Reuses active SDK `Resource` from `TracerProvider`, links to active trace context or creates new span context, applies `redact_event_fields`, sets span attributes, and marks span status as `StatusCode.ERROR` if `error_slug` or failure outcome is present.
- `src/observability/__init__.py` — modify: Re-export `CATALOG_EVENTS`, `EventEnvelope`, and `emit_event`.
- `docs/field-dictionary.md` — create: Document the shared wide-event envelope specification, rules, conventions, and section stubs for all 9 catalog events (`http.request`, `huey.task`, `portfolio.sync.completed`, `portfolio.sync.failed`, `market.data.fetched`, `market.cache.accessed`, `alert.evaluated`, `ws.delivery`, `auth.event`).
- `tests/test_events.py` — create: Comprehensive unit tests covering single telemetry record output, envelope attributes, active trace continuation, standalone trace generation, sensitive field redaction, test environment kill-switch / no-op verification, high-cardinality type preservation, error status marking, and field dictionary documentation coverage.

**Steps:**
1. Create `src/observability/events.py`:
   - Define canonical catalog constants: `CATALOG_EVENTS: frozenset[str]` containing `http.request`, `huey.task`, `portfolio.sync.completed`, `portfolio.sync.failed`, `market.data.fetched`, `market.cache.accessed`, `alert.evaluated`, `ws.delivery`, `auth.event`.
   - Define `EventEnvelope` dataclass: holds `event_name: str`, `timestamp: datetime`, `trace_id: str`, `span_id: str`, `service_name: str`, `deploy_id: str`, `environment: str`, and `fields: dict[str, Any]`, with `to_dict()` and `to_attributes()` methods.
   - Implement SDK resource attribute helper (`_get_sdk_resource_attributes()`): extracts `service.name`, `deploy_id`, and `deployment.environment` from the active `TracerProvider.resource.attributes` without re-reading `Settings()`.
   - Implement `emit_event(name: str, **fields: Any) -> EventEnvelope`:
     - Sanitizes/redacts `fields` using `redact_event_fields(fields)` from `src.observability.redaction`.
     - Obtains tracer (`get_tracer("observability.events")`).
     - Extracts active span context (`trace.get_current_span().get_span_context()`).
     - Creates and ends an event span named `name`:
       - Sets `event.name = name`.
       - Sets `trace_id` and `span_id` attributes.
       - Sets resource attributes (`service.name`, `deploy_id`, `environment`).
       - Formats and sets `timestamp` (ISO-8601 UTC string and unix ms).
       - Sets all sanitized `fields` as span attributes (preserving primitives `str`, `int`, `float`, `bool`, and serializing nested dicts/lists).
       - If `fields` contains `error_slug` or failure outcomes (`status="failed"` / `outcome="failure"`), sets `span.set_status(StatusCode.ERROR)`.
     - If an active recording parent span exists (and is not the event span itself), also calls `current_span.add_event(name, sanitized_fields)` so trace waterfalls show the event marker.
     - Constructs and returns the `EventEnvelope`.
2. Update `src/observability/__init__.py`:
   - Re-export `CATALOG_EVENTS`, `EventEnvelope`, and `emit_event` in `__all__`.
3. Create `docs/field-dictionary.md`:
   - Document the shared envelope schema: `event.name`, `trace_id`, `span_id`, `service.name`, `deploy_id`, `environment`, `timestamp`.
   - Include a linked Table of Contents for all 9 catalog events.
   - Document a structured section stub for each event:
     - `http.request` (F-OBS-T12)
     - `huey.task` (F-OBS-T13)
     - `portfolio.sync.completed` (F-OBS-T13)
     - `portfolio.sync.failed` (F-OBS-T13)
     - `market.data.fetched` (F-OBS-T14)
     - `market.cache.accessed` (F-OBS-T14)
     - `alert.evaluated` (F-OBS-T15)
     - `ws.delivery` (F-OBS-T15)
     - `auth.event` (F-OBS-T12)
   - For each section, document event purpose, producing ticket, target boundary, expected typed fields, and an example JSON payload.
4. Implement unit tests in `tests/test_events.py`:
   - `test_emit_event_produces_single_telemetry_record`: With `InMemorySpanExporter`, assert `emit_event` outputs exactly one span record carrying `event.name`, `trace_id`, `span_id`, `service.name`, `deploy_id`, `environment`, and `timestamp`.
   - `test_emit_event_preserves_arbitrary_primitive_types`: Assert string, integer, float, and boolean fields are preserved in exported span attributes.
   - `test_emit_event_shares_active_trace_context`: Calling `emit_event` within `with tracer.start_as_current_span("parent_span"):` produces a record sharing the parent span's `trace_id` and setting `parent_span_id`.
   - `test_emit_event_standalone_generates_valid_ids`: Calling `emit_event` without an active span generates valid non-empty 32-hex `trace_id` and 16-hex `span_id`.
   - `test_emit_event_applies_redaction_boundary`: Keys on sensitive list (`password`, `token`, `secret`, `api_key`, `session_id`, `email`) and pattern matches (JWT, Bearer, OTP) are masked with `[REDACTED]`, while protected keys (`provider`, `broker`) are kept intact.
   - `test_emit_event_noop_in_test_env_without_processor`: Verify that in `ENVIRONMENT=test` with no `span_processor` attached to `TracerProvider`, `emit_event` executes cleanly with zero exceptions and zero network I/O.
   - `test_emit_event_error_status_marking`: Verify spans with `error_slug` or failure status have `StatusCode.ERROR` set.
   - `test_field_dictionary_covers_all_catalog_events`: Assert that `docs/field-dictionary.md` exists and contains sections for every event in `CATALOG_EVENTS`.
5. Run code verification and regression test suite:
   - Run `./scripts/agent-test --gate0-only` (Gate 0 lint and type check).
   - Run `./scripts/agent-test tests/test_events.py tests/test_observability.py tests/test_redaction.py`.
   - Run full `./scripts/agent-test` to ensure zero regressions across the backend test suite.

**Verification:**
- `./scripts/agent-test --gate0-only`: Gate 0 ruff lint and ty type checks pass cleanly with 0 errors.
- `./scripts/agent-test tests/test_events.py`: All unit tests in `tests/test_events.py` pass.
  - AC 1: `test_emit_event_produces_single_telemetry_record` and `test_emit_event_preserves_arbitrary_primitive_types` verify single telemetry record with full envelope and typed fields.
  - AC 2: `test_emit_event_queryable_by_event_name` verifies `event.name` is present in span name and attributes matching HyperDX query expectations.
  - AC 3: `test_emit_event_applies_redaction_boundary` verifies sensitive keys and values are redacted before export.
  - AC 4: `test_emit_event_noop_in_test_env_without_processor` verifies no network I/O in test environment and hermetic in-memory exporter testability.
  - AC 5: `test_field_dictionary_covers_all_catalog_events` verifies `docs/field-dictionary.md` documents envelope and all 9 catalog event sections.
- `./scripts/agent-test`: Full regression suite passes under `ENVIRONMENT=test`.
- Live HyperDX / ClickStack verification (optional manual dev runbook):
  1. Start overlay: `docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d`
  2. Emit test event from backend shell: `docker compose exec backend python -c "from src.observability import emit_event; emit_event('http.request', path='/test', status=200)"`
  3. Query ClickHouse: `docker compose exec clickstack clickhouse-client --query "SELECT SpanName, SpanAttributes['event.name'], SpanAttributes['deploy_id'] FROM default.otel_traces WHERE SpanAttributes['event.name'] = 'http.request'"` -> returns 1 row.
  4. Search in HyperDX UI (http://localhost:8080): enter query `event.name:http.request` -> event appears.

**Risks / watch-outs:**
- **Attribute type compliance in OpenTelemetry**: OTel span attributes require primitive types (`str`, `bool`, `int`, `float`) or sequences thereof. Dicts or objects passed to `emit_event` must be serialized (e.g. to JSON strings) and `None` values omitted/converted so attribute setting never raises runtime errors.
- **Traceparent / Context continuity**: When an active span exists, `tracer.start_span` automatically links to `trace.get_current_span()`. When no span is active, it must generate a clean root context rather than failing or dropping the event.
- **Resource caching**: Reusing SDK resource attributes from `_state.active_provider.resource` avoids re-instantiating `Settings()` on every emission, keeping the call-site lightweight and performant.
