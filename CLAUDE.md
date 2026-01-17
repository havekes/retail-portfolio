# Coding Agent Guide: retail-portfolio

## Project Overview
`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Tech Stack**:
- Python 3.14
- FastAPI backend
- SQLAlchemy ORM
- uv package manager
- Docker Compose for dev environement

## Development Workflow

**ALWAYS**: Execute commands in the correct docker container `docker exec retail-portfolio-backend`

1. Write a feature or fix a bug
2. Lint code: `docker exec retail-portfolio-backend uv run ruff check`
3. Run type checks: `docker exec retail-portfolio-backend -T uv run basedpyright`
4. Run tests: `docker exec retail-portfolio-backend -T uv run pytest`
5. Format code: `docker exec retail-portfolio-backend -T uv run ruff format`

**MANDATORY**: When writing or editing code, **ALWAYS** run linting, type checks, tests and format before submitting.
**MANDATORY**: When editing a model, also generate the migrations using alembic (`docker compo)

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
