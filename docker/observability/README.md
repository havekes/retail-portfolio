# Observability Overlay Runbook (ClickStack + tail sampling + Prometheus)

This runbook documents the local Docker Compose observability overlay introduced in ticket `F-OBS-T01` and extended in `F-OBS-T16`. The overlay adds a dev-only telemetry stack:
- **ClickStack all-in-one** (`clickhouse/clickstack-all-in-one:2.39.1`): ClickHouse, embedded OpenTelemetry Collector, MongoDB, and the HyperDX UI/API.
- **Tail-sampling gateway** (`otel/opentelemetry-collector-contrib:0.161.0`, service `otel-sampler`): owns the F-OBS-T16 sampling and decision-stamping policy and forwards the retained traces to ClickStack.
- **Prometheus** (`prom/prometheus:v3.13.4`): Scrapes itself and the OpenTelemetry Collector metrics on port 8888.

The overlay is strictly opt-in via Compose profiles. A plain `docker compose up` or `just up` starts only the core dev services without starting observability containers or requiring any new environment variables.

---

## 1. Quick Start

### Start the observability overlay
```bash
just obs-up
# or:
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability up -d
```

### Stop the observability overlay
```bash
just obs-down
# or:
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability down
```

With the overlay active, application telemetry (`backend`, `worker`, `frontend`, `indicator-service`) is routed to `otel-sampler:4318` instead of directly to ClickStack, so every stored wide event carries the applied sampling decision. Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://clickstack:4318` in the root `.env` to bypass the gateway for raw, unsampled debugging.

---

## 2. First-Run Setup: HyperDX User & Ingestion API Key

ClickStack OSS uses an OpAMP-managed OpenTelemetry Collector. The collector activates OTLP listening ports (`4317` gRPC and `4318` HTTP) and authenticates telemetry requests once at least one team has an API key.

1. **Access the HyperDX UI**:
   Open [http://localhost:8080](http://localhost:8080) (or the port set by `CLICKSTACK_UI_PORT`).
2. **Create the First User**:
   Register the initial account. This creates the primary team in the local database and establishes the default ClickHouse data source connection.
3. **Obtain the Ingestion API Key**:
   Navigate to **Team Settings → API Keys** in the UI and copy your team's API key.
4. **Configure `.env`**:
   Add the API key to your root `.env`:
   ```bash
   HYPERDX_API_KEY="<your-api-key>"
   ```
   The tail-sampling gateway forwards it as the `authorization` header to ClickStack. Until it is set (or while it is wrong), the sampler still starts and buffers, but ClickStack rejects the batches — ingestion stays inert and the exporter retries. Application SDKs keep exporting to the gateway unconditionally.

---

## 3. Verifying Ingestion (Hand-Sent Test Payloads)

Payloads must be sent through the gateway (`otel-sampler:4318`) so they exercise the sampling policy. The gateway owns only the **traces** pipeline — that is exactly what the application SDKs export (`src/observability/bootstrap.py`); OTLP logs or metrics posted to it are not forwarded. Each hand-sent payload is one single-span trace, the smallest unit the tail sampler can decide on.

### HTTP / JSON OTLP intake (Port 4318)
Send a test wide-event trace (a `http.request` with a 500 status, so the retention policy keeps it):
```bash
docker compose exec clickstack curl -i -s -X POST http://otel-sampler:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [
      {
        "resource": {
          "attributes": [
            {"key": "service.name", "value": {"stringValue": "test-service"}}
          ]
        },
        "scopeSpans": [
          {
            "scope": {"name": "observability.events"},
            "spans": [
              {
                "traceId": "0123456789abcdef0123456789abcdef",
                "spanId": "0123456789abcdef",
                "name": "http.request",
                "kind": 1,
                "startTimeUnixNano": "1727632800000000000",
                "endTimeUnixNano": "1727632801000000000",
                "attributes": [
                  {"key": "event.name", "value": {"stringValue": "http.request"}},
                  {"key": "status", "value": {"intValue": "500"}}
                ],
                "status": {}
              }
            ]
          }
        ]
      }
    ]
  }'
```
Response will return `HTTP/1.1 200 OK {"partialSuccess":{}}`. Wait out the sampler's `decision_wait` (10s) before querying.

### Confirm data landed in ClickHouse
Query `default.otel_traces`:
```bash
docker compose exec clickstack clickhouse-client --query \
  "SELECT SpanName, SpanAttributes['event.name'] AS event,
          SpanAttributes['status'] AS status,
          SpanAttributes['event.sampled'] AS sampled,
          SpanAttributes['event.sample_rate'] AS sample_rate
   FROM default.otel_traces"
```
The retained span must carry `StatusCode = 'Error'` (promoted by `transform/error_marking`) and a `1` sampling rate.

### gRPC OTLP intake (Port 4317)
Verify the HTTP/2 gRPC listener:
```bash
docker compose exec clickstack curl -i -s --http2-prior-knowledge http://otel-sampler:4317/
```
The response returns `HTTP/2 415` with `content-type: application/grpc`, indicating the gRPC server is actively receiving requests.

---

## 4. Prometheus Scrapes

Prometheus runs on port `9090` (configured via `PROMETHEUS_PORT`).

### Check readiness
```bash
docker compose exec backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://prometheus:9090/-/ready').read().decode())"
```

### Check active scrape targets
```bash
docker compose exec backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://prometheus:9090/api/v1/targets').read().decode())"
```
Both `prometheus` (self) and `otel-collector` (`clickstack:8888`) targets will report `"health": "up"`.

---

## 5. Retention & TTL Policy

`docker/observability/clickhouse-ttl.sql` applies explicit retention tiers, replacing the coarse 30-day defaults from F-OBS-T01:

| Table | Tier |
| --- | --- |
| `default.otel_traces` — `market.cache.accessed` | 7 days |
| `default.otel_traces` — `http.request`, `market.data.fetched`, `ws.delivery` | 14 days |
| `default.otel_traces` — `auth.event`, `huey.task`, `alert.evaluated`, `portfolio.sync.completed`, `portfolio.sync.failed`, unknown | 30 days |
| `default.otel_logs` | 30 days |
| `default.otel_metrics_*` | 14 days |

The trace tier is a **row-level TTL expression** — a `multiIf` on `SpanAttributes['event.name']` — so one table carries several tiers and each event class expires on its own schedule.

Apply (or re-apply) the policy:
```bash
docker compose exec -T clickstack clickhouse-client --multiquery < docker/observability/clickhouse-ttl.sql
```

Verify it is visible on the table:
```bash
docker compose exec clickstack clickhouse-client --query "SHOW CREATE TABLE default.otel_traces"
```
The `TTL` clause must read `toDateTime(Timestamp) + toIntervalDay(multiIf(...))` with the per-class branches (the flat `+ INTERVAL 30 DAY` form is gone).

---

## 6. Tail Sampling Policy

The application emitters always emit; sampling happens **only** in the gateway. ClickStack's all-in-one embedded collector accepts additive custom config but cannot rewire its built-in `traces` pipeline, so the `otel-sampler` service owns the policy (`docker/observability/otelcol-sampling.yaml`):

| Order | Policy | Type | Effect |
| --- | --- | --- | --- |
| 1 | `errors-all` | `status_code` | Retains 100% of traces containing a span with status `ERROR` |
| 2 | `error-slug-present` | `string_attribute` (`error_slug`, regex `.+`) | Retains 100% of traces carrying a non-empty `error_slug` |
| 3 | `success-bulk` | `probabilistic` | Retains `OTEL_SAMPLER_SUCCESS_PERCENT`% (default **7**, band **5-10**) of everything else |

Tail sampling stops at the first matching policy, so the probabilistic bulk can never shadow a failure.

`transform/error_marking` runs *before* the sampler and promotes the wide-event failure signals to span status `ERROR`, mirroring `_error_reason()` in `src/observability/events.py`: a truthy `error_slug`, an `outcome` of `failed`/`failure`/`error`, and — because an int `status` is invisible to the application-side heuristic — `http.request` with `status == 500`.

`transform/sampling_stamp` then writes the applied decision onto every retained span: `event.sampled=true` plus `event.sample_rate` (`1` for the error cohorts, the bulk percentage otherwise). Analyses over stored traces can therefore reason about representativeness instead of assuming "everything is here".

> **Trace-bound caveat**: tail sampling decides per **trace**, not per span. A wide event emitted while a parent span is active (for example `http.request` inside a request trace) shares the parent trace's decision and stamp. Standalone events are single-span traces, so the percentage applies per record for them.

### Configuration knobs

| Variable | Default | Meaning |
| --- | --- | --- |
| `HYPERDX_API_KEY` | *(empty)* | Team ingestion key the gateway sends as `authorization` to ClickStack. Without it the sampler runs but inserts are rejected upstream. |
| `OTEL_SAMPLER_SUCCESS_PERCENT` | `7` | Percentage of the successful bulk retained. Keep inside the 5-10 band. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-sampler:4318` | Overlay default; set to `http://clickstack:4318` to bypass the gateway. |

### Manual verification runbook

Requires a running overlay with a valid `HYPERDX_API_KEY` (README § 2).

1. **Start the stack** (`just obs-up`) and confirm the gateway is healthy:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability logs otel-sampler | tail -5
   ```
   The log ends with `Everything is ready. Begin running and processing data.` and shows no `Exporting failed` retries.

2. **Send the deterministic burst** through the gateway (100 successes, 20 int-500 failures, 20 `outcome=failure` events, all single-span traces):
   ```bash
   docker compose exec -T backend python docker/observability/send-sampling-burst.py
   ```

3. **Wait past the decision window** (`decision_wait` is 10s, plus the 5s batch timeout) and query ClickHouse:
   ```bash
   docker compose exec clickstack clickhouse-client --query "
     SELECT
       SpanAttributes['event.name'] AS event,
       SpanAttributes['status'] AS status,
       count() AS retained
     FROM default.otel_traces
     WHERE SpanAttributes['event.name'] IN ('http.request', 'auth.event')
     GROUP BY event, status
     ORDER BY event, status"
   ```
   Expected: `http.request`/`500` → **20** (nothing dropped) and `http.request`/`200` → **~7** (7% of 100). Re-run step 2 once to confirm the success count varies inside the 5-10% band instead of being pinned to a fixed subset.

4. **Confirm the decision is stored**:
   ```bash
   docker compose exec clickstack clickhouse-client --query "
     SELECT DISTINCT
       SpanAttributes['event.name'] AS event,
       SpanAttributes['event.sampled'] AS sampled,
       SpanAttributes['event.sample_rate'] AS sample_rate
     FROM default.otel_traces
     WHERE SpanAttributes['event.name'] IN ('http.request', 'auth.event')"
   ```
   Expected: `true`/`1` for the failure cohorts and `true`/`7` for the retained successes. (Attributes are stored as strings; a `Double(1)` and an `Int(7)` both render without a decimal part.)

5. **Confirm the retention tiers** as described in § 5.

Record the observed before/after counts when running this for a release or when tuning the percentage.

---

## 7. Persistence, Teardown & Rollback

### Named volumes
Telemetry and UI states are persisted across container restarts using three named volumes:
- `clickstack_mongo_data`: HyperDX metadata (teams, users, dashboard configs)
- `clickstack_clickhouse_data`: ClickHouse tables and partition data
- `clickstack_clickhouse_log`: ClickHouse server logs

### Reset telemetry data
To completely wipe all collected logs, traces, and metrics and reset HyperDX state:
```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml --profile observability down -v
```

### Rollback
Because all observability components reside in `docker-compose.observability.yml` and `docker/observability/`, removing these files or starting services with standard `just up` or `docker compose up -d` completely decouples the base development stack from observability.

### Config-only validation
Static validation without a live stack (documented one-liner; requires the pinned image):
```bash
docker run --rm \
  -e OTEL_SAMPLER_SUCCESS_PERCENT=7 -e HYPERDX_API_KEY=test-key \
  -v ./docker/observability/otelcol-sampling.yaml:/etc/otelcol/config.yaml:ro \
  otel/opentelemetry-collector-contrib:0.161.0 \
  validate --config /etc/otelcol/config.yaml
```
Both environment variables must be set (the compose service defaults them). The parse-only policy assertions live in `tests/observability/test_sampling_config.py`.
