# Observability Overlay Runbook (ClickStack + Prometheus)

This runbook documents the local Docker Compose observability overlay introduced in ticket `F-OBS-T01`. The overlay adds a dev-only telemetry stack:
- **ClickStack all-in-one** (`clickhouse/clickstack-all-in-one:2.39.1`): ClickHouse, embedded OpenTelemetry Collector, MongoDB, and the HyperDX UI/API.
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
   OTEL_EXPORTER_OTLP_HEADERS="authorization=<your-api-key>"
   ```

---

## 3. Verifying Ingestion (Hand-Sent Test Payloads)

### HTTP / JSON OTLP intake (Port 4318)
Send a test log record to the collector:
```bash
docker compose exec clickstack curl -i -s -X POST http://localhost:4318/v1/logs \
  -H "Content-Type: application/json" \
  -H "Authorization: <your-api-key>" \
  -d '{
    "resourceLogs": [
      {
        "resource": {
          "attributes": [
            {"key": "service.name", "value": {"stringValue": "test-service"}}
          ]
        },
        "scopeLogs": [
          {
            "scope": {"name": "test-scope"},
            "logRecords": [
              {
                "timeUnixNano": "1727632800000000000",
                "severityNumber": 9,
                "severityText": "INFO",
                "body": {"stringValue": "Hand-sent test log event"},
                "attributes": [{"key": "test.key", "value": {"stringValue": "test.value"}}]
              }
            ]
          }
        ]
      }
    ]
  }'
```
Response will return `HTTP/1.1 200 OK {"partialSuccess":{}}`.

### Confirm data landed in ClickHouse
Query `default.otel_logs`:
```bash
docker compose exec clickstack clickhouse-client --query \
  "SELECT ServiceName, Body, SeverityText, LogAttributes FROM default.otel_logs"
```

### gRPC OTLP intake (Port 4317)
Verify the HTTP/2 gRPC listener:
```bash
docker compose exec clickstack curl -i -s --http2-prior-knowledge http://localhost:4317/
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

ClickStack automatically configures a default 30-day (720 hour) TTL on table creation. To explicitly re-apply or enforce coarse retention policies across telemetry tables:
```bash
docker compose exec -T clickstack clickhouse-client --multiquery < docker/observability/clickhouse-ttl.sql
```

---

## 6. Persistence, Teardown & Rollback

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
