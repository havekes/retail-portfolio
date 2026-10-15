---
type: reference
title: Quickstart & Task Routing
description: Entry point to the retail-portfolio wiki — what the repository is, how the Docker Compose stack runs from the single root .env, which container owns what (backend, worker, frontend, indicator-service, mcp-gateway, postgres, redis, mailcrab), the current host ports, and a task-routing table that sends any change to exactly one owning page.
tags: [quickstart, task-routing, onboarding, repository-map, development-workflow, openwiki]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-15T13:03:07.448Z
sources:
  - id: openwiki-source-98710b2923699ef9451ad58b
    resource: repo://.ai/reviews/2026-10-09-architecture-go-services.md
  - id: openwiki-source-894a8d47cf899acdc1b875c0
    resource: repo://.ai/skills/orchestration/SKILL.md
  - id: openwiki-source-741d60254bffee1f54b62b5c
    resource: repo://.claude/agents/arch-reviewer.md
  - id: openwiki-source-5f5b95b3d6a215fa02ceb945
    resource: repo://.env.example
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-6d4b4e707b8d60b6ccfa3425
    resource: repo://.github/workflows/openwiki-update.yml
  - id: openwiki-source-618752d6f11341db792d17ef
    resource: repo://.opencode/opencode.json
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-ebee543967c6f3e7a101e271
    resource: repo://alembic.ini
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
  - id: openwiki-source-11ef2d56dffda152beeb9f84
    resource: repo://docker-compose.prod.yml
  - id: openwiki-source-b79fbbd921df689b4bbdc82f
    resource: repo://docker-compose.yml
  - id: openwiki-source-e483fd3285d99d05c7b265cf
    resource: repo://frontend/AGENTS.md
  - id: openwiki-source-0bdf50a0b0b0618dd3a5abe8
    resource: repo://frontend/src/hooks.server.ts
  - id: openwiki-source-45599bb9a8794a9c90b7e20d
    resource: repo://frontend/src/lib/api/apiClient.ts
  - id: openwiki-source-8a88da80cc6ed6d98b2035f2
    resource: repo://frontend/src/lib/api/userPreferencesService.ts
  - id: openwiki-source-0a9a504227d25141ac6e3e3a
    resource: repo://frontend/src/lib/components/charts/plugins/valuation-band/valuation-band.ts
  - id: openwiki-source-277415f21fdc20b26619d18d
    resource: repo://frontend/src/lib/components/charts/security-chart.svelte
  - id: openwiki-source-3f8311916804417f28db7f0d
    resource: repo://frontend/src/lib/components/layout/app-sidebar-actions.svelte
  - id: openwiki-source-04059ae9c861b675fbebe0d7
    resource: repo://frontend/src/lib/components/watchlist/watchlistService.svelte.ts
  - id: openwiki-source-ecd4b1167badc1f9ac4ea606
    resource: repo://frontend/src/lib/services/ChartDrawingsService.svelte.ts
  - id: openwiki-source-a8a830617ab03d4b55d49d9a
    resource: repo://frontend/src/routes/%2Blayout.svelte
  - id: openwiki-source-33c886f28072e35f81eadfae
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/%2Bpage.server.ts
  - id: openwiki-source-a680cc2053312375d46bcfe4
    resource: repo://frontend/src/routes/watchlists/%2Bpage.server.ts
  - id: openwiki-source-378e3cf05ab0d05d335c68d5
    resource: repo://frontend/vite.config.ts
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
  - id: openwiki-source-3871c7364a9411872d29e162
    resource: repo://scripts/opencode-go-session-fetch.mjs
  - id: openwiki-source-c347ef400d4d12fd07984865
    resource: repo://scripts/setup-agent-worktree.sh
  - id: openwiki-source-fc76e2092b349ff852ef3b15
    resource: repo://services/README.md
  - id: openwiki-source-de4e7fa85608340db568fc0c
    resource: repo://src/account/service/portfolio.py
  - id: openwiki-source-230f617cb6d47154ef463034
    resource: repo://src/AGENTS.md
  - id: openwiki-source-b251d0144a6ce3e32623e4c2
    resource: repo://src/commands/flush_market_data.py
  - id: openwiki-source-dfd9a181d2f58b1a466b8c27
    resource: repo://src/commands/seed.py
  - id: openwiki-source-e1e5885568a239055161be95
    resource: repo://src/config/services.py
  - id: openwiki-source-11b9d806fcc6dd6e7747ed87
    resource: repo://src/main.py
  - id: openwiki-source-d70f78b70446e1ce1912c7c5
    resource: repo://src/market/data_router.py
  - id: openwiki-source-b5c9dababd9a2ff2d28150b0
    resource: repo://src/market/gateway.py
  - id: openwiki-source-8ba9c7034638e16be9336256
    resource: repo://src/market/repository_sqlalchemy.py
  - id: openwiki-source-47b0223ca650e12504aa1417
    resource: repo://src/market/repository.py
  - id: openwiki-source-d8383d22d61483b00080a280
    resource: repo://src/market/router.py
  - id: openwiki-source-689c3cecf701f8b197038e75
    resource: repo://src/market/task.py
  - id: openwiki-source-c8a9ed75dfc5d7332062ae40
    resource: repo://src/worker_dashboard/router.py
  - id: openwiki-source-7a8d629077019775a9fec3d3
    resource: repo://src/worker.py
  - id: openwiki-source-9c5ae74acc82cf270945cf3d
    resource: repo://src/ws/manager.py
  - id: openwiki-source-d63e02f817074e4280e045ae
    resource: repo://src/ws/router.py
generated: { by: "openwiki/0.7.2", at: "2026-10-15T13:03:07.448Z" }
---

# Quickstart & Task Routing

`retail-portfolio` is a portfolio tracker for retail investors. One repository holds five
runnable systems: a Python 3.14 / FastAPI backend (`src/`) with SQLAlchemy 2 async models over
PostgreSQL and Alembic migrations, a Huey worker on Redis (`src/worker.py`), a SvelteKit 2 /
Svelte 5 SSR frontend (`frontend/`), a stateless Go indicator sidecar
(`services/indicator-service/`), and a Go MCP gateway (`services/mcp-gateway/`) that reads the
backend's provider-agnostic market data plane. Local development is Docker Compose only, and
the backend, worker, Compose interpolation and the frontend dev server all read one root
`.env` copied from the tracked `.env.example`.

`AGENTS.md` is the root guide: it delegates backend work (`src/`, `tests/`, `migrations/`) to
`src/AGENTS.md`, frontend work (`frontend/`) to `frontend/AGENTS.md`, and Go microservices work
(`services/`) to `services/README.md` plus each service's own `README.md`. Those guides, the
agent skills under `.ai/skills/` (symlinked into `.agent/`, `.claude/` and `.opencode/`), and
the OpenWiki block at the end of `AGENTS.md` are the authoritative statement of how work is
done here — this wiki is only context.

## Run it

```bash
cp .env.example .env
just up        # or: docker compose up -d
```

`just up` starts the stack with the host Docker socket's real group id (discovered by
`scripts/docker-gid.sh`, overridable with `DOCKER_GID`), which is what lets
testcontainers-backed tests inside the containers reach the daemon.

```mermaid
flowchart LR
    Browser["Browser"] -->|"localhost:8002"| Frontend["frontend :8100"]
    Frontend -->|"SSR over the Compose network"| Backend["backend :8000"]
    McpGateway["mcp-gateway :8080"] -->|"X-Service-Token"| Backend
    Backend -->|"INDICATOR_SERVICE_URL"| Indicator["indicator-service :8080"]
    Backend --> Postgres["PostgreSQL :5432"]
    Backend --> Redis["Redis :6379"]
    Backend --> Mailcrab["mailcrab SMTP :1025"]
    Worker["worker under watchfiles"] --> Postgres
    Worker --> Redis
```

Container and request topology of the dev stack: host-published entry points on the left, each
call labelled with the mechanism that carries it.

| Service | URL / purpose | Host port (root `.env` override) | Container port |
|---|---|---|---|
| backend | `http://localhost:8001` — `/redoc`, `/api/ping`, `/health/live`, `/health/ready`, the versioned API under `/api/v1`, Huey dashboard at `/worker/api` | `BACKEND_PORT` | `8000` |
| worker | no port of its own: it consumes the Huey queue and exposes nothing | — | — |
| frontend | `http://localhost:8002/` | `FRONTEND_PORT` | `8100` |
| mailcrab (dev SMTP inbox) | `http://localhost:8003` | `MAILCRAB_PORT` | `1080` |
| indicator service | `http://127.0.0.1:8004` — stateless Go indicator calculator | `INDICATOR_SERVICE_PORT` | `8080` |
| mcp-gateway | `http://127.0.0.1:8005` — Go MCP server (`/mcp`, `/health`) over the backend data plane | `MCP_GATEWAY_PORT` | `8080` |
| PostgreSQL | `localhost:5432` | `POSTGRES_PORT` | `5432` |
| debugpy | `localhost:8090` (backend) / `localhost:8091` (worker) | `BACKEND_DEBUG_PORT`, `WORKER_DEBUG_PORT` | `5678` |
| Redis | not published — reachable only on the Compose network as `redis:6379` | — | — |

Every one of those ports is Compose-interpolated from the root `.env`, so change ports there
rather than in `docker-compose.yml`. `src/.env` and `frontend/.env` are obsolete — move any
custom values into the root `.env` and delete them. Neither Go service is meant to be public:
dev Compose publishes each one on loopback only (`127.0.0.1:<port>:8080`) and
`docker-compose.prod.yml` publishes no host port for either, because the indicator sidecar has
no authentication and the gateway's `/mcp` listener is deliberately unauthenticated (its trust
boundary is the backend data plane it calls with `X-Service-Token`).

`worker` is a separate container from `backend`: it runs
`huey_consumer src.worker.huey -w 2 --worker-type thread --periodic` under `watchfiles`
reload, so task changes are picked up without restarting Compose. Nothing in a request path
runs those tasks, and the dashboard API is mounted on the backend app, not the worker — see
[Realtime, Background Jobs & the Worker](./workflows/realtime-and-background-jobs.md).

Three configuration details bite when ports or secrets change:

- The frontend service receives `JWT_SECRET` derived from the root `SECRET_KEY`, so the SSR
  route guard in `frontend/src/hooks.server.ts` verifies tokens with exactly the backend HS256
  signing key; Compose fails fast when `SECRET_KEY` is unset.
- An existing checkout must add `MARKET_DATA_SERVICE_TOKEN` to the root `.env` (the dev default
  is `dev-market-data-token`). Without it the shared secret the MCP gateway sends no longer
  matches settings and the backend data plane answers `401`.
- `CORS_ALLOW_ORIGINS` in `.env.example` names `http://localhost:8101` while the dev frontend is
  published on `8002`. Dev still works because the backend sets
  `allow_origin_regex=r"https?://.*"` for any non-prod environment, but in prod that regex is
  `None` and the origin list must be correct.

CI (`.github/workflows/ci.yml`) runs the same verification in four jobs: backend
(`uv run ty check`, `ruff check` + `ruff format --check`, `pytest`), frontend (`npm run check`,
`npm run lint`, `npm run test:run`, plus `node --test` on the OpenWiki session shim), and one
job per Go module (`go vet`, `gofmt -l`, `staticcheck`, `govulncheck`, `go build`, `go test`).

## Where things live

| Path | What it owns |
|------|--------------|
| `src/` | FastAPI backend, split into domains (`account`, `auth`, `market`, `integration`, `ws`) plus cross-cutting `core`, `config` and `worker_dashboard` |
| `frontend/` | SvelteKit SSR app: routes, services, API clients, components |
| `services/indicator-service/` | Go indicator sidecar (stateless calculator; backend-only client) |
| `services/mcp-gateway/` | Go MCP gateway: MCP transport plus a data-plane client for `/api/v1/market/data` |
| `migrations/` | Alembic revisions (the Alembic `script_location`, set in `alembic.ini` and `pyproject.toml`) |
| `tests/` | Backend pytest suites, organized by domain and layer |
| `src/stubs/` | Stub external gateways used by tests and `STUB_EXTERNAL_API` mode |
| `src/commands/` | Seeding (`seed.py`) and market-data flush (`flush_market_data.py`) CLI entrypoints |
| `openspec/` | Canonical capability specs and active/archived change artifacts |
| `scripts/` | `agent-test` harness, `setup-agent-worktree.sh`, `docker-gid.sh`, the OpenWiki preload shim (`opencode-go-session-fetch.mjs`) and its Node test |
| `.ai/` | Agent skills (`skills/`), feature specs (`features/`), architecture reviews (`reviews/`) and per-ticket working notes (`notes/`) |
| `.agent/`, `.claude/`, `.opencode/` | Mirrored agent definitions: subagents, workflows/slash commands, per-tool skills and the OpenCode model map |
| `.github/workflows/` | CI (`ci.yml`) and the scheduled OpenWiki refresh (`openwiki-update.yml`) |

## If you are changing X, read Y

Each row names the single owning page; go there instead of duplicating detail here.

| You are changing… | Read |
|---|---|
| Anything at the system level: processes, startup, request flow, layer rules | [Architecture Overview](./architecture/overview.md) |
| A backend domain: add a route/service/repository, or touch `account`, `auth`, `market`, `integration`, `ws`, `core` | [Backend Domains](./architecture/domains.md) |
| `Settings`, the root `.env` contract, the `svcs` registry, DB/Redis managers, middleware | [Configuration, Dependency Injection & Cross-Cutting Runtime](./architecture/configuration.md) |
| SvelteKit routes, `load`/form actions, API clients, runes-based services, SSR pitfalls | [Frontend Architecture](./architecture/frontend.md) |
| The market data layer: the `MarketGateway` contract, the provider bindings (FMP, Polygon, legacy EODHD), per-data-class caching, currency/FX resolution, and the `/api/v1/market/data` routes | [Market Data Providers & the Service-to-Service Data Plane](./architecture/market-data-providers.md) |
| The MCP gateway: `/mcp` transport and tool registry, the `X-Service-Token` data-plane client, error taxonomy, redaction rules, compose/CI wiring | [MCP Gateway: Go Sidecar, Tools and the Data-Plane Client](./integrations/mcp-gateway.md) |
| Either Go service's shared conventions: module layout, `Load(getenv)` configuration, slog, `X-Request-ID`, graceful shutdown, Docker build target, and the commands that verify them | [Go Microservices: Conventions & Service Inventory](./architecture/go-services.md) |
| The chart surface: chart mount/series lifecycle, panes and pane heights, timeframe/chart style, indicator overlays, chart settings, price alerts | [Charting: Chart Surface, Panes & Indicators](./architecture/charting.md) |
| Drawing tools: series-primitive plugins and helpers, finance math, drawing persistence/undo-redo, chart snapshots and the rewind timeline | [Chart Drawings, Plugins & Rewind](./architecture/chart-drawings-and-rewind.md) |
| Anything persisted per user: the `/accounts/me/preferences` contract, key ownership, merge/`exclude_none` semantics | [User Preferences](./concepts/user-preferences.md) |
| Signup/login, the `auth_token` JWT, 2FA/TOTP, passkeys, ownership authorization, the WS ticket, `X-Service-Token` | [Authentication & Authorization](./architecture/authentication.md) |
| The holdings read path: the accounts dashboard, `/accounts/[id]`, cross-account `/holdings`, holdings table columns/grouping/preferences | [Accounts & Holdings Views](./workflows/accounts-and-holdings-views.md) |
| Portfolios: the `portfolios`/`portfolio_accounts` models, `PortfolioService`, the `/portfolios` CRUD routes, the list page, the `?portfolio_id=` holdings filter | [Portfolios & Holdings Filters](./workflows/portfolios.md) |
| Watchlists, the sidebar watchlist groups and ticker shortcuts, the `/watchlists` page, or the global-search dialog | [Watchlists, Sidebar & Global Search](./workflows/watchlists-and-search.md) |
| A fair-value range on a security: the valuations table, the four market routes, `valuationClient`, the fundamentals sidebar group | [Security Valuations (Fair-Value Ranges)](./concepts/security-valuation.md) |
| The `/security/[security_id]` route itself: the shell-first load, the page data wave, the instant titlebar, and the actions-sidebar groups (notes, documents, alerts, indicators, holdings, AI) | [Security Detail Page & Actions Sidebar](./workflows/security-detail-page.md) |
| Broker connect, Wealthsimple login/OTP, position import and the Huey sync task | [Broker Connect, Import & Position Sync](./workflows/broker-sync.md) |
| CSV templates, account discovery, the inspect → import → sync lifecycle | [CSV Account Import & Sync](./workflows/csv-import.md) |
| Price fetches/backfill, daily & intraday tasks, the downstream recalc/alert cascade, indicator computation into the Go sidecar | [Market Data, Indicators & the Price Update Cascade](./workflows/market-data-and-indicators.md) |
| AI context assembly, fundamentals/notes/debate endpoints, the async title task | [AI Analysis Flows](./workflows/ai-analysis.md) |
| The worker: task registries, periodic/on-demand jobs, retries, the Redis WebSocket fan-out, sync-status keys, the frontend consumer | [Realtime, Background Jobs & the Worker](./workflows/realtime-and-background-jobs.md) |
| An outbound dependency: FMP/Polygon/EODHD, Wealthsimple, the AI endpoint, SMTP/mailcrab, Redis, the indicator sidecar | [External Services & Adapters](./integrations/external-services.md) |
| Money, currency conversion, totals, holdings/P&L math, rounding | [Money & Currency Handling](./concepts/money-and-currency.md) |
| How to run, ship and change: Compose dev/prod topologies, in-container commands, the agent-test harness, worktrees, migrations, CI, OpenSpec, the OpenWiki refresh | [Development, CI & Change Workflows](./operations/workflows.md) |
| The pytest/Vitest layout, fixtures, mandatory mocking, harness gates, the Go test commands, the CI matrix | [Testing & Verification](./operations/testing.md) |
| Agent guidance and this wiki: `AGENTS.md`, `src/AGENTS.md`, `frontend/AGENTS.md`, `services/README.md`, the agent-tooling trees, the OpenWiki block and its retrieval policy | [Development, CI & Change Workflows](./operations/workflows.md) |

Every link above resolves to a page in this wiki; `AGENTS.md` names this page as the
fallback route when the OpenWiki retrieval tools are unavailable.

## Non-negotiables

These rules come from `AGENTS.md`, its per-area guides (`src/AGENTS.md`,
`frontend/AGENTS.md`, `services/README.md`) and the OpenWiki block at the end of `AGENTS.md`,
and hold for every task:

- **Backend and frontend commands run inside Docker only:**
  `docker compose exec <backend|frontend> <command>`. The host is never the reference
  environment for those two ecosystems. Go checks are the exception: they run with the host Go
  toolchain (`gofmt`, `staticcheck`, `go vet ./...`, `go test ./...`) or through `just`
  (`just lint-go`, `just test-indicator-service`, `just test-mcp-gateway`, `just test-all`).
  CI runs the same checks.
- **Use the agent harness.** `./scripts/agent-test` (shorthand `just test …`) is the primary
  test entrypoint for the backend and frontend. It shells through `docker compose exec -T` for
  you, sanitizes output and caps it at `--max-chars` (default 3000), and offers **Gate 0**
  (lint + type checker; halts before tests on failure), **Gate 1** (a path argument — targeted,
  fail-fast) and **Gate 2** (no path — full suite with a two-tier Index/Traces summary). Flags:
  `--backend` / `--frontend`, `--all`, `--no-gate0`, `--gate0-only`, `--local`, `--json`,
  `--max-chars N`. Raw `docker compose exec … pytest`/`vitest` is the fallback if the harness
  itself breaks.
- **Model edits require a migration.** Editing a backend model means generating the Alembic
  revision in the same change; migration files follow `<hash>_<description>.py` naming, and
  manual SQL goes through `op.execute()` inside a standard revision.
- **Tests never touch external services.** Mock all outbound I/O — Redis, HTTP APIs (market
  data providers, broker APIs), and SMTP in the backend; all API calls in the frontend. The
  ephemeral testcontainers PostgreSQL is the only allowed infrastructure dependency. A test
  that makes a real network/Redis/SMTP call is broken by definition; mock it, don't expect the
  service to be up.
- **Parallel agents isolate with git worktrees.** Use
  `scripts/setup-agent-worktree.sh <worktree-path> <branch-name> [base-ref]` (`base-ref`
  defaults to `origin/main`), which discovers free ports and generates a worktree `.env` before
  starting that worktree's Compose stack — otherwise files and Docker resources collide.
- **Agents never merge into `main`.** Ticket PRs merge into their `feat/<slug>` integration
  branch; only the user merges that branch.
- **Spec-driven changes.** Non-trivial work goes through OpenSpec in `openspec/`
  (propose → apply → archive); canonical specs live in `openspec/specs/<capability>/spec.md`.
- **Source code and tests are authoritative; the generated wiki is optional context.**
  `openwiki/` is just-in-time context, not required startup reading, and its pages must not be
  hand-edited — see [Consuming the generated wiki](#consuming-the-generated-wiki).

## Consuming the generated wiki

The `openwiki/` tree is generated documentation, refreshed by the scheduled
`.github/workflows/openwiki-update.yml` workflow (daily at 08:00 UTC, plus
`workflow_dispatch`), which installs OpenWiki globally, runs `openwiki code --update --print`
with the OpenCode session preload shim, and opens a pull request on the `openwiki/update`
branch limited to `add-paths: openwiki`. Documentation therefore lands through review, never as
a direct commit. Do not hand-edit these pages unless explicitly asked: update source code and
docs and let the workflow regenerate them.

The OpenWiki block at the end of `AGENTS.md` (delimited by `<!-- OPENWIKI:START -->` /
`<!-- OPENWIKI:END -->`) defines how agents are meant to use it. It is the authoritative
statement of consumption policy: if it and this page disagree, the block wins.

- **The wiki is optional just-in-time context, not required startup reading.** Do not
  enumerate, preload, or search wikis at task start. Retrieval applies when the user asks
  for it, when unfamiliar architecture or dependency behavior materially affects the task,
  or when source inspection leaves an important uncertainty — and it stops once the
  question is grounded.
- **Use the retrieval tools when those conditions apply.** `openwiki_search` supplies
  just-in-time context; `openwiki_read` returns the relevant complete sections. If search
  returns `workspace_required`, ask which listed workspace to use and retry with its ID.
- **`openwiki_list_workspaces` / `openwiki_list_wikis`** are for when workspace membership
  itself needs to be discovered.
- **If the retrieval tools are unavailable**, read `openwiki/quickstart.md` and follow its
  links — this page and the table above are the entry point.
- **Source code and tests stay authoritative.** A brief's unknowns and review items are
  verification gaps, not automatic requirements.
- **Validate narrowly and quietly.** Prefer the narrowest validation that proves the changed
  behavior, and preserve complete failure output.

```mermaid
flowchart TD
    Q["Need context for this task?"] --> A{"Did the user ask, or does unfamiliar architecture or dependency behavior materially matter, or did source reading leave an uncertainty?"}
    A -- no --> S["Stay in the source - do not preload or search the wiki"]
    A -- yes --> T{"OpenWiki retrieval tools available?"}
    T -- no --> F["Read openwiki/quickstart.md and follow its links"]
    T -- yes --> R["openwiki_search for just-in-time context, then openwiki_read for the relevant complete sections"]
    R --> W{"Search returned workspace_required?"}
    W -- yes --> K["Ask which listed workspace to use, then retry with its ID"]
    K --> R
    W -- no --> G["Stop once the question is grounded - source code and tests remain authoritative"]
```

How an agent decides whether to consult the generated wiki, and what to do when retrieval needs a workspace.
