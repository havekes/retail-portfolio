# Architecture Overview

`retail-portfolio` is a domain-driven FastAPI backend plus a SvelteKit SSR frontend.

## Backend architecture

The backend uses Python 3.14, FastAPI, async SQLAlchemy with PostgreSQL, and `svcs` for dependency injection.

### Entry points

| File | Responsibility |
|------|----------------|
| `src/main.py` | FastAPI app, lifespan (migrations, DI registry, WebSocket, Huey dashboard), CORS, global exception handlers, router wiring, `/api/ping` |
| `src/worker.py` | Huey consumer setup; Redis in prod/staging, memory in `test`; attaches its own `svcs` registry |
| `src/commands/seed.py` | Standalone CLI seed command for reference data and dev fixtures |

`src/main.py` includes routers from each domain and registers all services in `lifespan_context` via `src/config/services.py`.

### Domain-driven internal layers

Each backend domain under `src/` follows the same layered shape:

```
domain/
├── model.py                  # SQLAlchemy ORM models
├── schema.py                 # Pydantic DTOs for HTTP and service boundaries
├── api_types.py              # Public types for cross-domain calls
├── repository.py             # Abstract repository interfaces
├── repository_sqlalchemy.py  # SQLAlchemy implementations
├── repository_<other>.py      # External/cache implementations (e.g., cache, EODHD)
├── api.py                    # Public domain APIs used by other domains
├── service.py                # Business logic / orchestration
├── router.py                 # FastAPI HTTP routes
├── enum.py                   # Domain enums
└── exception.py              # Domain exceptions
```

Key rules from `src/AGENTS.md`:

- **Repositories return schemas, never ORM models.**
- **Services call other domains only through their public `api.py` APIs and `api_types.py`.**
- **Routers handle HTTP concerns; services do not raise `HTTPException` except for authorization.**
- **Domain APIs are registered as factory singletons with `svcs`.**

### Dependency injection

Dependency injection is centralized in `src/config/services.py`. Each domain exports a `register_*_services(registry)` function. The registry is created in `src/main.py` lifespan and attached to the FastAPI app state.

```python
registry = svcs.Registry()
app.state.svcs_registry = registry
register_services(registry, sessionmanager)
```

Request-scoped service instances are resolved via FastAPI’s `svcs` `DepContainer`, for example:

```python
async def get_accounts(services: DepContainer) -> list[AccountRead]:
    api = await services.aget(AccountApi)
    ...
```

The worker uses a separate `Registry` with a `DatabaseSessionManager` configured with `NullPool` (`src/worker.py`) to avoid async engine issues across task cycles.

### Cross-domain example

`account.PositionService` is a typical orchestrator:

```
PositionService (account domain)
├── PositionRepository        (account domain)
├── MarketPricesApi             (market domain) ← cross-domain
├── SecurityApi                 (market domain) ← cross-domain
└── IntegrationAccountApi       (integration domain) ← cross-domain
```

When routers need to aggregate data (e.g., account totals), they call a service; the service fetches its own domain data and calls public APIs of other domains for pricing or broker sync.

### Data and state

- **Database:** PostgreSQL (`asyncpg` in prod, `psycopg2-binary` for Alembic sync operations), managed by `DatabaseSessionManager` in `src/config/database.py`.
- **Migrations:** Alembic, configured in `pyproject.toml` with `script_location = migrations`. `migrations/env.py` imports all domain models onto `BaseModel.metadata`.
- **Redis:** used for Huey task queue and WebSocket cross-process fan-out.
- **External dependencies:** EODHD for market data, Wealthsimple API for broker integration, OpenAI-compatible endpoint for AI features.
- **Stubbing:** `STUB_EXTERNAL_API=true` (set in tests and configurable in `.env`) registers stub gateways/services so CI/tests run without credentials.

### Background work

Background tasks use Huey (`src/worker.py`):

- `src/integration/task.py`: syncs broker positions, sends WebSocket sync progress events.
- `src/market/task.py`: daily price update and async AI note-title generation.

A Huey dashboard is mounted by `src/main.py` under `/worker/api`.

### WebSockets

`src/ws/manager.py` maintains per-user WebSocket connections and uses Redis Pub/Sub channel `ws_messages` to fan out messages across worker/backend processes. It falls back to local broadcast if Redis is unavailable. Auth uses a signed 30-second ticket (`auth/router.py` `/ws-ticket`) or the `auth_token` cookie / `sec-websocket-protocol` header.

### Error handling

`src/main.py` registers global exception handlers:

- `EntityNotFoundError` → `404`
- `AuthorizationError` → `404` (hides existence)
- Catch-all → `500`, with error details hidden in production

A CORS middleware safety net (`cors_exception_middleware`) adds CORS headers even on unhandled exceptions.

## Frontend architecture

The frontend is a SvelteKit 2 / Svelte 5 Node SSR app.

| Concern | Location | Notes |
|---------|----------|-------|
| Routes | `frontend/src/routes/` | Server `load` + form actions + page components |
| API clients | `frontend/src/lib/api/` | One client per domain, factory + singleton pattern |
| Components | `frontend/src/lib/components/` | Domain grouped: accounts, brokers, actions-sidebar, charts, ui |
| Types | `frontend/src/lib/types/`, `frontend/src/lib/api/types/` | Mirror backend schemas |
| State | `*.svelte.ts` class modules, Svelte context | Runes-based, `$state`/`$derived`/`$effect` |
| Auth | `frontend/src/hooks.server.ts` | Validate JWT `auth_token` cookie, redirect unauthenticated users |

The frontend communicates with the backend at `/api`. During SSR it can use an internal base URL; in the browser it uses the public API base.

See [Backend Domains](./domains.md) for per-domain backend details and [Frontend Architecture](./frontend.md) for UI specifics.
