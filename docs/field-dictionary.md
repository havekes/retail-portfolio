# Wide-event field dictionary

Every catalog event is emitted with `src.observability.emit_event(name, **fields)` and lands in
ClickStack (ClickHouse) as one OpenTelemetry span named after the event. This document is the
contract for the **shared envelope** plus the typed fields each catalog event is expected to carry.

Emitting code: `src/observability/events.py`.
Redaction boundary: `src/observability/redaction.py` (`RedactingSpanProcessor`).

## Envelope

Every event — regardless of name — carries exactly these attributes. They are set by
`emit_event`, not by call sites.

| Attribute                 | Type   | Description                                                                 |
| ------------------------- | ------ | --------------------------------------------------------------------------- |
| `event.name`              | string | Catalog event name (also the exported span name).                           |
| `trace_id`                | string | 32-hex W3C trace id; equals the active trace's id, or a new root trace id.   |
| `span_id`                 | string | 16-hex span id of the event's own span.                                      |
| `parent_span_id`          | string | 16-hex id of the enclosing span. Only present when there is an active span.  |
| `service.name`            | string | Emitting process (`backend`, `worker`, ...) from the SDK resource.           |
| `deploy_id`               | string | Deployment identifier stamped by the SDK resource.                          |
| `environment`             | string | `deployment.environment` from the SDK resource (`dev`, `test`, `prod`).     |
| `timestamp`               | string | ISO-8601 UTC timestamp taken at emission time.                               |
| `timestamp_unix_millis`   | int    | The same instant as Unix epoch milliseconds.                                 |

## Rules and conventions

- **One event, one telemetry record.** `emit_event` never emits more than one span. When an active
  span exists, a marker event is also attached to that parent span so the event shows up in the
  trace waterfall; the marker is not a second record.
- **Transport.** Wide events are span records, not OTLP log records: tail-based sampling
  (F-OBS-T16) only operates on traces, and the Go emitters are span-based.
- **Attribute typing.** `str`, `int`, `float` and `bool` values are exported as-is. `None` values
  are dropped. Homogeneous primitive sequences are exported as sequences; any other nested
  structure (dict, heterogeneous list, object) is JSON-serialized to a string.
- **Failure marking.** An event whose fields contain a truthy `error_slug`, or `status`/`outcome`
  of `failed`, `failure` or `error`, has span status `ERROR` set, so the sampling policy treats it
  as an error and always retains it.
- **Redaction.** All `fields` pass through `redact_event_fields` before export: sensitive keys
  (`password`, `token`, `secret`, `api_key`, `session_id`, `email`, ...) are masked with
  `[REDACTED]`, and token/JWT/bearer/OTP/email patterns are scrubbed from string values.
  `provider`, `broker` and other `PROTECTED_KEYS` are internal telemetry dimensions and are kept.
- **Provider names.** Upstream provider/broker identity is allowed here (operator-only store) and
  must never be copied into a user- or agent-facing surface.
- **Test safety.** Under `ENVIRONMENT=test` no exporter is attached, so emission is a no-op with no
  network I/O; unit tests attach an in-memory exporter instead.

## Querying

Events are queryable by `event.name` in HyperDX (`event.name:portfolio.sync.completed`) and in
ClickHouse directly:

```sql
SELECT Timestamp, SpanAttributes['event.name'], SpanAttributes['deploy_id']
FROM default.otel_traces
WHERE SpanAttributes['event.name'] = 'portfolio.sync.completed'
```

## Catalog events

| Event                                                             | Producing ticket |
| ----------------------------------------------------------------- | ---------------- |
| [`http.request`](#httprequest)                                     | F-OBS-T12        |
| [`auth.event`](#authevent)                                         | F-OBS-T12        |
| [`huey.task`](#hueytask)                                           | F-OBS-T13        |
| [`portfolio.sync.completed`](#portfoliosynccompleted)              | F-OBS-T13        |
| [`portfolio.sync.failed`](#portfoliosyncfailed)                    | F-OBS-T13        |
| [`market.data.fetched`](#marketdatafetched)                        | F-OBS-T14        |
| [`market.cache.accessed`](#marketcacheaccessed)                    | F-OBS-T14        |
| [`alert.evaluated`](#alertevaluated)                               | F-OBS-T15        |
| [`ws.delivery`](#wsdelivery)                                       | F-OBS-T15        |

Each section below lists the event's purpose, its emitting boundary, and the typed fields it is
expected to carry **in addition to the shared envelope**. Fields marked _(required)_ are the
minimum an implementation must emit; later tickets may add fields without a breaking change.

## `http.request`

- **Purpose:** one record per inbound HTTP request, for latency and status cohort analysis.
- **Producing ticket:** F-OBS-T12.
- **Boundary:** `src/core/middleware.py`, `RequestIdMiddleware.dispatch` — the same point as the
  existing access log, which stays unchanged (still exactly one line per request). The event is
  emitted on the success path and, with `status=500`, when the request raises.

| Field                     | Type   | Notes                                                              |
| ------------------------- | ------ | ------------------------------------------------------------------ |
| `route` _(required)_      | string | Matched route template, never the raw path with identifiers.        |
| `method` _(required)_     | string | HTTP method.                                                       |
| `status` _(required)_     | int    | Response status code (`500` when the request raised).               |
| `duration_ms` _(required)_| float  | Request duration in milliseconds.                                  |
| `request_bytes`           | int    | Request `content-length`; omitted when the request had no body.      |
| `response_bytes`          | int    | Response `content-length`; omitted for streamed/chunked responses.   |
| `user_id`                 | string | Present when the request's token decoded; no database lookup runs.    |
| `client_host`             | string | Client host, or `unknown` when the ASGI server provided none.         |

**Route label.** `route` is the `path` of the matched Starlette route. App-level routes keep their
path (`/api/ping`); routes declared on an included `APIRouter` are recorded relative to that
router's prefix (`/auth/login`). When no route matched — `404` and friends — the event carries
`route="unmatched"`; the raw URL path is never emitted.

**Identity.** `user_id` comes from decoding the `auth_token` cookie or the `Authorization: Bearer`
header with the JWT-only `UserApi.decode_token` — no database or revocation check runs on this
boundary, and any decode failure leaves the field absent.

```json
{
  "event.name": "http.request",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "service.name": "backend",
  "deploy_id": "1a2b3c4",
  "environment": "prod",
  "timestamp": "2026-09-29T10:15:00.123456+00:00",
  "route": "/accounts/{account_id}/holdings",
  "method": "GET",
  "status": 200,
  "duration_ms": 42.7,
  "response_bytes": 1873,
  "client_host": "203.0.113.7",
  "user_id": "9f8b7c6d-5e4f-4a3b-9c2d-1e0f2a3b4c5d"
}
```

An unmatched route emits the same shape with `"route": "unmatched"` and `"status": 404`.

## `auth.event`

- **Purpose:** authentication boundary outcomes (login, 2FA verification, passkey login).
- **Producing ticket:** F-OBS-T12.
- **Boundary:** `src/auth/router.py` (`_emit_auth_event`) at the login, 2FA-verify and passkey-login
  success and failure paths, alongside the existing `auth.*` log records (unchanged).

| Field                        | Type   | Notes                                                        |
| ---------------------------- | ------ | ------------------------------------------------------------- |
| `outcome` _(required)_       | string | `success`, `failure` or `challenge` (2FA challenge issued).    |
| `event_type` _(required)_    | string | `login`, `2fa_verify` or `passkey_login`.                      |
| `user_id`                    | string | Present on success (the authenticated user); absent on failure. |
| `failure_reason`             | string | Failure class only — never a credential or PII value.          |

`failure_reason` is one of: `invalid_credentials`, `email_unverified` (login); `token_invalid`,
`user_inactive`, `code_invalid` (2FA verification); `verification_failed` (passkey login).
`outcome="failure"` marks the span `ERROR`, so every failed attempt is retained unconditionally.

No password, email address, OTP code or token value may be part of this event.

```json
{
  "event.name": "auth.event",
  "outcome": "challenge",
  "event_type": "login"
}
```

```json
{
  "event.name": "auth.event",
  "outcome": "failure",
  "event_type": "2fa_verify",
  "failure_reason": "code_invalid"
}
```

## `huey.task`

- **Purpose:** one record per worker task execution, for retry and failure-rate analysis.
- **Producing ticket:** F-OBS-T13.
- **Boundary:** `src/worker.py` / Huey signal handlers.

| Field             | Type   | Notes                                              |
| ----------------- | ------ | -------------------------------------------------- |
| `task_name` _(required)_ | string | Registered task name.                       |
| `task_id` _(required)_   | string | Huey task id.                               |
| `queue`                  | string | Huey queue (instance) name.                  |
| `retries`                | int    | Retry counter: `0` on the first attempt.       |
| `status` _(required)_    | string | `success`, `failed` or `interrupted`.         |
| `duration_ms` _(required)_ | float | Execution duration; omitted when no start time was recorded (e.g. a task interrupted before executing). |
| `error_slug`             | string | Present on failure; marks the span `ERROR`.  |

```json
{
  "event.name": "huey.task",
  "task_name": "sync_account_positions_task",
  "task_id": "b1f0c0d2-...",
  "queue": "retail-portfolio",
  "status": "failed",
  "retries": 1,
  "duration_ms": 1830.4,
  "error_slug": "external_api_error"
}
```

## `portfolio.sync.completed`

- **Purpose:** a successful account sync, built incrementally across provider calls and persistence.
- **Producing ticket:** F-OBS-T13.
- **Boundary:** `src/integration/task.py` (`_sync_account_positions_task`, `_do_sync_positions`).

| Field                       | Type   | Notes                                                    |
| --------------------------- | ------ | -------------------------------------------------------- |
| `account_id` _(required)_   | string | Internal account id.                                      |
| `user_id`                   | string | Owning user.                                              |
| `broker` _(required)_       | string | Internal broker dimension; never user-facing.              |
| `trigger` _(required)_      | string | `manual` or `scheduled`.                                   |
| `positions_seen` _(required)_ | int  | Positions returned by the broker.                          |
| `positions_changed` _(required)_ | int | Positions persisted as changed.                          |
| `duration_ms` _(required)_  | float  | Total sync duration.                                       |
| `provider_calls`            | object | Bounded per-provider call outcomes (JSON-serialized): `positions_fetch`, `positions_persist`, `accounts_reconcile`, `securities_resolved`. |
| `outcome` _(required)_      | string | `success` for this event.                                  |

```json
{
  "event.name": "portfolio.sync.completed",
  "account_id": "acct_42",
  "user_id": "usr_123",
  "broker": "retail-broker",
  "trigger": "manual",
  "positions_seen": 118,
  "positions_changed": 7,
  "duration_ms": 4210.9,
  "outcome": "success"
}
```

## `portfolio.sync.failed`

- **Purpose:** a failed account sync, carrying the fields the sampling policy treats as an error.
- **Producing ticket:** F-OBS-T13.
- **Boundary:** `src/integration/task.py` failure path.

| Field                     | Type   | Notes                                                        |
| ------------------------- | ------ | -------------------------------------------------------------- |
| `account_id` _(required)_ | string | Internal account id.                                           |
| `user_id`                 | string | Owning user.                                                   |
| `broker` _(required)_     | string | Internal broker dimension.                                      |
| `trigger` _(required)_    | string | `manual` or `scheduled`.                                        |
| `duration_ms` _(required)_| float  | Duration until failure.                                         |
| `outcome` _(required)_    | string | `failure` — marks the span `ERROR` (retained unconditionally).   |
| `error_slug` _(required)_ | string | Stable failure class.                                           |

```json
{
  "event.name": "portfolio.sync.failed",
  "account_id": "acct_42",
  "user_id": "usr_123",
  "broker": "retail-broker",
  "trigger": "scheduled",
  "duration_ms": 903.1,
  "outcome": "failure",
  "error_slug": "broker_unauthorized"
}
```

## `market.data.fetched`

- **Purpose:** provider and data-plane fetches, for freshness-lag and per-provider cohort analysis.
- **Producing ticket:** F-OBS-T14.
- **Boundary:** `src/market/gateway.py` (`record_fetch`), applied at the fetch call sites in
  `src/market/repository_eodhd.py`, `src/market/service.py` and `src/market/api.py`, so both the
  real EODHD gateway (`eodhd.py`) and the stubs emit through one path.

| Field                  | Type   | Notes                                              |
| ---------------------- | ------ | --------------------------------------------------- |
| `symbol` _(required)_  | string | Instrument symbol.                                  |
| `dataset` _(required)_ | string | Dataset or endpoint class (`eod`, `intraday`, `search`). |
| `provider` _(required)_| string | Internal provider dimension (kept by redaction).     |
| `exchange`             | string | Exchange code.                                      |
| `cache_state`          | string | `fresh`, `stale`, `miss`, ...                       |
| `freshness_lag_ms`     | int    | Age of the returned data.                            |
| `duration_ms` _(required)_ | float | Fetch duration.                                  |
| `outcome` _(required)_ | string | `success` or `failure` (`failure` marks the span `ERROR`). |
| `row_count`            | int    | Rows returned.                                       |
| `error_slug`           | string | Stable failure class; present on `failure` only.     |

API keys, service tokens and raw user-scoped cache keys never appear here.

```json
{
  "event.name": "market.data.fetched",
  "symbol": "AAPL",
  "dataset": "eod",
  "provider": "eodhd",
  "exchange": "US",
  "cache_state": "miss",
  "freshness_lag_ms": 1200,
  "duration_ms": 185.3,
  "outcome": "success",
  "row_count": 1
}
```

## `market.cache.accessed`

- **Purpose:** cache boundary reads, to explain stale-price cohorts by cache state.
- **Producing ticket:** F-OBS-T14.
- **Boundary:** `src/market/cache.py` (`IndicatorCache`, `SecuritySearchCache`).

| Field                     | Type   | Notes                                             |
| ------------------------- | ------ | -------------------------------------------------- |
| `cache_kind` _(required)_ | string | Which cache implementation (`indicator`, `security_search`). |
| `key_class` _(required)_  | string | Static cache-namespace label — never the raw user-scoped key. |
| `outcome` _(required)_    | string | `hit`, `miss`, `negative` or `write`.               |
| `ttl_seconds`             | int    | Configured TTL for the read/write.                  |
| `error_slug`              | string | Stable failure class (e.g. `cache_error`) on a failed read. |

```json
{
  "event.name": "market.cache.accessed",
  "cache_kind": "security_search",
  "key_class": "security_search",
  "outcome": "miss",
  "ttl_seconds": 2592000
}
```

## `alert.evaluated`

- **Purpose:** the hourly alert evaluation run.
- **Producing ticket:** F-OBS-T15.
- **Boundary:** `src/market/task.py`, `src/market/alert_service.py`.

| Field                          | Type   | Notes                                    |
| ------------------------------ | ------ | ----------------------------------------- |
| `alerts_evaluated` _(required)_| int    | Alerts evaluated in the run.               |
| `alerts_triggered` _(required)_| int    | Alerts that triggered.                     |
| `symbol_outcomes`              | object | Bounded per-symbol outcomes (JSON-serialized). |
| `duration_ms` _(required)_     | float  | Run duration.                              |
| `run_at` _(required)_          | string | ISO-8601 run timestamp.                    |
| `outcome` _(required)_         | string | `success`, `failure`, ...                   |

```json
{
  "event.name": "alert.evaluated",
  "alerts_evaluated": 64,
  "alerts_triggered": 3,
  "duration_ms": 512.0,
  "run_at": "2026-09-29T10:00:00+00:00",
  "outcome": "success"
}
```

## `ws.delivery`

- **Purpose:** WebSocket publish and delivery, closing the trace across process boundaries.
- **Producing ticket:** F-OBS-T15.
- **Boundary:** `src/ws/manager.py` (`send_personal_message`).

| Field                   | Type   | Notes                                          |
| ----------------------- | ------ | ----------------------------------------------- |
| `user_id` _(required)_  | string | Target user.                                    |
| `message_type` _(required)_ | string | Message type only — never the payload body.  |
| `connection_count`      | int    | Live connections for the user.                   |
| `outcome` _(required)_  | string | `delivered`, `failed`, ...                       |
| `duration_ms`           | float  | Publish/delivery duration.                       |

No message body contents beyond the message type, and no PII or holdings data.

```json
{
  "event.name": "ws.delivery",
  "user_id": "usr_123",
  "message_type": "portfolio_update",
  "connection_count": 2,
  "outcome": "delivered",
  "duration_ms": 4.2
}
```
