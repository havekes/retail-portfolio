# Coding Agent Guide: retail-portfolio

## Project Overview
`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Tech Stack**:
- Python 3.14
- FastAPI backend with svcs (dependency injection)
- SQLAlchemy ORM with async support
- Pydantic for data validation and serialization
- uv package manager
- Docker Compose for dev environment
- basedpyright for type checking
- ruff for linting and formatting
- pytest for testing

**Architecture Pattern**: Domain-Driven Design with layered internal structure

## Development Workflow

**ALWAYS**: Execute commands in the correct docker container `docker exec retail-portfolio-backend`

1. Write a feature or fix a bug
2. Lint code: `docker exec retail-portfolio-backend uv run ruff check`
3. Run type checks: `docker exec retail-portfolio-backend uv run basedpyright src`
4. Run tests: `docker exec retail-portfolio-backend uv run pytest`
5. Format code: `docker exec retail-portfolio-backend uv run ruff format`

**MANDATORY**: When writing or editing code, **ALWAYS** run linting, type checks, tests and format before submitting.
**MANDATORY**: When editing a model, also generate the migrations using alembic (`docker compo)

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
├── repository_*.py           # Alternative implementations (external APIs, etc.)
├── api.py                    # Public APIs for inter-domain communication
├── service.py                # Business logic (orchestration, calculations)
├── router.py                 # FastAPI route handlers
├── api_types.py              # Public type definitions
└── enum.py                   # Domain-specific enums
```

### Layering Principles

**Models** → SQLAlchemy ORM models for database schema
- Used to generate Alembic migrations
- Should never be returned to clients

**Schemas** → Pydantic models for all data transfer
- **Repositories ALWAYS return schemas, never models**
- Used between routers, services, and domain boundaries
- Naming conventions:
  - `*Read` suffix: Data returned from GET endpoints
  - `*Write` suffix: Data accepted by POST/PATCH endpoints

**Repositories** → Data access abstraction layer
- Abstract interfaces define the contract
- Multiple implementations support different backends:
  - `repository_sqlalchemy.py` - Database access
  - `repository_eodhd.py` - External API (EODHD)
  - `repository_wealthsimple.py` - External API (Wealthsimple)
- Always return schemas for consistency

**Services** → Business logic & orchestration
- Handle complex operations spanning multiple repositories
- Calculate derived values (e.g., account totals, currency conversion)
- Depend on repositories for data access
- Can depend on other domain APIs

**APIs** → Public domain interfaces for inter-domain communication
- Each domain exposes public APIs (e.g., `AccountApi`, `MarketPricesApi`)
- Other domains call these APIs rather than accessing repositories directly
- Enables loose coupling and clear domain boundaries
- Injected as dependencies via the service container

**Routers** → FastAPI HTTP endpoints
- Define route parameters, payloads, return types
- Validate requests via Pydantic schemas
- Delegate to services or APIs for business logic
- Depend on `current_user` for authentication
- Use `AuthorizationApi` to verify user ownership of resources

### Key Domains

**Account Domain** (`src/account/`)
- Manages investment accounts and positions
- `AccountApi` and `PositionApi` expose position data
- `PositionService` calculates account totals by fetching prices from market data

**Auth Domain** (`src/auth/`)
- User authentication and authorization
- `UserApi` handles login/signup/token validation
- `AuthorizationApi` verifies user ownership of resources

**Market Domain** (`src/market/`)
- Securities data and current pricing
- `SecurityApi` resolves securities and their details
- `MarketPricesApi` fetches current prices (from EODHD or cache)
- `EodhdGateway` wraps the EODHD external API

**Integration Domain** (`src/integration/`)
- Integrates with external brokers (Wealthsimple, etc.)
- `IntegrationUserService` manages user broker credentials
- Broker gateways implement `BrokerApiGateway` interface
- Syncs accounts and positions to Account domain

**Config Module** (`src/config/`)
- `settings.py` - Environment configuration with Pydantic Settings
- `services.py` - Service container registration and dependency injection
- `database.py` - Async SQLAlchemy session management
- `logging.py` - Logging configuration

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

### Critical Rules

- **Always return schemas from repositories** - Never expose ORM models
- **Use APIs for cross-domain access** - Don't call other domains' repositories directly
- **Factories register services** - Never create service instances manually
- **Type everything** - Use Pydantic models and type hints consistently
- **Test in isolation** - Mock dependencies, test one layer at a time
