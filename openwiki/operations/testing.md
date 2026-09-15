# Testing

## Backend tests

Tests live in `/tests` and use `pytest` against a throwaway PostgreSQL container (via `testcontainers`), or a `TEST_DATABASE_URL` when one is supplied. Tests must not depend on any other external service: Redis, HTTP APIs, and SMTP are all mocked. `tests/conftest.py` sets required environment variables before the app is imported:

```python
SECRET_KEY = "..."
ENVIRONMENT = "test"
STUB_EXTERNAL_API = "true"
```

### Test layout

| Directory | Focus |
|-----------|-------|
| `tests/routers/` | FastAPI endpoint tests (auth, accounts, portfolios, market, integration, documents, notes) |
| `tests/services/` | Service-layer tests (account, auth, market, position) |
| `tests/repositories/` | Repository tests (SQLAlchemy) |
| `tests/tasks/` | Huey task tests (integration, market) |
| `tests/commands/` | CLI command tests |
| `tests/fixtures/` | Shared fixtures for auth, accounts, market |
| `tests/test_main.py` | Smoke test for app startup |

### Key fixtures

- `test_engine` (function scope) — creates the schema per test in the Postgres container and drops it after.
- `db_session` (function scope) — provides an `AsyncSession` and rolls back at the end.
- `seed_reference_data` — seeds `AccountTypeModel` and `InstitutionModel`.
- `auth_client` / `unauth_client` — HTTPX async clients with configured auth fixtures.
- `global_mocks` (session scope, autouse) — patches the WebSocket manager and Huey dashboard.
- `fake_redis_manager` (function scope, autouse) — replaces the shared `src.core.redis.redis_manager` client with an in-memory fake (`tests/fixtures/redis.py`); `mock_redis_storage` exposes the backing store for assertions.

### Running backend tests

```bash
# From inside the backend container
docker compose exec backend uv run pytest

# With xdist parallelism (configured in pyproject.toml)
docker compose exec backend uv run pytest -n auto
```

## Frontend tests

The frontend uses Vitest with `jsdom` and `@testing-library/svelte`.

- `frontend/vite.config.ts`: `environment: 'jsdom'`, `setupFiles: ['./src/setupTest.ts']`, includes `src/**/*.{test,spec}.{js,ts}`.
- `frontend/src/setupTest.ts`: imports `@testing-library/jest-dom/vitest` and stubs `window.location`.

Existing tests:

- `frontend/src/lib/components/auth/login-form.test.ts`
- `frontend/src/lib/components/auth/signup-form.test.ts`
- `frontend/src/lib/api/apiClient.test.ts`

Because SvelteKit runtime modules such as `$app/forms` and `$app/paths` are not available in `jsdom`, tests manually mock them.

### Running frontend tests

```bash
# From inside the frontend container
docker compose exec frontend npm run test:run
```

## Test checks in CI

CI runs the full matrix. Backend tests run with no Redis service and no database service — Redis is mocked and PostgreSQL is provided by `testcontainers`. Frontend tests run `npm run check`, `npm run lint`, and `npm run test:run`.

## What to run before committing

For backend changes:

```bash
uv run ruff check
uv run ruff format --check
uv run ty check
uv run pytest
```

For frontend changes:

```bash
npm run check
npm run lint
npm run test:run
```

For database model changes, also generate and commit an Alembic migration:

```bash
uv run alembic revision --autogenerate -m "add x to y"
```
