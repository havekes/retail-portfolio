---
type: architecture
title: Architecture Overview
description: System-level runtime map of retail-portfolio — the FastAPI process (lifespan migrations, eager data-plane gateway resolution, svcs registry, middleware order, error handling), the Huey worker, the SvelteKit SSR frontend, the Go indicator sidecar and MCP gateway, PostgreSQL/Redis/mailcrab, routes under /api/v1, health probes, layer rules and the commands that verify a change.
tags: [architecture, fastapi, huey, sveltekit, go-services, mcp-gateway, data-plane, postgresql, redis, dependency-injection, request-lifecycle, docker-compose]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-15T13:03:07.448Z
sources:
  - id: openwiki-source-5f5b95b3d6a215fa02ceb945
    resource: repo://.env.example
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-11ef2d56dffda152beeb9f84
    resource: repo://docker-compose.prod.yml
  - id: openwiki-source-b79fbbd921df689b4bbdc82f
    resource: repo://docker-compose.yml
  - id: openwiki-source-bb1ebe868e35e9e500714501
    resource: repo://Dockerfile
  - id: openwiki-source-e483fd3285d99d05c7b265cf
    resource: repo://frontend/AGENTS.md
  - id: openwiki-source-0bdf50a0b0b0618dd3a5abe8
    resource: repo://frontend/src/hooks.server.ts
  - id: openwiki-source-45599bb9a8794a9c90b7e20d
    resource: repo://frontend/src/lib/api/apiClient.ts
  - id: openwiki-source-c59fe4336a371ea1052a01dd
    resource: repo://justfile
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-9e744972fabdd8b4cf6187c6
    resource: repo://services/indicator-service/internal/httpapi/router.go
  - id: openwiki-source-692344b8dd5d47fcc6f9bfe0
    resource: repo://services/indicator-service/README.md
  - id: openwiki-source-4a501a3fad557af156591f05
    resource: repo://src/account/registry.py
  - id: openwiki-source-30de42522595a37de333f4dd
    resource: repo://src/account/router.py
  - id: openwiki-source-b911aefb4dbb6f043ed2380e
    resource: repo://src/account/task.py
  - id: openwiki-source-230f617cb6d47154ef463034
    resource: repo://src/AGENTS.md
  - id: openwiki-source-92dacc39dc7b0f24b1f6b1aa
    resource: repo://src/auth/api.py
  - id: openwiki-source-822ca61471a547e89400439b
    resource: repo://src/auth/router.py
  - id: openwiki-source-4c3d639efe14a5f50763de50
    resource: repo://src/config/limiter.py
  - id: openwiki-source-e1e5885568a239055161be95
    resource: repo://src/config/services.py
  - id: openwiki-source-d1e4e10eebd8f4d4314bc43f
    resource: repo://src/config/settings.py
  - id: openwiki-source-0b05f99dd1a5c08ae3ebc4a5
    resource: repo://src/core/exception.py
  - id: openwiki-source-bb9b5d3400aa107e32ebff27
    resource: repo://src/core/middleware.py
  - id: openwiki-source-fd173f0cb9d58ea27b5992d2
    resource: repo://src/integration/router.py
  - id: openwiki-source-11b9d806fcc6dd6e7747ed87
    resource: repo://src/main.py
  - id: openwiki-source-336c8d4ea788e2c5f7cddd73
    resource: repo://src/market/__init__.py
  - id: openwiki-source-c606a6f066e1a0d331b3781d
    resource: repo://src/market/composite.py
  - id: openwiki-source-d70f78b70446e1ce1912c7c5
    resource: repo://src/market/data_router.py
  - id: openwiki-source-0759916706da37d0d3bef090
    resource: repo://src/market/exception.py
  - id: openwiki-source-d8383d22d61483b00080a280
    resource: repo://src/market/router.py
  - id: openwiki-source-9fc85bceeb3edfbe3ab56a7c
    resource: repo://src/market/service.py
  - id: openwiki-source-c8a9ed75dfc5d7332062ae40
    resource: repo://src/worker_dashboard/router.py
  - id: openwiki-source-7a8d629077019775a9fec3d3
    resource: repo://src/worker.py
  - id: openwiki-source-9c5ae74acc82cf270945cf3d
    resource: repo://src/ws/manager.py
  - id: openwiki-source-346e26038016b0d379bc804e
    resource: repo://src/ws/README.md
  - id: openwiki-source-d63e02f817074e4280e045ae
    resource: repo://src/ws/router.py
  - id: openwiki-source-310380094f3817bbc88b1407
    resource: repo://tests/market/test_gateway_registration.py
  - id: openwiki-source-8b176c94b018259ee14f35b7
    resource: repo://tests/test_main.py
  - id: openwiki-source-f0abc296482c495e6bdb9e20
    resource: repo://tests/test_request_id.py
generated: { by: "openwiki/0.7.2", at: "2026-10-15T13:03:07.448Z" }
---

# Architecture Overview

`retail-portfolio` is a portfolio tracker for the retail investor. It runs as a small
set of cooperating containers: a FastAPI backend, a Huey worker process, a SvelteKit SSR
frontend, two Go sidecars (a stateless indicator calculator and an MCP gateway that
fronts the backend's service-to-service market data plane), plus PostgreSQL, Redis and —
in dev only — mailcrab.

This page is the system-level map: which process owns what, how the app starts, how a
request flows, which layer rules hold the backend together, and which commands verify a
change. Per-domain detail lives in [Backend Domains](./domains.md); configuration and DI
seams in [Configuration](./configuration.md); the UI shell in
[Frontend Architecture](./frontend.md); the chart surface in [Charting](./charting.md)
and drawing/snapshot internals in
[Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md); the Go services in
[Go Microservices](./go-services.md) and the [MCP Gateway](../integrations/mcp-gateway.md);
the data plane and providers in
[Market Data Providers](./market-data-providers.md); the asynchronous runtime in
[Realtime, Background Jobs & the Worker](../workflows/realtime-and-background-jobs.md);
the per-user preference contract in [User Preferences](../concepts/user-preferences.md);
authentication in [Authentication & Authorization](./authentication.md); developer/CI
workflows in [Development, CI & Change Workflows](../operations/workflows.md) and
[Testing & Verification](../operations/testing.md).

## Processes and containers

`docker-compose.yml` is the supported way to run the stack (`docker compose up -d`, or
`just up` to inject the host Docker group id): the backend is then on
`http://localhost:8001` (interactive API docs at `/redoc`, ping at `/api/ping`), the
frontend on `http://localhost:8002`, the indicator sidecar on `http://127.0.0.1:8004`
and the MCP gateway on `http://127.0.0.1:8005`. Every port is Compose-interpolated from
the single root `.env`, so ports are changed there rather than in the Compose file.

```mermaid
flowchart TD
    Browser["Browser"] -->|"HTTP host :8002"| Frontend["frontend: SvelteKit SSR on :8100"]
    Frontend -->|"SSR fetch VITE_INTERNAL_API_URL"| Backend["backend: uvicorn src.main:app on :8000"]
    Browser -->|"browser fetch VITE_API_BASE_URL"| Backend
    Browser -->|"/api/ws WebSocket"| Backend
    Backend -->|PostgreSQL| Postgres[("postgres:18")]
    Backend -->|"Huey queue, Pub/Sub, rate limit, status keys"| RedisStore[("redis:7")]
    Backend -->|SMTP| Mailcrab["mailcrab dev SMTP and UI"]
    Backend -->|"POST /compute"| Indicator["indicator-service: Go sidecar on :8080"]
    Worker["worker: huey_consumer src.worker.huey"] -->|"PostgreSQL NullPool"| Postgres
    Worker -->|"task queue and Pub/Sub publish"| RedisStore
    Worker -->|SMTP| Mailcrab
    McpClient["MCP client or agent"] -->|"streamable HTTP on :8005"| Mcp["mcp-gateway: Go sidecar on :8080"]
    Mcp -->|"GET /api/v1/market/data/* with X-Service-Token"| Backend
```

Container topology: the browser reaches the SvelteKit SSR app, which server-side-fetches
the backend over the Compose network; the backend is the only caller of the Go indicator
sidecar; and the MCP gateway is the only caller of the backend's service-to-service data
plane. Both Go services are stateless — the backend owns candle data, indicator specs and
provider access.

| Service | Role |
|---------|------|
| `backend` | FastAPI app served by `uvicorn src.main:app`; owns HTTP, WebSocket, migrations, rate limiting, error handling and the service-to-service data plane |
| `worker` | Huey consumer; dev command is `uv run -m watchfiles "huey_consumer src.worker.huey -w 2 --worker-type thread --periodic" src/` |
| `frontend` | SvelteKit dev server (`npm run dev`, container port 8100) in dev; the `adapter-node` build on port 3000 in prod |
| `indicator-service` | Stateless Go calculator exposed at `POST /compute` and `GET /health`; no auth, internal network only |
| `mcp-gateway` | Go MCP server over streamable HTTP at `/mcp` plus `/health`; holds no provider credentials and calls only the backend data plane |
| `postgres` | Primary datastore (PostgreSQL 18) |
| `redis` | Huey task queue, WebSocket Pub/Sub fan-out, slowapi rate-limit storage, sync/2FA/denylist keys, data-plane response cache |
| `mailcrab` | Dev SMTP sink + web UI for outgoing email |

The MCP gateway is the newest container and the one with the firmest startup ordering: it
is built from `./services/mcp-gateway`, publishes `127.0.0.1:${MCP_GATEWAY_PORT:-8005}:8080`,
reads `BACKEND_BASE_URL` (default `http://backend:8000`), `MARKET_DATA_SERVICE_TOKEN` and
`DATA_PLANE_PATH` (default `/api/v1/market/data`), and declares
`depends_on: backend: condition: service_healthy` — so it only starts once the backend's
`/health/live` probe passes. Its own healthcheck probes `/health` from inside the
container.

Both Go sidecars publish their host port bound to `127.0.0.1` only, and no frontend code
holds either URL: the indicator sidecar's address lives in the backend
(`INDICATOR_SERVICE_URL`) and the MCP gateway's address is only documentation for external
MCP clients. The sidecar ports exist for manual inspection, not for browser traffic.

`docker-compose.prod.yml` keeps the same shape but is not a drop-in copy: it builds the
images (`build: .` for backend and worker, `build: ./frontend`), pins ports
(`8000:8000`, `80:3000`), drops the debug ports, and **has no `mailcrab` service**.
`mcp-gateway` is present but internal-only — no host port is published, and
`MARKET_DATA_SERVICE_TOKEN: "${MARKET_DATA_SERVICE_TOKEN:?...}"` makes Compose refuse to
start without the shared secret. Its worker command is `huey_consumer src.worker.huey -w 2
--worker-type thread` — without `--periodic`, so Huey's periodic schedules only fire under
the dev Compose file. The root `Dockerfile` builds a `python:3.14-slim` image whose `CMD`
runs `uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
--timeout-graceful-shutdown 30` and whose `HEALTHCHECK` probes `/health/live`; each of
those four worker processes executes the lifespan, and therefore `alembic upgrade head`,
at startup.

The indicator sidecar is deliberately public-network-free: it exposes no authentication
and no rate limiting, so it must stay on the internal Docker network. The MCP gateway's
MCP listener is likewise unauthenticated — its shared-secret trust boundary is the backend
data plane it calls, not the listener — so it is internal network only too.

## Backend startup (lifespan)

`src/main.py` builds the `FastAPI` app with `lifespan=lifespan_context`. The lifespan is
the single place where process-scoped resources are created and torn down:

1. **Migrations.** Outside `test`, Alembic runs `command.upgrade(cfg, "head")` in a
   worker thread via `asyncio.to_thread(run_migrations)`, so schema upgrades happen
   before the first request is served. In `test`, tables come from
   `BaseModel.metadata.create_all` instead. No other process runs migrations — the Huey
   worker's `on_startup` only builds its registry and signals — so a worker always starts
   against the schema the backend has migrated.
2. **Dependency registry.** A fresh `svcs.Registry()` is created, stored on
   `app.state.svcs_registry`, and populated by
   `register_services(registry, sessionmanager)` from `src/config/services.py`.
3. **Eager data-plane gateway resolution.** A throwaway
   `async with svcs.Container(registry) as container:` block calls
   `await container.aget(DataPlaneMarketGateway)`, so a broken registration or an
   unusable provider configuration fails at boot instead of on the first data-plane
   request. The probe container is closed immediately, releasing the composite's provider
   HTTP clients; request handlers resolve their own instance from the registry. Missing
   credentials are caught even earlier by `Settings`: outside `dev`/`test`, and with
   `STUB_EXTERNAL_API` off, a blank `FMP_API_KEY` or `POLYGON_API_KEY` raises at settings
   load.
4. **WebSocket manager.** `ws_manager.init_redis(settings.redis_url)` opens the Redis
   client for the running event loop and starts the Pub/Sub listener task.
5. **Huey dashboard.** `init_worker_dashboard(...)` binds the Huey instance, a task
   database over `database_url` (creating its table), a Redis-backed
   `WebSocketManager` and signal handlers, all stored under `app.state.huey_dashboard`.

```mermaid
sequenceDiagram
    participant U as uvicorn worker
    participant L as lifespan_context
    participant A as Alembic
    participant R as svcs Registry
    participant G as DataPlaneMarketGateway
    participant W as ws_manager
    participant D as Huey dashboard
    participant M as redis_manager

    U->>L: enter lifespan
    L->>A: command.upgrade head in a worker thread
    A-->>L: schema at head
    L->>R: register_services with sessionmanager
    L->>G: aget in a throwaway container, then close it
    G-->>L: fail fast on a missing provider key
    L->>W: init_redis plus Pub Sub listener
    L->>D: init_worker_dashboard with bind_signals
    L-->>U: yield svcs_registry
    Note over L: a failure during yield is logged, not fatal
    U->>L: shutdown
    L->>D: close_worker_dashboard
    L->>W: close
    L->>M: close
```

Startup creates migrations, the registry, the data-plane gateway probe, the WebSocket
listener and the dashboard in that order, then teardown unwinds them in reverse; only the
`test` environment swaps the migration step for `BaseModel.metadata.create_all`.

Inside the `async with registry:` block the lifespan yields
`{"svcs_registry": registry}`; teardown then calls `close_worker_dashboard`,
`ws_manager.close()` and `redis_manager.close()`. The lifespan body wraps its yield in a
`try/except` so a failure during yield is logged instead of silently killing shutdown.

In `dev`, the module also calls `debugpy.listen(("0.0.0.0", 5678))` at import time, which
is why Compose publishes a backend debug port. `app` is constructed with
`debug=settings.environment != "prod"`, and the module calls `init_logging()` (Rich
handlers in dev, JSON lines with `request_id` in prod) before the first request.

## Route mounting and entrypoints

**HTTP API routes live under `/api/v1`.** `src/main.py` builds one
`APIRouter(prefix="/api/v1")` and includes the domain routers into it:

```python
v1 = APIRouter(prefix="/api/v1")
v1.include_router(account_router)
v1.include_router(portfolio_router)
v1.include_router(auth_router)
v1.include_router(institutions_router)
v1.include_router(integration_router)
v1.include_router(market_router)
v1.include_router(data_router)

app.include_router(v1)
app.include_router(ws_router)
app.include_router(worker_dashboard_router)
```

Only the two extra routers and the ad-hoc endpoints sit outside that prefix. The full
top-level surface is:

| Path | Owner | Notes |
|------|-------|-------|
| `/api/v1/...` | `v1` router aggregating every domain router | e.g. `/api/v1/auth/*`, `/api/v1/accounts/*`, `/api/v1/portfolios/*`, `/api/v1/market/*`, `/api/v1/integration/*`, `/api/v1/external/*` |
| `/api/v1/market/data/*` | `src/market/data_router.py` (`data_router`, prefix `/market/data`) | Service-to-service data plane for the MCP gateway; `X-Service-Token` auth instead of the user JWT |
| `/api/ws` | `src/ws/router.py` | WebSocket endpoint, not under `/api/v1` |
| `/api/ping` | `src/main.py` | Simple DB-backed healthcheck |
| `/health/live` | `src/main.py` | Liveness probe used by the Compose and image healthchecks |
| `/health/ready` | `src/main.py` | Readiness probe: DB + Redis |
| `/worker/api/...` | `src/worker_dashboard/router.py` | Huey dashboard: `/worker/api/tasks` plus `/worker/api/updates` WebSocket |

Older documentation that describes routes as bare `/api` without the `/v1` segment is
wrong: domain routers themselves are prefix-less relative to that (for example
`auth_router` is `APIRouter(prefix="/auth")`, `account_router` is `/accounts`,
`portfolio_router` is `/portfolios`, `market_router` is `/market`) and get their
`/api/v1` prefix only here. The frontend `apiClient` hard-codes the same `/api/v1`
base.

One naming inversion is worth internalizing because it makes URL-to-owner lookups
error-prone: `src/integration/router.py` defines both

```python
integration_router = APIRouter(prefix="/external")
institutions_router = APIRouter(prefix="/integration")
```

so `/api/v1/external/*` is the broker-integration surface while `/api/v1/integration/*`
serves the institution list. Mounting is the only thing that gives these routers their
`/api/v1` segment — `src/main.py` includes `account_router`, `portfolio_router`,
`auth_router`, `institutions_router`, `integration_router`, `market_router` and
`data_router` into `v1` in that order, so a new domain router must be added both where it
is defined and to that include list.

Two routers that each own a wide surface are worth knowing by their module:
`src/account/router.py` defines both `account_router` (`/accounts`) and `portfolio_router`
(`/portfolios`), and `src/market/router.py` carries `market_router` (`/market`) for the
market read paths, watchlists with manual ordering, alerts, notes, documents, chart
snapshots, security valuations (`/securities/valuation/batch` and
`/securities/{security_id}/valuation`), indicator compute and the AI endpoints.

The data plane is deliberately separate from `market_router` and is not a user surface:
every route depends on `require_service_token`, which compares the `X-Service-Token`
header against `settings.market_data_service_token` in constant time and raises `401`
otherwise, with no cookie fallback. Failures are translated to provider-neutral HTTP
statuses (unknown symbol `404`, provider outage `502`, configuration problem `503`) and a
provider name never appears in a response body. Its route paths and query parameter names
are a stable contract for the Go MCP gateway, pinned by a committed OpenAPI snapshot —
see [Market Data Providers](./market-data-providers.md) and
[MCP Gateway](../integrations/mcp-gateway.md).

Other process entrypoints: `src/worker.py` is the Huey consumer module, and
`src/commands/seed.py` / `src/commands/flush_market_data.py` are standalone CLI commands
for reference data and market-data maintenance (`src/market/commands/` holds smaller
EODHD inspection scripts).

## Request lifecycle

Every HTTP request passes through the middleware stack installed in `src/main.py`. The
registration order in source is `RequestIdMiddleware`, then `app.state.limiter` plus the
`RateLimitExceeded` handler, then `SlowAPIMiddleware`, then the two function middlewares
`reset_rate_limit_state_middleware` and `cors_exception_middleware`, and finally
`CORSMiddleware`. Starlette prepends each `add_middleware` call to the front of its user
middleware list and builds the stack so that the first entry is outermost — the
reverse-order rule, where the middleware registered last is the outermost — so the
effective inbound order is the reverse of registration: `CORSMiddleware`,
`cors_exception_middleware`, `reset_rate_limit_state_middleware`, `SlowAPIMiddleware`,
`RequestIdMiddleware`, then the router.

- `CORSMiddleware` — configured from comma-separated `cors_allow_origins`,
  `cors_allow_methods` and `cors_allow_headers`; outside `prod` it additionally allows
  `allow_origin_regex=r"https?://.*"`, with `allow_credentials=True`. Being outermost, it
  also short-circuits preflight requests before they reach the inner middleware.
- `cors_exception_middleware` — safety net that converts an escaping exception into a
  `500` JSON response and re-injects CORS headers manually. Sitting inside the CORS layer
  but outside the rate-limit and request-ID middleware, it is normally what turns an
  unmapped route exception into a `500` before the exception can reach the app-level
  `Exception` handler registered on the outermost Starlette error middleware.
- `reset_rate_limit_state_middleware` plus `SlowAPIMiddleware` — rate limiting backed by
  `src/config/limiter.py`, keyed by `user_or_ip_key_func` (the user id decoded from the
  `auth_token` cookie or `authorization` header, falling back to the remote address) with
  Redis storage outside `test` and `memory://` in tests; the shim deletes
  `request.state._rate_limiting_complete` so slowapi state does not leak between calls.
- `RequestIdMiddleware` (`src/core/middleware.py`) — reads or generates `X-Request-ID`,
  stores it on `request.state`, binds it into a contextvar for log correlation, echoes it
  back on the response, and logs one entry/exit line per request (4xx at `warning`,
  everything else at `info`) with `duration_ms`.

```mermaid
sequenceDiagram
    participant C as Client
    participant Cors as CORSMiddleware
    participant Ce as cors_exception_middleware
    participant Rl as Rate limiting
    participant Rid as RequestIdMiddleware
    participant R as Domain router under /api/v1
    participant S as Service or domain API
    participant DB as PostgreSQL

    C->>Cors: HTTP request
    Cors->>Cors: apply CORS policy
    Cors->>Ce: call next
    Ce->>Rl: call next
    Rl->>Rl: enforce limiter quota
    Rl->>Rid: call next
    Rid->>Rid: bind or generate X-Request-ID
    Rid->>R: call next
    R->>R: resolve DepContainer from app.state.svcs_registry
    R->>S: aget service and call business method
    S->>DB: async session query
    DB-->>S: rows
    S-->>R: schemas or api_types
    R-->>Rid: JSON response
    Rid->>Rid: log exit plus duration_ms
    Rid-->>Rl: response with X-Request-ID
    Rl-->>Ce: response
    Ce-->>Cors: response
    Cors-->>C: response with CORS headers

    Note over Ce,Rid: An exception escaping the inner layers is caught by cors_exception_middleware, which returns 500 with CORS headers
```

Request lifecycle from the CORS layers down through rate limiting and `X-Request-ID`
binding, then router resolution, service/repository work and the response back out — with
the CORS safety net catching anything that escapes.

### Handlers and responses

Route handlers receive the `svcs` container as a FastAPI dependency (`DepContainer`) and
resolve collaborators by interface:

```python
@portfolio_router.get("/")
async def portfolios(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[PortfolioRead]:
    portfolio_service = await services.aget(PortfolioService)
    return await portfolio_service.get_portfolios_by_user(user.id)
```

They declare Pydantic request/response models, enforce auth through the `current_user`
dependency (or `require_service_token` on the data plane), and delegate business logic to
services or domain APIs. They never touch another domain's repositories — though, as the
layer rules below note, they may resolve their own domain's repositories directly
(`@account_router.get("/")` does exactly that with `AccountRepository`).

## Health and readiness

| Endpoint | Behavior |
|----------|----------|
| `/health/live` | Always `200 {"status": "alive"}`; used by the Compose and image healthchecks |
| `/health/ready` | Executes `select(1)` on a resolved `AsyncSession` **and** `PING`s Redis via `redis_manager.client()`; returns `200 {"status": "ready", ...}` when every check is `ok`, otherwise `503 {"status": "degraded", ...}` |
| `/api/ping` | Resolves a session and runs `select(1)`, returning `{"ping": "pong", "database": "ok" \| "error"}` — it reports DB failure in the body rather than failing the request |

The two kinds are deliberately distinct: liveness must not depend on downstream
services, readiness must. `/health/live` is also the Compose health condition the
`mcp-gateway` container waits on. `tests/test_main.py` asserts both shapes, and `/api/ping`
returning `"pong"` is the smoke test the README points at.

## Dependencies and cross-domain calls

Dependency injection is centralized in `src/config/services.py`. Each domain exports a
`register_*_services(registry)` function (`src/core/registry.py`,
`src/account/registry.py`, `src/auth/__init__.py`, `src/integration/registry.py`,
`src/market/__init__.py`), and `register_services` always:

1. registers `AsyncSession` as a factory over `sessionmanager.session`;
2. registers core services (`EmailService`);
3. registers account and auth services unconditionally;
4. picks the stub or live registration set for the market and integration domains based
   on `settings.stub_external_api` (`register_integration_stub_services` /
   `register_market_stub_services` versus `register_integration_services` /
   `register_market_services`).

Two market gateway keys coexist, and the distinction is load-bearing for the data plane:
`MarketGateway` stays bound to the EODHD gateway (prices and search for the legacy
flows), while `DataPlaneMarketGateway` resolves to the
`CompositeMarketGateway` over FMP (prices, search, fundamentals) and Polygon (options).
Both registration sets register both keys, so switching to stubs changes the gateways
behind the keys, not the keys themselves. This is why the boot probe in the lifespan can
fail early: the provider-agnostic data-plane key is wired at startup, not lazily per
route.

The same `register_services` function is what the worker calls, so the API and the worker
resolve the same interfaces — only the session manager differs (see the realtime page). A
new repository, service or domain API becomes resolvable only once it is registered in
its domain's `register_*_services`.

Cross-domain access always goes through public domain APIs, never foreign repositories.
`PositionService` is the canonical orchestrator: it depends on its own
`PositionRepository` and on the market domain's `MarketPricesApi` / `SecurityApi` and
the integration domain's `IntegrationAccountApi`; the types crossing those boundaries
come from `api_types.py`.

## Backend layer rules

Each backend domain under `src/` follows the same shape (`model.py`, `schema.py`,
`api_types.py`, `repository.py`, `repository_sqlalchemy.py`, `repository_<other>.py`,
`api.py`, `service.py`, `router.py`, `enum.py`, `exception.py`). The rules that a change
must not break, from `src/AGENTS.md`:

- **Repositories always return schemas, never ORM models.** Models exist to generate
  migrations and are never returned to clients.
- **Cross-domain calls happen only through the other domain's `api.py` APIs and
  `api_types.py`.** A service must not import another domain's repository or schema.
  A router *may* use its own domain's repositories directly — the market watchlist,
  alert, note, document, snapshot and security-valuation routes do exactly that, and the
  account router resolves `AccountRepository` directly for `GET /accounts` — but never a
  foreign domain's.
- **Routers own HTTP concerns; services do not raise `HTTPException`** (the
  authorization service is the documented exception). Domain errors inherit from
  `EntityNotFoundError` / `AuthorizationError` in `src/core/exception.py` and the global
  handlers turn them into `404`, or they are deliberately *not* such a subclass and the
  router maps them itself — `WatchlistOrderIdentityError` becomes `422` and
  `WatchlistDuplicateNameError` becomes `409` for exactly that reason, the CSV
  upload routes raise `422` for missing form fields, and the data plane maps gateway
  failures to `404`/`502`/`503`.
- **Services are registered as factories and resolved from the registry** — never
  instantiated by hand inside a request.
- **Editing a model requires an Alembic migration** following the
  `<hash>_<description>.py` naming convention, shipped in the same change.

Domains documented from this base: `account`, `auth`, `market`, `integration`, `ws`,
`core`, `config` — see [Backend Domains](./domains.md) for models, public APIs, services
and extension recipes.

## Realtime and background work (orientation)

Two cross-process mechanisms matter at the system level; both are documented in full on
[Realtime, Background Jobs & the Worker](../workflows/realtime-and-background-jobs.md).

- **The worker.** `src/worker.py` defines the Huey instance (`RedisHuey` everywhere
  except `test`, where it is `MemoryHuey`), builds its own `svcs` registry in
  `@huey.on_startup()` with a `NullPool` session manager, and imports the task modules
  (`src/account/task.py`, `src/integration/task.py`, `src/market/task.py`) at module
  bottom so their decorators register. Task bodies are synchronous Huey functions that
  bridge into async logic with `asyncio.run(...)` and re-bind the originating
  `request_id` into the log contextvar; their triggers, retries and cascade live on the
  realtime page.
- **The WebSocket fan-out.** `src/ws/manager.py` holds a process-global
  `ConnectionManager` with a per-`UserId` connection registry and one Redis client per
  event loop; publishers write to the `ws_messages` Pub/Sub channel and the main-loop
  listener delivers to local connections, so a Huey worker thread can push into the API
  process, with a local-broadcast fallback if Redis is unavailable. `/api/ws` accepts
  either a short-lived signed ticket (`POST /api/v1/auth/ws-ticket`, `salt="ws-ticket"`,
  `max_age=30`) or the `auth_token` cookie / `sec-websocket-protocol` token, and closes
  with code `1008` on failure or on a replayed ticket (`ws-ticket-used:<sha256>` Redis
  key with `nx=True, ex=30`). The worker dashboard mirrors the pattern at
  `/worker/api/updates`.

The Huey dashboard mounted at `/worker/api` is the operational window into task history:
its task routes carry `Depends(current_user)`, and its WebSocket reuses the ticket
helper.

## Error handling

`src/main.py` registers the global exception handlers that give the API one error
shape:

| Handler | Status | Body |
|---------|--------|------|
| `EntityNotFoundError` | `404` | `{"error": str(error)}` |
| `AuthorizationError` | `404` | `{"error": str(error)}` — existence is hidden from unauthorized callers |
| `RateLimitExceeded` | slowapi handler | slowapi's `_rate_limit_exceeded_handler` |
| `Exception` (catch-all) | `500` | `{"detail": "Internal Server Error", "error": ...}`, where `error` is the exception string outside `prod` and the literal `"Internal Error"` in `prod` |

Both `cors_exception_middleware` and the catch-all handler apply the same `prod`
redaction rule, and both log via `logger.exception`. Focused tests for this behavior are
`tests/test_main.py` (health, ping, handler logging and redaction) and
`tests/test_request_id.py` (header generation, preservation, log context, 4xx warning).

## Frontend

The frontend is a SvelteKit 2 / Svelte 5 Node SSR application
(`@sveltejs/adapter-node`) that talks to the backend exclusively through a typed client
layer over `/api/v1`.

| Concern | Location |
|---------|----------|
| Routes | `frontend/src/routes/` — `+page.server.ts` loads and form actions |
| API clients | `frontend/src/lib/api/` — one client per backend area over `apiClient` |
| Components | `frontend/src/lib/components/` — domain-grouped |
| Types | `frontend/src/lib/types/`, `frontend/src/lib/api/types/` |
| State | `*.svelte.ts` class modules using runes (`$state`/`$derived`/`$effect`) |
| SSR auth guard | `frontend/src/hooks.server.ts` — verifies the `auth_token` cookie and redirects |

Two base URLs matter: `VITE_INTERNAL_API_URL` (`http://backend:8000` in Compose) is used
for server-side loads, while `VITE_API_BASE_URL` is the browser-visible backend. The SSR
guard verifies JWTs with `JWT_SECRET`, which Compose derives from the backend's
`SECRET_KEY` so the two can never drift, and rejects any token whose `scope` is not
`access`.

There is no third URL: **no frontend code holds the indicator-service or MCP gateway
address.** Both sidecars are backend-side concerns, so neither `INDICATOR_SERVICE_URL` nor
`MCP_GATEWAY_URL` reaches the browser or the SSR layer.

See [Frontend Architecture](./frontend.md) for route, state and charting detail, and
[Authentication & Authorization](./authentication.md) for the token and 2FA flows.

## Verifying a change

The global constraints below apply to every change, not just backend ones:

- **Docker-only commands.** Run backend and frontend development commands inside the
  containers — `docker compose exec <backend|frontend> <command>`; the host is never the
  reference environment, and CI runs the same checks. Go microservice checks are the
  exception: they run on the host Go toolchain (`gofmt`, `staticcheck`, `go test ./...`,
  `go vet ./...`) or through `just` (`just lint-go`).
- **Use the agent harness.** `./scripts/agent-test` (shorthand `just test`) is the
  primary test entrypoint: Gate 0 (lint + type checker, halting before tests), Gate 1
  (a path argument, targeted and fail-fast) and Gate 2 (no argument, full regression
  with an Index/Traces summary). Raw `docker compose exec … pytest`/`vitest` is the
  fallback. Go services get their own recipes: `just test-indicator-service`,
  `just test-mcp-gateway`, and `just test-all` runs backend, frontend and both Go
  modules in parallel.
- **Model edits require a migration.** Editing a backend model means generating the
  Alembic revision named `<hash>_<description>.py` in the same change.
- **Tests never depend on external services.** No test may dial Redis, HTTP APIs
  (EODHD, broker APIs), SMTP or DNS; the ephemeral testcontainers PostgreSQL is the only
  allowed infrastructure dependency, and frontend tests mock every API client. A test
  that makes a real network call is broken by definition.

CI (`.github/workflows/ci.yml`) mirrors this in four independent jobs: backend
(`uv run ty check`, `uv run ruff check` + `uv run ruff format --check`, `uv run pytest`),
frontend (`npm run check`, `npm run lint`, `npm run test:run` with the `VITE_*` and
`JWT_SECRET` variables set but no backend running, plus the Node script tests),
indicator-service and mcp-gateway (each `go vet ./...`, a `gofmt -l` format gate, a
pinned `staticcheck`, `govulncheck` with a documented stdlib-only allowance, `go build
./...` and `go test ./...`).

## Relationship to the other pages

- [Configuration](./configuration.md) — the single root `.env`, `Settings`, registry
  seams, database/Redis managers, logging and rate limiting.
- [Backend Domains](./domains.md) — per-domain models, APIs, services, routers.
- [Frontend Architecture](./frontend.md) — shell, routes, clients and SSR rules.
- [Go Microservices](./go-services.md) — the shared conventions and ownership boundary
  of `indicator-service` and `mcp-gateway`.
- [MCP Gateway](../integrations/mcp-gateway.md) — MCP transport, tool surface and
  data-plane client behaviour.
- [Market Data Providers](./market-data-providers.md) — gateways, the endpoint cache and
  the service-to-service data-plane contract.
- [Charting](./charting.md) — chart surface, panes, indicators, price alerts.
- [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md) — drawing plugins,
  drawing persistence and the snapshot/rewind pipeline.
- [Realtime, Background Jobs & the Worker](../workflows/realtime-and-background-jobs.md)
  — task semantics, the price-update cascade, Pub/Sub fan-out, sync-status keys.
- [User Preferences](../concepts/user-preferences.md) — the per-user preferences column
  and its read/write matrix.
- [Authentication & Authorization](./authentication.md) — token, 2FA and passkey flows.
- [External Services & Adapters](../integrations/external-services.md) — EODHD,
  Wealthsimple, the AI endpoint, SMTP, Redis and the indicator sidecar.
- [Development, CI & Change Workflows](../operations/workflows.md) and
  [Testing & Verification](../operations/testing.md).
- [Quickstart](../quickstart.md) — the short onboarding path through these pages.
