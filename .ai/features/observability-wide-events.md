---
title: Unified wide-event observability (ClickStack)
slug: observability-wide-events
status: ready
date: 2026-09-24
---

# Unified wide-event observability

## Problem

Production behavior on this project is a black box beyond `docker logs`. A question like "why are prices stale for Wealthsimple accounts with many positions?" requires log archaeology across five processes with no shared correlation: the `request_id` from `RequestIdMiddleware` dies at the HTTP boundary, Huey tasks and the WebSocket manager have no shared ID, and the Go services log independently. There are no metrics, no traces, no aggregated storage — container restarts destroy the only telemetry that exists. Pre-aggregated metrics (the classic three-pillars plan) structurally cannot answer the high-cardinality questions this domain actually raises (per-account, per-provider, per-cache-state cohorts), so the project adopts the *Observability Engineering* approach instead: unified, arbitrarily-wide structured events stored raw in a columnar store, aggregated at read time.

## Goal

Every meaningful operation in all five app processes emits one wide structured event carrying dozens of business fields plus a shared trace context; events land raw in a self-hosted ClickStack (ClickHouse) instance queryable via HyperDX, with a thin Prometheus for infra-level gauges. Engineers can run the core analysis loop (compare anomalous cohort vs. baseline) across any dimension without shipping new code.

## User-facing behavior

The "user" of this feature is the developer/operator. Concrete scenarios:

1. **Deploy verification (developer feedback loop).** After changing sync logic, the developer queries `portfolio.sync.completed` events filtered to `trigger=manual` and their own `user_id` immediately after deploy, and sees duration, positions changed, and provider call outcomes for their change while intent is fresh.
2. **Anomaly investigation.** A user reports stale prices. The operator filters `market.data.fetched` where `freshness_lag_ms` is high, and cohort comparison shows the anomalous set shares `provider=X` and `cache_state=stale` — drill-down to a root cause in minutes.
3. **Cross-process failure tracing.** A sync task fails. Querying `huey.task` with its `error_slug` shows the linked `trace_id`, and the same trace contains the originating `http.request`, the `market.data.fetched` provider calls, and the delivery of the failure via `ws.delivery` — one continuous trace across Python worker, Redis pub/sub, and browser.
4. **Frontend error correlation.** A frontend error toast displays the backend `request_id`/`trace_id`; pasting it into HyperDX shows the full backend trace for support correlation.
5. **Local dev parity.** `docker compose up` with the observability overlay brings up ClickStack + Prometheus; events from all services flow with zero per-developer setup.

## Scope

**In scope:**
- Self-hosted **ClickStack** (ClickHouse + OpenTelemetry Collector + HyperDX) as the primary telemetry store/UI, added via a Docker Compose overlay alongside the existing dev stack.
- A thin **Prometheus** instance (also in Compose) for genuinely low-cardinality infra gauges (container-level, Redis queue depth, DB pool size).
- OpenTelemetry SDK wiring for all four backend-side processes: Python (FastAPI backend, Huey worker) and Go (indicator-service, mcp-gateway), using auto-instrumentation where available plus manual spans at domain boundaries.
- W3C trace-context propagation across every process seam: HTTP → Huey task kwargs, Redis pub/sub → WebSocket delivery, backend → indicator-service, mcp-gateway → backend data-plane.
- A canonical **wide-event catalog** (starting point of 8 events, ~20–40 fields each) emitted at business boundaries, built incrementally across multi-stage operations (e.g., a sync's provider calls → persistence → completion).
- Unification of the existing `request_id` with the OTel `trace_id` (one correlation ID everywhere).
- `deploy_id` stamping on every event (groundwork for future progressive delivery).
- A redaction boundary before telemetry egress (auth tokens, broker tokens, PII).
- Tail-based sampling policy: 100% of error events retained, successful bulk sampled (~5–10%).
- Error-inbox exception tracking (Sentry or equivalent) for backend + frontend, plus surfacing the correlation ID in frontend error UI.
- Analysis workflow: HyperDX as the primary UI, seeded example queries for the core analysis loop; dashboards kept minimal.
- Test-environment safety: OTel exporters disabled in `ENVIRONMENT=test` (`OTEL_SDK_DISABLED`), no new network dependency in the pytest suite.

**Out of scope:**
- Feature-flag system (Practice 4) beyond stamping a flag/deploy identifier on events; progressive delivery/canary automation (Practice 5) beyond the `deploy_id` groundwork.
- Full RUM / Web Vitals instrumentation in the browser (deferred; frontend gets error tracking + trace-context headers only).
- Alerting/SLO rule packs and notification routing — SLI query groundwork only.
- Replacing or reworking the existing structured logging (`src/config/logging.py`, Go `slog` work from the F-*-LOGS tickets) — logging continues; important signals move to first-class events.
- Migration paths to other vendors (instrumentation stays OTel-native; switching later is collector config, not project work).

## Current state & gap

**Exists today:**
- Prod JSON logging with `request_id` injection: `src/config/logging.py` (`JsonFormatter`, `RequestIdFilter`, contextvar from `src/core/context.py`); Rich handler in dev.
- Request access logging + request-ID middleware: `src/core/middleware.py` (`RequestIdMiddleware`); uvicorn access logs correctly disabled.
- Liveness health endpoint + Compose healthcheck (`/health/live`).
- Go services already emit structured `slog` logs (indicator-service: closed F-INDICATOR-LOGS-T01/T02; mcp-gateway: F-MCP-GATEWAY-LOGS-T01 closed, T02 #571 open — in-flight work this feature must complement, not duplicate).
- Queue/sync state tracking exists in `src/integration/sync_status.py` and the Huey dashboard (`huey-dashboard` mounted at `/worker/api`).

**Missing:**
- No OpenTelemetry SDKs, no trace propagation, no metrics endpoint, no Prometheus, no columnar event store, no error inbox, no log aggregation — confirmed by absence in `pyproject.toml`, `frontend/package.json`, both Go `go.mod` files, and `docker-compose.yml`.
- Correlation gaps: Huey tasks (`src/market/task.py`, `src/account/task.py`, `src/integration/task.py`), WS pub/sub (`src/ws/manager.py`), and backend→Go HTTP calls (`src/config/services.py` for indicator-service; `services/mcp-gateway/backendclient.go` for the data plane) carry no shared context.
- External gateways (`src/market/eodhd.py`, `fmp.py`, `polygon.py`, `src/integration/brokers/wealthsimple.py`) and caches (`src/market/cache.py`, `endpoint_cache.py`) have no instrumentation and no per-provider telemetry.

## What needs to be done

Work areas with hard sequencing only where noted:

1. **Compose observability overlay** — ClickStack (ClickHouse, Collector, HyperDX) + Prometheus services, dev-only profile wiring, retention config. *(No app code depends on this being first, but all verification does.)*
2. **Python OTel foundation** — SDK bootstrap + settings, test-env kill switch, trace_id/request_id unification, deploy_id stamping, redaction processor, auto-instrumentation for FastAPI/SQLAlchemy/Redis/httpx.
3. **Cross-process trace propagation** — traceparent into Huey task metadata (enqueue + consumer), Redis pub/sub → WS delivery, backend → indicator-service headers.
4. **Go OTel wiring** — both services export traces/events via OTLP; propagation on inbound (mcp-gateway → backend) and outbound (backend → indicator-service) calls; complements existing slog.
5. **Wide-event catalog implementation** — the 8 canonical events (http.request, huey.task, portfolio.sync.completed/failed, market.data.fetched, market.cache.accessed, alert.evaluated, ws.delivery, auth.event) with incremental event builders for multi-stage operations.
6. **Thin Prometheus metrics** — infra gauges only (queue depth, pool utilization, process health); business signals stay in events.
7. **Sampling + retention policy** — tail-based sampling in the Collector (errors always kept), retention tiers per event class.
8. **Error inbox** — backend + frontend exception tracking with release/deploy tagging.
9. **Analysis workflow** — HyperDX onboarding: saved queries for the core analysis loop, minimal dashboards, documented field dictionary for the catalog.

## Decisions (locked by user)

1. ClickStack, self-hosted, in Docker Compose (not Honeycomb/SaaS).
2. Thin Prometheus layer included, also in Docker Compose.
3. The proposed 8-event catalog is approved as the starting point.

## Constraints from project conventions

- **Tests are hermetic** (root `AGENTS.md`): the observability stack must not add a network dependency to pytest; exporters no-op under `ENVIRONMENT=test`; any new fixtures mock outbound I/O.
- **Provider-name rule** (from the mcp-gateway/data-plane work): upstream provider brands must not appear in user- or agent-facing surfaces. Provider identity *is* required as an internal telemetry dimension — allowed in ClickStack/HyperDX (operator-only), never in user-facing error details or agent payloads.
- **No duplication**: existing request logging in `src/core/middleware.py` stays; trace context is added to it rather than re-logged by OTel instrumentation.
- In-flight overlap: ticket #571 (F-MCP-GATEWAY-LOGS-T02, mcp-gateway structured logging) is open — Go OTel tickets must not rework what it covers.

## Definition of done

- [ ] `docker compose` with the observability overlay brings up ClickStack + Prometheus; events from backend, worker, frontend, indicator-service, and mcp-gateway all arrive in ClickHouse.
- [ ] A failed sync is traceable end-to-end in HyperDX: `http.request` → `huey.task` → `market.data.fetched` → `ws.delivery` sharing one trace ID.
- [ ] All 8 catalog events are emitted with at least their specified fields; field dictionary documented.
- [ ] "p95 sync duration by broker for accounts with >100 positions" is answerable at read time without code changes.
- [ ] Every event carries `deploy_id` and the unified trace ID; `request_id` and `trace_id` are the same value in logs.
- [ ] 100% of error events retained; successful bulk sampled per policy; ClickHouse retention configured.
- [ ] No tokens/PII present in stored telemetry (redaction boundary verified by tests).
- [ ] Full pytest suite passes with observability disabled in test env; no new external-service dependency in tests.
- [ ] Backend + frontend unhandled exceptions appear in the error inbox with deploy tags.
