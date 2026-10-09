## Plan

**Approach:** Implement a lightweight, modular OpenTelemetry SDK initialization package in `src/observability/` providing `bootstrap_observability()` and `shutdown_observability()`, configured via Pydantic settings in `src/config/settings.py`. Configure an `OTLPSpanExporter` (HTTP protobuf targeting the ClickStack collector on port 4318) and `BatchSpanProcessor` only when telemetry is actively enabled (`environment != 'test'`, not `otel_sdk_disabled`, and `otel_exporter_otlp_endpoint` configured); when in test mode or unconfigured, select a non-exporting path to keep pytest hermetically isolated without network I/O. Hook bootstrap and shutdown into the FastAPI lifespan (`src/main.py`) for `service.name="backend"` and Huey startup/shutdown signals (`src/worker.py`) for `service.name="worker"`, creating a startup smoke span (`backend.startup` / `worker.startup`) to ensure spans are immediately exported and verified.

*Alternative rejected:* Configuring OTel solely via automatic environment variable detection was rejected because distinct process identities (`service.name="backend"` vs `service.name="worker"`), explicit graceful flush on shutdown hooks, and the strict pytest hermetic kill-switch require programmatic lifecycle management.

**Files:**
- `pyproject.toml` — modify: Add `opentelemetry-api>=1.27.0`, `opentelemetry-sdk>=1.27.0`, and `opentelemetry-exporter-otlp-proto-http>=1.27.0` to `dependencies`.
- `uv.lock` — modify: Update lockfile via `uv lock` (or `docker compose exec backend uv lock`) for new OTel dependencies.
- `.env.example` — modify: Add documented `# OTEL_SDK_DISABLED=false` and `# DEPLOY_ID=dev` in the observability configuration section.
- `docker-compose.observability.yml` — modify: Pass `OTEL_SDK_DISABLED` and `DEPLOY_ID` environment variables through to `backend` and `worker` services.
- `src/config/settings.py` — modify: Add `otel_sdk_disabled: bool = False`, `otel_exporter_otlp_endpoint: str | None = None`, `otel_exporter_otlp_headers: str | None = None`, `deploy_id: str = "dev"`, and `service_version: str = "0.0.0"` fields to `Settings`.
- `src/observability/__init__.py` — create: Export `bootstrap_observability`, `shutdown_observability`, `get_tracer`, `reset_observability`, and `is_telemetry_enabled`.
- `src/observability/bootstrap.py` — create: Implement `create_resource(service_name, settings)`, `parse_otlp_headers(headers_str)`, `is_telemetry_enabled(settings)`, `bootstrap_observability(service_name, settings, span_processor)`, `shutdown_observability()`, `reset_observability()`, and `get_tracer(name)`. Guard exporter imports so importing `src.observability` has zero side effects.
- `src/main.py` — modify: In `lifespan_context(app)`, call `bootstrap_observability(service_name="backend")`, emit a `backend.startup` smoke span, and call `shutdown_observability()` upon lifespan exit.
- `src/worker.py` — modify: In `setup_worker_services()`, call `bootstrap_observability(service_name="worker")` and emit a `worker.startup` smoke span; in `teardown_worker_services()`, call `shutdown_observability()`.
- `tests/test_observability.py` — create: Add unit tests for settings defaults, kill-switch behavior (`ENVIRONMENT=test`, `OTEL_SDK_DISABLED=true`, missing endpoint), resource attributes stamping (`service.name`, `service.version`, `deployment.environment`, `deploy_id`), worker vs backend service name distinction, explicit span creation with `InMemorySpanExporter`, OTLP header string parsing, and graceful flush/shutdown.
- `tests/test_settings.py` — modify: Add unit tests validating OTel settings fields and env var overrides.

**Steps:**
1. Update `pyproject.toml` to add `opentelemetry-api>=1.27.0`, `opentelemetry-sdk>=1.27.0`, and `opentelemetry-exporter-otlp-proto-http>=1.27.0` to `dependencies`. Run `uv lock` to update `uv.lock`.
2. Update `.env.example` to document `# OTEL_SDK_DISABLED=false` and `# DEPLOY_ID=dev`. In `docker-compose.observability.yml`, forward `OTEL_SDK_DISABLED` and `DEPLOY_ID` to `backend` and `worker` service environments.
3. In `src/config/settings.py`, add `otel_sdk_disabled: bool = False`, `otel_exporter_otlp_endpoint: str | None = None`, `otel_exporter_otlp_headers: str | None = None`, `deploy_id: str = "dev"`, and `service_version: str = "0.0.0"` to `Settings`. Update `tests/test_settings.py` with unit tests for these settings.
4. Implement `src/observability/bootstrap.py` and `src/observability/__init__.py`:
   - `create_resource(service_name, settings)`: Instantiates `Resource` with `service.name`, `service.version`, `deployment.environment`, and `deploy_id`, merging with environment resource attributes.
   - `parse_otlp_headers(headers_str)`: Parses comma-delimited `key=value` strings (such as `authorization=<api-key>`) into a dictionary for `OTLPSpanExporter`.
   - `is_telemetry_enabled(settings)`: Returns `False` if `settings.environment == "test"`, if `settings.otel_sdk_disabled` is True, if env `OTEL_SDK_DISABLED` is truthy, or if `settings.otel_exporter_otlp_endpoint` is unset/empty; returns `True` only when active.
   - `bootstrap_observability(service_name="backend", settings=None, span_processor=None)`: Creates `TracerProvider(resource=resource)`. If `span_processor` is supplied (for testing), adds it. Else if `is_telemetry_enabled(settings)` is True, lazily imports and configures `OTLPSpanExporter(endpoint=endpoint, headers=headers)` and `BatchSpanProcessor`, adding it to the provider. Otherwise adds no processor (no-op/non-exporting). Sets global tracer provider via `trace.set_tracer_provider()`.
   - `shutdown_observability()`: Flushes and shuts down the active `TracerProvider`.
   - `reset_observability()`: Helper for test isolation to shut down and reset global tracer state.
   - `get_tracer(name)`: Convenience accessor returning `trace.get_tracer(name)`.
5. Integrate with FastAPI lifespan in `src/main.py`:
   - In `lifespan_context(app: FastAPI)`: Call `bootstrap_observability(service_name="backend")`. Emit a `backend.startup` smoke span (`tracer = get_tracer("src.main"); with tracer.start_as_current_span("backend.startup") as span: span.set_attribute("startup.status", "ok")`).
   - At end of `lifespan_context`: Call `shutdown_observability()`.
6. Integrate with Huey worker in `src/worker.py`:
   - In `setup_worker_services()`: Call `bootstrap_observability(service_name="worker")`. Emit a `worker.startup` smoke span (`tracer = get_tracer("src.worker"); with tracer.start_as_current_span("worker.startup") as span: span.set_attribute("startup.status", "ok")`).
   - In `teardown_worker_services()`: Call `shutdown_observability()`.
7. Create comprehensive tests in `tests/test_observability.py`:
   - Test kill switch: When `settings.environment == "test"` or `OTEL_SDK_DISABLED=true` or endpoint is empty, no exporter or processor is added and no network sockets are opened.
   - Test resource attributes: Verify `service.name`, `service.version`, `deployment.environment`, and `deploy_id` are set on the `Resource`.
   - Test distinct service names: Verify `backend` and `worker` create distinct `service.name` attributes.
   - Test in-memory span export: Using `SimpleSpanProcessor(InMemorySpanExporter())`, create an explicit span and verify all resource attributes and span attributes are preserved.
   - Test shutdown: Verify `shutdown_observability()` flushes and shuts down the provider without error.
   - Test header parsing: Verify `parse_otlp_headers` correctly handles empty, single, and multiple header pairs with whitespace.
8. Execute verification and regression test suite: Run `./scripts/agent-test --gate0-only`, `./scripts/agent-test tests/test_observability.py`, and the full `./scripts/agent-test` suite. Then verify live export against ClickStack in ClickHouse with the observability overlay running.

**Verification:**
- `./scripts/agent-test --gate0-only`: Ruff lint and ty type checks pass cleanly with zero errors.
- `./scripts/agent-test tests/test_observability.py tests/test_settings.py`: Targeted unit tests verify kill-switch, resource attributes, distinct backend/worker service names, and in-memory export.
- `./scripts/agent-test`: Full regression suite passes under `ENVIRONMENT=test` with zero socket/network activity and no changes to existing logging output or behavior.
- Live ClickStack verification (with overlay running):
  1. Start overlay: `docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d`
  2. Set `.env`: `OTEL_EXPORTER_OTLP_ENDPOINT=http://clickstack:4318` (and `OTEL_EXPORTER_OTLP_HEADERS=authorization=<api-key>` if configured)
  3. Restart services: `docker compose restart backend worker`
  4. Query ClickHouse traces: `docker compose exec clickstack clickhouse-client --query "SELECT service_name, count() FROM otel_traces GROUP BY service_name"` -> Observe both `backend` and `worker` present with counts > 0.
  5. Inspect span resource attributes: `docker compose exec clickstack clickhouse-client --query "SELECT service_name, resource_attributes FROM otel_traces LIMIT 2"` -> Observe `service.name`, `deployment.environment`, and `deploy_id` correctly stamped on the records.

**Risks / watch-outs:**
- **Test hermeticity**: Pytest fixtures in `tests/conftest.py` set `ENVIRONMENT=test`. If `bootstrap_observability` does not strictly short-circuit in test mode, the lifespan manager in router tests would attempt real HTTP/OTLP calls. Guarding with `is_telemetry_enabled()` checking `settings.environment == "test"` prevents this.
- **OTel global provider reassignment**: Calling `trace.set_tracer_provider()` multiple times in the same Python process logs warnings. Providing `reset_observability()` and wrapping in clean test lifecycle ensures test suites run cleanly.
- **OTLP/HTTP endpoint path**: In OTel HTTP protocol, spans post to `/v1/traces`. Normalize `otel_exporter_otlp_endpoint` so that if `http://clickstack:4318` is provided, it consistently addresses `http://clickstack:4318/v1/traces`.
- **Preserve existing logging**: Keep `init_logging()` in `src/config/logging.py` completely unchanged and do not add duplicate logging handlers or modify `RequestIdMiddleware`.
