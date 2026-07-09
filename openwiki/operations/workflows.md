# Operations & Workflows

## Local development

The supported way to run the application is Docker Compose.

```bash
docker compose up -d
```

After startup:

- App: `http://localhost:8001`
- Backend API / ping: `http://localhost:8001/api/ping`
- ReDoc API docs: `http://localhost:8001/redoc`
- Frontend dev server: `http://localhost:8100`
- Mailcrab (email capture): `http://localhost:8003`

It is recommended to run commands inside containers:

```bash
docker compose exec backend <command>
docker compose exec frontend <command>
```

### Environment files

- Copy `src/.env.example` to `src/.env` for the backend.
- Copy `frontend/.env.example` to `frontend/.env` for the frontend.
- Do not commit `.env` files. `src/.env.example` is the sample backend config; `frontend/.env.example` is the sample frontend config.

### Containers

`docker-compose.yml` defines:

| Service | Image | Ports | Role |
|---------|-------|-------|------|
| backend | `ghcr.io/astral-sh/uv:python3.14-bookworm` | `8001:8000`, `8090:5678` | FastAPI app with hot reload |
| worker | same | `8091:5678` | Huey consumer |
| frontend | `node:latest` | `8002:8100` | SvelteKit dev server |
| postgres | `postgres:18` | `5432:5432` | PostgreSQL |
| redis | `redis:7-alpine` | — | Cache / WebSocket fan-out / Huey broker |
| mailcrab | `marlonb/mailcrab:latest` | `8003:1080` | Email sink for dev |

A production Compose file (`docker-compose.prod.yml`) exists but is not documented in detail in the current sources.

## Backend commands

Run these inside the backend container:

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
uv run ruff format
uv run alembic revision --autogenerate -m "message"
```

When editing a model, generate an Alembic migration and include it in the change. `src/AGENTS.md` flags this as mandatory.

## Frontend commands

Run these inside the frontend container:

```bash
npm run dev
npm run build
npm run check
npm run lint
npm run test:run
```

## CI pipeline

`.github/workflows/ci.yml` runs on push to `main` and on pull requests.

### Backend job

- Python 3.14 with `astral-sh/setup-uv`
- Redis service on port 6379
- Steps:
  1. `uv sync --dev`
  2. `uv run ty check`
  3. `uv run ruff check && uv run ruff format --check`
  4. `uv run pytest` with in-memory SQLite

### Frontend job

- Node 25
- `npm install` inside `frontend/`
- Copy `frontend/.env.example` → `frontend/.env`
- `npm run check`
- `npm run lint`
- `npm run test:run`

## OpenWiki update workflow

`.github/workflows/openwiki-update.yml` is scheduled daily at 08:00 UTC and can be triggered manually.

Steps:

1. Check out the repository.
2. Install `openwiki` globally with npm.
3. Run `openwiki code --update --print` with the configured model and LangSmith tracing.
4. Open a pull request against `main` with changes under `openwiki/`.

The workflow uses `create-pull-request` so documentation updates land via PR, not direct commits.

## Background jobs

The worker uses Huey with Redis-backed queue. Task modules are imported at worker startup (`src/worker.py`):

- `src.integration.task`
- `src.market.task`

Notable tasks:

- `daily_price_update` — periodic task at midnight to update prices for the last 365 days for all active securities.
- `generate_note_title_task` — asynchronously generates AI note titles.
- `_sync_account_positions_task` — syncs broker positions for an account.

A Huey dashboard is mounted in the FastAPI app at `/worker/api`.

## Spec-driven change workflow (OpenSpec)

This repository uses OpenSpec in `spec-driven` mode.

### Configuration

`openspec/config.yaml` declares `schema: spec-driven`. The canonical specs live in `openspec/specs/<capability>/spec.md`. Active changes live in `openspec/changes/<name>/` and, once archived, move to `openspec/changes/archive/YYYY-MM-DD-<name>/`.

### Stages

The same four skills/commands are mirrored across `.agent`, `.claude`, `.github/skills`, `.claude/commands`, and `.github/prompts`:

| Command | Purpose |
|---------|---------|
| `/opsx:propose` | Create a change, artifacts in dependency order (`proposal.md`, `design.md`, `tasks.md`, delta specs) |
| `/opsx:explore` | Think-only mode; do not write application code (OpenSpec artifacts allowed) |
| `/opsx:apply` | Implement pending tasks from a change; mark checkboxes as completed |
| `/opsx:archive` | Move the change to archive; optionally sync delta specs back to `openspec/specs/` |

### Rules

- Always create changes with `openspec new change "<name>"`, not by hand.
- Read dependency artifacts before writing a new one.
- `context` and `rules` returned by `openspec instructions` are agent-only and must not be copied into artifacts.
- In `/opsx:apply`, read `contextFiles` first, complete each task, and mark `- [ ]` → `- [x]` immediately.
- In `/opsx:archive`, do not auto-select a change; prompt if it is ambiguous.

## Seeding

`src/commands/seed.py` populates reference data (`AccountType`, `Institution`) on every run. In `dev` environment it also seeds a test user, sample securities, accounts, positions, portfolios, and integration users.

## Running in stub mode

Set `STUB_EXTERNAL_API=true` to use stub implementations of the market gateway (`StubAIService`, `StubWealthsimpleApiGateway`) instead of calling EODHD / Wealthsimple live APIs. Tests run in stub mode by default.
