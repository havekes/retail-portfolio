# Coding Agent Guide: retail-portfolio

## Project Overview
`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Tech Stack**:
- Python 3.14+
- FastAPI backend
- SQLAlchemy ORM
- uv package manager
- Docker & Docker Compose for deployment

## Prerequisites
- Python 3.14 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Docker and Docker Compose

## Running the App
**Preferred**: Use Docker Compose.
```
docker compose up
```
App available at `http://127.0.0.1:8001`.

- Ping endpoint: `http://127.0.0.1:8001/api/ping` (returns `{"ping": "pong"}`)
- Interactive API docs: `http://127.0.0.1:8001/redoc`

## Development Workflow
1. Activate venv: `source .venv/bin/activate`
2. Run `basedpyright` checks: `docker compose exec -T backend uv run basedpyright`
3. Lint code: `docker compose exec backend -T uv run ruff check`
4. Run tests: `docker compose exec backend -T uv run pytest`

**MANDATORY**: When writing or editing code, **ALWAYS** run linting (`uv run ruff check`) and tests (`uv run pytest`) before submitting.

## Backend Architecture Layers
Modular structure with clear separation of concerns:

- **Routers**
  - FastAPI route handlers
  - Define route params, payloads, return types, validation
  - Delegate to services (business logic) or repositories (simple CRUD)

- **Services**
  - Business logic layer
  - Orchestrate complex operations
  - Depend on repositories for data access

- **Repositories**
  - Data access abstraction
  - Abstract base class defines interface
  - **Always return schemas (never models)**
  - Concrete: SQLAlchemy implementation

- **Schemas** (Pydantic models)
  - Define data structures for all app communications
  - Naming conventions:
    - `Read` suffix: GET endpoint returns
    - `Write` suffix: POST/PATCH payloads

- **Models**
  - SQLAlchemy DB models
  - Used to generate Alembic migrations

- **External**
  - Wrappers for 3rd-party APIs
  - Use schemas for params/returns
  - Reusable as services

**Supporting Modules**:
- **Config**: App-wide typed configuration schema
- **Commands**: CLI commands

Follow these conventions strictly for consistency.
