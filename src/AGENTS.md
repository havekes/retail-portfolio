Coding Agent Guide: retail-portfolio (Backend)

## Project Overview

`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Backend Tech Stack**:
- Python 3.14
- FastAPI
- SQLAlchemy ORM with async support
- PostgreSQL
- Pydantic for data validation and serialization
- uv package manager
- ty for type checking
- ruff for linting and formatting
- pytest for testing

**Infrastructure**:
- Docker Compose for dev environment

**Architecture Pattern**: Domain-Driven Design with layered internal structure (Backend)

## Development Workflow

**ALWAYS**: Execute backend commands in the backend service (`docker compose exec backend`).

**Backend Workflow**:
1. Lint code: `docker compose exec backend uv run ruff check`
2. Run type checks: `docker compose exec backend uv run ty check`
3. Run tests: `docker compose exec backend uv run pytest`
4. Format code: `docker compose exec backend uv run ruff format`
5. Generate migrations: `docker compose exec backend uv run alembic revision --autogenerate -m "message"`

**Agent harness**: Prefer `./scripts/agent-test tests/...` (targeted, fail-fast) while developing and `./scripts/agent-test` (full backend regression) before finishing. It runs lint/type checks first, sanitizes output, and caps it so context isn't flooded. See root `AGENTS.md` for details.

**MANDATORY**: When writing or editing code, **ALWAYS** run linting, type checks, tests and format before submitting.
**MANDATORY**: When editing a backend model, also generate the migrations using alembic.
**MANDATORY**: All migration files MUST follow the Alembic standard `<hash>_<description>.py` naming. For manual SQL migrations, create a standard revision using the autogenerate command and use `op.execute()` inside it.

## Testing

**MANDATORY**: Backend tests MUST NOT depend on external services — no Redis, no HTTP APIs (EODHD, broker APIs), no SMTP, no DNS resolution. Mock every outbound client and stub **every** method the code under test calls.

Rationale: CI runs the suite without a Redis server. A test that dials `redis://redis:6379/0` only passes inside Docker where the Compose hostname resolves; on a host or in CI it fails with `socket.gaierror`/`ConnectionError` and takes the suite down with it. The same applies to unmocked HTTP/SMTP calls.

- Redis is mocked globally by the autouse `fake_redis_manager` fixture (`tests/fixtures/redis.py`) on the shared `src.core.redis.redis_manager` singleton. Do not add a real Redis dependency; reuse `mock_redis_storage` when you need to assert on stored keys.
- HTTP/external APIs must be stubbed (see `src/stubs/`) or patched (`StubEodhdGateway`, `StubWealthsimpleAPI`); SMTP is patched (`src.core.email.aiosmtplib.SMTP`).
- The ephemeral PostgreSQL container from `testcontainers` (see `tests/conftest.py`) is the one allowed infrastructure dependency; repository/migration tests may use it.
- A test that performs a real network, Redis, or SMTP call is broken by definition — mock it, do not "fix" it by expecting the service to be up.

## Backend Architecture

### Overall Structure: Domain-Driven Design with Internal Layers

The codebase is organized by **business domains**, where each domain is self-contained and communicates with other domains through public APIs.

```
src/
├── account/       # Account & position management domain
├── auth/          # User authentication & authorization
├── market/        # Securities & market data
├── integration/   # Broker integrations (Wealthsimple, etc.)
├── config/        # Application configuration & setup
└── main.py        # FastAPI app entry point
```

### Internal Domain Structure

Each domain follows a consistent **layered architecture**:

```
domain/
├── model.py                  # SQLAlchemy ORM models
├── schema.py                 # Pydantic models for data transfer
├── repository.py             # Abstract repository interfaces
├── repository_sqlalchemy.py  # Concrete SQLAlchemy implementations
├── repository_*.py           # Alternative implementations (external APIs, cache, etc.)
├── api.py                    # Public APIs for inter-domain communication
├── service.py                # Business logic (orchestration, calculations)
├── router.py                 # FastAPI route handlers
├── api_types.py              # Public type definitions (for cross domain communication)
├── enum.py                   # Domain-specific enums
└── commands/                 # CLI commands (seeding, etc.)
```

### Layering Principles

**Models** → SQLAlchemy ORM models for database schema

- Used to generate Alembic migrations
- Should never be returned to clients

**Schemas** → Pydantic models for all data transfer

- **Repositories ALWAYS return schemas, never models**
- Used between routers and services
- **Do not use outside the domain** (use API type instead)
- Naming conventions:
  - `*Read` suffix: Data returned from GET endpoints
  - `*Write` suffix: Data accepted by POST/PATCH endpoints

**Repositories** → Data access abstraction layer

- Abstract interfaces define the contract
- Multiple implementations support different backends:
  - `repository_sqlalchemy.py` - Database access
  - `repository_cache.py` - Cached access
  - `repository_*.py` - Other implementation (ex: external apis)
- Always return schemas for consistency

**Services** → Business logic & orchestration

- Handle complex operations spanning multiple repositories
- Depend on repositories for data access
- Can depend on other domain APIs

**APIs** → Public domain interfaces for inter-domain communication

- Each domain exposes public APIs (e.g., `AccountApi`, `MarketPricesApi`)
- Other domains call these APIs rather than accessing repositories directly
- Enables loose coupling and clear domain boundaries
- Injected as dependencies via the `svcs` service container

**API types** → Public schemas for inter-domain communication

- Types exposed for cross-domain communication
- Expose this instead of a schema

**Routers** → FastAPI HTTP endpoints

- Define route parameters, payloads, return types
- Validate requests via Pydantic schemas
- Delegate to services or APIs for complex business logic
- Depend on `current_user` for authentication
- Use `AuthorizationApi` to verify user ownership of resources

### Dependency Injection & Service Container

Uses the `svcs` library for dependency injection:

- **Service Registration**: `config/services.py` registers all APIs, repositories, and services
- **Factory Functions**: Each domain exports factory functions (e.g., `register_account_apis()`)
- **Request-Scope Injection**: Services are injected into route handlers via FastAPI dependencies
- **Clean Separation**: Routers depend on interfaces, not implementations

### Cross-Domain Communication Example

```
PositionService (account domain)
  └─ Depends on:
      ├─ PositionRepository (account domain)
      ├─ MarketPricesApi (market domain) ← Cross-domain dependency
      └─ SecurityApi (market domain) ← Cross-domain dependency
```

When calculating account totals:

1. Router calls `PositionService.get_account_totals()`
2. Service fetches positions from repository
3. For each position, queries `SecurityApi` and `MarketPricesApi` for pricing
4. Computes totals with current prices

### Do's and don'ts

- **Do** use custom types for entity `Ids` (ex: `type AccountId = UUID`)
- **Do** use `rich.print` (aliased as `rprint`) for terminal output in CLI commands to avoid linting issues.
- **Don't** raise HTTPException from within a service (except Authorization service). Instead raise a custom exception and handle it in the router.

### Critical Rules

- **Always return schemas from repositories** - Never expose ORM models
- **Use APIs and API types for cross-domain access** - Don't call other domains' repositories directly
- **Factories register services** - Never create service instances manually
- **Type everything** - Use Pydantic models and type hints consistently
