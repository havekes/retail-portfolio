---
type: reference
title: Quickstart & Task Routing
description: Entry point to the retail-portfolio wiki — what the repository is, how to run the Docker Compose stack, where every system lives, and a task-routing table that points backend, frontend, chart, auth, broker-sync, CSV, market-data, AI, integration, money, holdings-read-path, dev-workflow and testing work at the right page.
tags: [quickstart, task-routing, onboarding, repository-map, development-workflow]
verified:
  - by: openwiki/0.5.2
    at: 2026-09-21T14:49:00.510Z
sources:
  - id: openwiki-source-5f5b95b3d6a215fa02ceb945
    resource: repo://.env.example
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-6d4b4e707b8d60b6ccfa3425
    resource: repo://.github/workflows/openwiki-update.yml
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
  - id: openwiki-source-b79fbbd921df689b4bbdc82f
    resource: repo://docker-compose.yml
  - id: openwiki-source-e483fd3285d99d05c7b265cf
    resource: repo://frontend/AGENTS.md
  - id: openwiki-source-09dad1559edc73c5b154a081
    resource: repo://frontend/src/lib/components/holdings/holdings-table.svelte
  - id: openwiki-source-3f8311916804417f28db7f0d
    resource: repo://frontend/src/lib/components/layout/app-sidebar-actions.svelte
  - id: openwiki-source-846f5f71a06546739c7f1ccb
    resource: repo://frontend/src/routes/%2Bpage.server.ts
  - id: openwiki-source-b8584948ed4a6fee33406f78
    resource: repo://frontend/src/routes/accounts/%5Bid%5D/%2Bpage.server.ts
  - id: openwiki-source-899c8715bbba1ad86cff7b6b
    resource: repo://frontend/src/routes/holdings/%2Bpage.server.ts
  - id: openwiki-source-c59fe4336a371ea1052a01dd
    resource: repo://justfile
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-b1543404abfc927178353273
    resource: repo://scripts/agent-test
  - id: openwiki-source-d313a882430947b02725046e
    resource: repo://scripts/docker-gid.sh
  - id: openwiki-source-230f617cb6d47154ef463034
    resource: repo://src/AGENTS.md
generated: { by: "openwiki/0.5.2", at: "2026-09-21T14:49:00.510Z" }
---

# Quickstart & Task Routing

`retail-portfolio` is a portfolio tracker for retail investors: a Python 3.14 / FastAPI
backend (`src/`) with SQLAlchemy 2 async models over PostgreSQL and Alembic migrations, a
Huey worker on Redis (`src/worker.py`), a SvelteKit 2 / Svelte 5 SSR frontend
(`frontend/`), and a stateless Go indicator sidecar (`services/indicator-service/`). Local
development is Docker Compose only; the backend, worker, Compose interpolation and the
frontend dev server all read one root `.env` copied from the tracked `.env.example`.

`AGENTS.md` is the root guide: it delegates backend work to `src/AGENTS.md` and frontend
work to `frontend/AGENTS.md`. `CLAUDE.md` is a one-line stub that imports `AGENTS.md` via
`@AGENTS.md` and adds no guidance of its own.

## Run it

```bash
cp .env.example .env
just up        # or: docker compose up -d
```

`just up` starts the stack with the host Docker socket's real group id (discovered by
`scripts/docker-gid.sh`, overridable with `DOCKER_GID`), which is what lets
testcontainers-backed tests inside the containers reach the daemon.

| Service | URL | Port override (root `.env`) |
|---|---|---|
| backend | `http://localhost:8001` (docs at `/redoc`, ping at `/api/ping`) | `BACKEND_PORT` → container `8000` |
| frontend | `http://localhost:8002/` | `FRONTEND_PORT` → container `8100` |
| mailcrab (dev SMTP inbox) | `http://localhost:8003` | `MAILCRAB_PORT` |
| indicator service | `http://localhost:8085` | `INDICATOR_SERVICE_PORT` |
| PostgreSQL | `localhost:5432` | `POSTGRES_PORT` |
| debugpy (backend / worker) | `localhost:8090` / `localhost:8091` | `BACKEND_DEBUG_PORT`, `WORKER_DEBUG_PORT` |

Every one of those ports is Compose-interpolated from the root `.env`, so change ports
there rather than in `docker-compose.yml`. `src/.env` and `frontend/.env` are obsolete —
move any custom values into the root `.env` and delete them.

CI (`.github/workflows/ci.yml`) runs the same verification in three jobs: backend
(`uv run ty check`, `ruff check` + `ruff format --check`, `pytest`), frontend
(`npm run check`, `npm run lint`, `npm run test:run`) and indicator-service
(`go vet`, `go build`, `go test`).

## Where things live

| Path | What it owns |
|------|--------------|
| `src/` | FastAPI backend, split into domains (`account`, `auth`, `market`, `integration`, `ws`) plus cross-cutting `core`, `config` and `worker_dashboard` |
| `frontend/` | SvelteKit SSR app: routes, services, API clients, components |
| `services/indicator-service/` | Go indicator sidecar (stateless calculator) |
| `migrations/` | Alembic revisions |
| `tests/` | Backend pytest suites, organized by domain and layer |
| `src/stubs/` | Stub external gateways used by tests and `STUB_EXTERNAL_API` mode |
| `src/commands/` | Seeding and market-data flush CLI entrypoints |
| `openspec/` | Canonical capability specs and active/archived change artifacts |
| `scripts/` | `agent-test` harness, `setup-agent-worktree.sh`, `docker-gid.sh` |
| `.github/workflows/` | CI (`ci.yml`) and the scheduled OpenWiki refresh (`openwiki-update.yml`) |

## If you are changing X, read Y

| You are changing… | Read |
|---|---|
| Anything at the system level: processes, startup, request flow, layer rules | [Architecture Overview](./architecture/overview.md) |
| A backend domain: add a route/service/repository, or touch `account`, `auth`, `market`, `integration`, `ws`, `core` | [Backend Domains](./architecture/domains.md) |
| `Settings`, the root `.env` contract, the `svcs` registry, DB/Redis managers, middleware | [Configuration, DI & Cross-Cutting Runtime](./architecture/configuration.md) |
| SvelteKit routes, `load`/form actions, API clients, runes-based services, SSR pitfalls | [Frontend Architecture](./architecture/frontend.md) |
| Charts, drawing tools, indicator overlays, chart snapshots/rewind, finance math | [Charting, Drawing Tools & Rewind](./architecture/charting.md) |
| Signup/login, the `auth_token` JWT, 2FA/TOTP, passkeys, ownership authorization, the WS ticket | [Authentication & Authorization](./architecture/authentication.md) |
| Broker connect, Wealthsimple login/OTP, position import and the Huey sync task | [Broker Connect, Import & Position Sync](./workflows/broker-sync.md) |
| CSV templates, account discovery, the inspect → import → sync lifecycle | [CSV Account Import & Sync](./workflows/csv-import.md) |
| Price fetches/backfill, daily & intraday tasks, the downstream recalc/alert cascade, indicator computation | [Market Data, Indicators & the Price Update Cascade](./workflows/market-data-and-indicators.md) |
| AI context assembly, fundamentals/notes/debate endpoints, the async title task | [AI Analysis Flows](./workflows/ai-analysis.md) |
| An outbound dependency: EODHD, Wealthsimple, the AI endpoint, SMTP/mailcrab, Redis, the indicator sidecar | [External Services & Adapters](./integrations/external-services.md) |
| Money, currency conversion, totals, holdings/P&L math, rounding | [Money & Currency Handling](./concepts/money-and-currency.md) |
| The holdings read path: the accounts dashboard, `/accounts/[id]`, cross-account `/holdings`, holdings table columns/grouping/preferences | [Accounts & Holdings Views](./workflows/accounts-and-holdings-views.md) |
| How to run, ship and change: Compose stack, in-container commands, agent-test harness, worktrees, migrations, CI, OpenSpec | [Development, CI & Change Workflows](./operations/workflows.md) |
| The pytest/Vitest layout, fixtures, mandatory mocking, harness gates, CI matrix | [Testing & Verification](./operations/testing.md) |

## Non-negotiables

These rules come from `AGENTS.md`, its per-area guides (`src/AGENTS.md`,
`frontend/AGENTS.md`) and the OpenWiki block at the end of `AGENTS.md`, and hold for every
task:

- **Docker-only commands.** All development commands run inside the containers:
  `docker compose exec <backend|frontend> <command>`. The host is never the reference
  environment; CI runs the same checks.
- **Use the agent harness.** `./scripts/agent-test` (shorthand `just test`) is the primary
  test entrypoint. It runs inside Docker for you, sanitizes and caps output, and offers
  **Gate 0** (lint + type checker; halts before tests on failure), **Gate 1** (a path
  argument — targeted, fail-fast) and **Gate 2** (no path — full suite with a two-tier
  Index/Traces summary). Flags: `--backend` / `--frontend`, `--all`, `--no-gate0`,
  `--gate0-only`, `--local`, `--json`, `--max-chars N`. Raw
  `docker compose exec … pytest`/`vitest` is the fallback if the harness itself breaks.
- **Model edits require a migration.** Editing a backend model means generating the Alembic
  revision in the same change; migration files follow `<hash>_<description>.py` naming, and
  manual SQL goes through `op.execute()` inside a standard revision.
- **Tests never touch external services.** Mock all outbound I/O — Redis, HTTP APIs (EODHD,
  broker APIs), and SMTP in the backend; all API calls in the frontend. The ephemeral
  testcontainers PostgreSQL is the only allowed infrastructure dependency. A test that makes
  a real network/Redis/SMTP call is broken by definition; mock it, don't expect the service
  to be up.
- **Parallel agents isolate with git worktrees.** Use
  `scripts/setup-agent-worktree.sh <worktree-path> <branch-name>`, which discovers free ports
  and generates a worktree `.env`, before starting that worktree's Compose stack — otherwise
  files and Docker resources collide.
- **Spec-driven changes.** Non-trivial work goes through OpenSpec in `openspec/`
  (propose → apply → archive); canonical specs live in `openspec/specs/<capability>/spec.md`.
- **The generated wiki is optional context.** `openwiki/` is a generated evidence index, not
  required startup reading. Source code and tests are authoritative: when a page and the code
  disagree, trust the code and report the drift. Unknowns in an agent brief are verification
  gaps, not automatic requirements; prefer the narrowest quiet validation that proves the
  changed behavior, and preserve complete failure output. Do not hand-edit generated pages —
  update source/docs and let the scheduled OpenWiki workflow regenerate them.
