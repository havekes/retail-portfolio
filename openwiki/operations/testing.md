# Testing

## Backend tests

Tests live in `/tests` and use `pytest` with in-memory SQLite (`sqlite+aiosqlite:///:memory:`). `tests/conftest.py` sets required environment variables before the app is imported:

```python
DATABASE_URL="sqlite+aiosqlite:///:memory:"
SECRET_KEY="..."
ENVIRONMENT="test"
STUB_EXTERNAL_API="true"
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

- `test_engine` (function scope) — creates the SQLite schema per test and drops it after.
- `db_session` (function scope) — provides an `AsyncSession` and rolls back at the end.
- `seed_reference_data` — seeds `AccountTypeModel` and `InstitutionModel`.
- `auth_client` / `unauth_client` — HTTPX async clients with configured auth fixtures.
- `global_mocks` (session scope, autouse) — patches WebSocket manager and Huey dashboard to avoid Redis timeouts.

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

CI runs the full matrix. Backend tests run with Redis in a service container and an in-memory SQLite database. Frontend tests run `npm run check`, `npm run lint`, and `npm run test:run`.

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
