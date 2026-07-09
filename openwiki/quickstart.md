# retail-portfolio

`retail-portfolio` is a portfolio tracker for retail investors. It is a full-stack TypeScript/Python application.

- **Backend:** Python 3.14, FastAPI, SQLAlchemy 2 async, PostgreSQL, Alembic, Huey (Redis), `svcs` dependency injection
- **Frontend:** SvelteKit 2, Svelte 5, Vite, Tailwind 4, shadcn-svelte, lightweight-charts
- **Infra:** Docker Compose for local development, GitHub Actions for CI, OpenWiki for recurring docs

This wiki covers architecture, domain logic, operational runbooks, testing, and the OpenSpec change workflow. Start with [Architecture Overview](./architecture/overview.md) for the backend structure and [Frontend Architecture](./architecture/frontend.md) for the SvelteKit side.

## Run the app locally

The only supported local run path is Docker Compose.

1. Copy environment examples:
   ```bash
   cp src/.env.example src/.env
   cp frontend/.env.example frontend/.env
   ```
2. Start services:
   ```bash
   docker compose up -d
   ```
3. Verify:
   - App: `http://localhost:8001`
   - Frontend: `http://localhost:8100/`
   - API docs: `http://localhost:8001/redoc`
   - Ping: `http://localhost:8001/api/ping`
   - Mail catcher: `http://localhost:8003`

Run backend commands inside the container:

```bash
docker compose exec backend uv run pytest
docker compose exec backend uv run ruff check
docker compose exec backend uv run ty check
docker compose exec backend uv run alembic revision --autogenerate -m "message"
```

Frontend commands are run inside `frontend/`:

```bash
npm install
npm run lint
npm run check
npm run test:run
```

See [Operations & Workflows](./operations/workflows.md) and [Testing](./operations/testing.md) for details.

## Project organization

| Path | Purpose |
|------|---------|
| `src/` | FastAPI backend, organized by domain |
| `frontend/` | SvelteKit SSR app |
| `migrations/` | Alembic migrations |
| `tests/` | Backend pytest suites |
| `openspec/` | Canonical specs and active/archived change artifacts |
| `.agent/`, `.claude/`, `.github/skills/` | Agent skill definitions for OpenSpec |
| `.github/workflows/` | CI, OpenWiki update automation |

## Domain overview

The backend is split into business domains. Each domain uses a layered internal structure: models, schemas, repositories, services, APIs, and routers.

| Domain | Concern | Key entry points |
|--------|---------|------------------|
| `src/account` | Accounts, positions, portfolios, institutions | `src/account/router.py`, `src/account/service/`, `src/account/model.py` |
| `src/auth` | Users, JWT, email verification, authorization | `src/auth/router.py`, `src/auth/api.py`, `src/auth/service.py` |
| `src/market` | Securities, prices, watchlists, alerts, notes, documents, technical indicators, AI analysis | `src/market/router.py`, `src/market/service.py`, `src/market/api.py`, `src/market/ai_service.py` |
| `src/integration` | Broker integrations (Wealthsimple) | `src/integration/router.py`, `src/integration/brokers/wealthsimple.py`, `src/integration/task.py` |
| `src/ws` | WebSocket fan-out via Redis Pub/Sub | `src/ws/router.py`, `src/ws/manager.py` |
| `src/core` | Shared exceptions, email service | `src/core/exception.py`, `src/core/email.py` |
| `src/config` | Settings, DI registry, DB session manager | `src/config/settings.py`, `src/config/services.py`, `src/config/database.py` |

More detail in [Backend Domains](./architecture/domains.md).

## Frontend overview

The frontend is a SvelteKit Node app. It uses server-side `load` functions for initial data, SvelteKit form actions for mutations, and a domain-organized API client layer under `frontend/src/lib/api/`. Major UI domains live in `frontend/src/lib/components/`.

| Area | Path |
|------|------|
| Routes | `frontend/src/routes/` |
| API clients | `frontend/src/lib/api/` |
| Accounts UI | `frontend/src/lib/components/accounts/` |
| Brokers UI | `frontend/src/lib/components/brokers/` |
| Security actions sidebar | `frontend/src/lib/components/actions-sidebar/` |
| Charts | `frontend/src/lib/components/charts/` |

More detail in [Frontend Architecture](./architecture/frontend.md).

## Change workflow

This repo uses **OpenSpec** for spec-driven changes. Agent skills and slash commands mirror each other across `.agent/`, `.claude/`, and `.github/skills/`.

| Stage | Command / Skill | Purpose |
|-------|-----------------|---------|
| Propose | `/opsx:propose` or `openspec-propose` | Create change artifacts: proposal, design, tasks, delta specs |
| Explore | `/opsx:explore` or `openspec-explore` | Investigate and compare options without writing code |
| Apply | `/opsx:apply` or `openspec-apply-change` | Implement pending tasks from a change |
| Archive | `/opsx:archive` or `openspec-archive-change` | Move change to archive and optionally sync specs |

Canonical specs live in `openspec/specs/<capability>/spec.md`. Active changes live in `openspec/changes/<name>/`. See [Operations & Workflows](./operations/workflows.md) for the OpenSpec details.

## Testing and quality

Backend:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
```

Frontend:

```bash
npm run check
npm run lint
npm run test:run
```

CI runs the same commands on push/PR. See [Testing](./operations/testing.md).

## Generated documentation

This wiki is generated by OpenWiki. The `.github/workflows/openwiki-update.yml` workflow refreshes it daily. Do not hand-edit generated pages unless asked; prefer updating source docs and letting OpenWiki regenerate.
