---
type: "Reference"
title: "Development, CI & Change Workflows"
openwiki_generated: true
verified:
  - by: openwiki/0.5.2
    at: 2026-09-18T20:16:58.058Z
sources:
  - id: openwiki-source-b6d79691ae8158aab326e9d3
    resource: repo://.agent/workflows/opsx-apply.md
  - id: openwiki-source-55872b73dfc0e1388d16ab8f
    resource: repo://.agent/workflows/opsx-archive.md
  - id: openwiki-source-89276d07b76832f343492796
    resource: repo://.agent/workflows/opsx-explore.md
  - id: openwiki-source-cd6a33fc3b74a9a16cc85155
    resource: repo://.agent/workflows/opsx-propose.md
  - id: openwiki-source-715dace563ef484b6e8bd1e2
    resource: repo://.dockerignore
  - id: openwiki-source-5f5b95b3d6a215fa02ceb945
    resource: repo://.env.example
  - id: openwiki-source-5bd6c48f5ba68cedf3d758ba
    resource: repo://.github/prompts/opsx-archive.prompt.md
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-6d4b4e707b8d60b6ccfa3425
    resource: repo://.github/workflows/openwiki-update.yml
  - id: openwiki-source-9a893e0578e12c52c0533ec0
    resource: repo://.opencode/command/opsx-propose.md
  - id: openwiki-source-8037e2358a2c4f9b2c722a11
    resource: repo://AGENTS.md
  - id: openwiki-source-a2371d6362e5db4bc834ad03
    resource: repo://CLAUDE.md
  - id: openwiki-source-11ef2d56dffda152beeb9f84
    resource: repo://docker-compose.prod.yml
  - id: openwiki-source-b79fbbd921df689b4bbdc82f
    resource: repo://docker-compose.yml
  - id: openwiki-source-bb1ebe868e35e9e500714501
    resource: repo://Dockerfile
  - id: openwiki-source-cc3f1d0259a2efebbe62cecf
    resource: repo://frontend/Dockerfile
  - id: openwiki-source-c59fe4336a371ea1052a01dd
    resource: repo://justfile
  - id: openwiki-source-a41ded727f97fd17b9db4917
    resource: repo://migrations/env.py
  - id: openwiki-source-38af7bdd34d817fbd3c29077
    resource: repo://openspec/config.yaml
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
  - id: openwiki-source-b1543404abfc927178353273
    resource: repo://scripts/agent-test
  - id: openwiki-source-c347ef400d4d12fd07984865
    resource: repo://scripts/setup-agent-worktree.sh
  - id: openwiki-source-634b7bac22fbe90060118ce8
    resource: repo://services/indicator-service/calculator_test.go
  - id: openwiki-source-a53f7eb5e75addb6919a0071
    resource: repo://services/indicator-service/Dockerfile
  - id: openwiki-source-34cb4ee7457dd79b53e785af
    resource: repo://services/indicator-service/main.go
  - id: openwiki-source-b911aefb4dbb6f043ed2380e
    resource: repo://src/account/task.py
  - id: openwiki-source-230f617cb6d47154ef463034
    resource: repo://src/AGENTS.md
  - id: openwiki-source-b251d0144a6ce3e32623e4c2
    resource: repo://src/commands/flush_market_data.py
  - id: openwiki-source-dfd9a181d2f58b1a466b8c27
    resource: repo://src/commands/seed.py
  - id: openwiki-source-1bc1a904875e872775adbd74
    resource: repo://src/integration/task.py
  - id: openwiki-source-11b9d806fcc6dd6e7747ed87
    resource: repo://src/main.py
  - id: openwiki-source-689c3cecf701f8b197038e75
    resource: repo://src/market/task.py
  - id: openwiki-source-c8a9ed75dfc5d7332062ae40
    resource: repo://src/worker_dashboard/router.py
  - id: openwiki-source-7ffbd3b42b6e6df4d4db1a43
    resource: repo://src/worker_dashboard/setup.py
  - id: openwiki-source-7a8d629077019775a9fec3d3
    resource: repo://src/worker.py
generated: { by: "openwiki/0.5.2", at: "2026-09-18T20:16:58.058Z" }
---


# Development, CI & Change Workflows

This page is the operational map: how the stack is run locally, which commands are
allowed to touch code, how work reaches `main` (CI, worktrees, OpenSpec changes), how it
is deployed, and which background work the worker owns. Runtime topology and per-request
flow belong to [Architecture Overview](../architecture/overview.md); the harness internals
are covered by [Testing & Verification](./testing.md).

## Local development: Docker Compose only

Docker Compose is the only supported way to run the application (`AGENTS.md`,
`README.md`):

```bash
cp .env.example .env
docker compose up -d
```

After startup:

- App / backend API: `http://localhost:8001`
- Ping: `http://localhost:8001/api/ping`; ReDoc: `http://localhost:8001/redoc`
- Frontend dev server: `http://localhost:8002` (override with `FRONTEND_PORT`)
- Mailcrab (dev email sink): `http://localhost:8003`
- Indicator service: `http://localhost:8085`

**All development commands must run inside Docker**: `docker compose exec <backend|frontend> <command>`.
CI runs the same checks, so the host environment is never the reference.

### Dev stack services and ports

`docker-compose.yml` defines seven services. Published ports are Compose-interpolated
from the root `.env`, so every port below is overridable:

| Service | Image / build | Published ports | Role |
|---------|---------------|-----------------|------|
| `backend` | `ghcr.io/astral-sh/uv:python3.14-bookworm` | `${BACKEND_PORT:-8001}:8000`, `${BACKEND_DEBUG_PORT:-8090}:5678` | `uv sync && uv run uvicorn src.main:app --reload` with debugpy on 5678 |
| `worker` | same | `${WORKER_DEBUG_PORT:-8091}:5678` | `uv run -m watchfiles "huey_consumer src.worker.huey -w 2 --worker-type thread --periodic" src/` |
| `frontend` | `node:latest` | `${FRONTEND_PORT:-8002}:8100` | `npm install && npm run dev` (SvelteKit dev server) |
| `postgres` | `postgres:18` | `${POSTGRES_PORT:-5432}:5432` | Primary datastore, named volume `postgres_data` |
| `redis` | `redis:7-alpine` | — (internal) | Cache, WebSocket fan-out, Huey broker |
| `mailcrab` | `marlonb/mailcrab:latest` | `${MAILCRAB_PORT:-8003}:1080` | SMTP sink + web UI |
| `indicator-service` | `build: ./services/indicator-service` | `${INDICATOR_SERVICE_PORT:-8085}:8080` | Go indicator sidecar; healthcheck hits `http://localhost:8080/health` |

Two details matter when changing the dev stack:

- **The backend mounts the host Docker socket** (`/var/run/docker.sock`) and adds the
  host Docker group via `group_add: ["${DOCKER_GID:-959}"]`, because testcontainers-backed
  tests (those without `TEST_DATABASE_URL`) start a throwaway Postgres container. `just up`
  resolves the group id first with `scripts/docker-gid.sh`; on Docker Desktop/OrbStack that
  script asks the daemon instead of `stat`ing the host file, because the socket is remounted
  with different ownership.
- **Both `backend` and `worker` run as uid/gid `1000:1000`** with `UV_CACHE_DIR` and
  `UV_PROJECT_ENVIRONMENT` pointed into `/app/.cache`, so the bind-mounted repo stays
  writable and the venv survives container recreation.

### Root `.env` contract

The tracked `.env.example` at the repository root is the single configuration source;
`.env` is gitignored and must never be committed. The one file feeds three dev-stack
consumers:

- `backend` and `worker` load it via `env_file: [./.env]` and re-assert `ENVIRONMENT`.
- Compose interpolates ports/URLs (`${BACKEND_PORT}`, `${FRONTEND_PORT}`, `${DOCKER_GID}`,
  `VITE_*`, …) at `docker compose up` time, so port changes need a recreate, not a restart.
- `frontend` receives `VITE_API_BASE_URL`, `VITE_INTERNAL_API_URL`, `VITE_ALLOWED_HOSTS`,
  and `JWT_SECRET: "${SECRET_KEY:?SECRET_KEY must be set in the root .env}"` — the SSR route
  guard verifies tokens with exactly the backend signing key, and Compose fails fast if
  `SECRET_KEY` is absent.

`src/.env` and `frontend/.env` are obsolete; values must live in the root `.env`.
Variable-by-variable consumption is documented in
[Configuration, DI & Cross-Cutting Runtime](../architecture/configuration.md).

### Parallel agents: git worktree isolation

Agents working on several tasks at once **must** isolate with git worktrees, otherwise
files and Docker resources collide:

```bash
scripts/setup-agent-worktree.sh <worktree-path> <branch-name>
cd <worktree-path> && docker compose up -d
```

The script creates the worktree (branching from `origin/main` when the branch does not
exist), discovers free ports with `socket.bind(("", 0))`, seeds the worktree `.env` from
the main checkout's `.env` (falling back to `.env.example`), and then deterministically
rewrites `COMPOSE_PROJECT_NAME`, `DOCKER_GID` and all seven published ports
(`BACKEND_PORT`, `FRONTEND_PORT`, `BACKEND_DEBUG_PORT`, `WORKER_DEBUG_PORT`,
`POSTGRES_PORT`, `MAILCRAB_PORT`, `INDICATOR_SERVICE_PORT`) so re-runs leave no stale
entries. Every worktree therefore gets its own Compose project, volumes and port set.

## Testing: the agent harness first

`./scripts/agent-test` is the primary test entrypoint for agents (root `AGENTS.md`); the
`just` recipes are thin wrappers. It runs on the host and shells through
`docker compose exec -T <service>` unless it is already inside a container or `--local` is
passed, sanitizes output (ANSI stripping, vendor-frame removal, blank-line collapsing) and
hard-caps it at `--max-chars` (default 3000).

```bash
just test                       # auto-detect ecosystems from the git diff
just test tests/routers/test_auth.py
just test frontend/src/lib/api/apiClient.test.ts
just test-backend               # ./scripts/agent-test backend
just test-frontend              # ./scripts/agent-test frontend
just test-all                   # ./scripts/agent-test --all
just check                      # ./scripts/agent-test --gate0-only
just up                         # DOCKER_GID=$(./scripts/docker-gid.sh) docker compose up -d
```

Three gates with different intents:

- **Gate 0 — pre-flight lint/type.** Backend: `uv run ruff check`, `uv run ruff format --check`,
  `uv run ty check`. Frontend: `svelte-kit sync`, `svelte-check`, `eslint -f json`
  (reformatted to `path:line:col: message (rule)`), `prettier --check .`. If Gate 0 fails the
  harness halts and prints only diagnostics — **no tests run**, so fix lint/type errors first.
- **Gate 1 — targeted iteration.** A path argument (`./scripts/agent-test tests/routers/test_auth.py`)
  runs only that target with fail-fast (`pytest -x` / `vitest --bail=1`) and `--no-cov` on the
  backend. Paths typed as `backend` / `frontend` select a whole ecosystem instead.
- **Gate 2 — full regression.** With no targets, ecosystems are auto-detected from the git
  diff (`origin/main...HEAD`, working tree, staged, untracked). `src/`, `tests/`, `migrations/`,
  `pyproject.toml`, `uv.lock` and `alembic.ini` imply backend; `frontend/` implies frontend;
  `openspec/`, `openwiki/`, `.github/`, `.opencode/`, `.agent/`, `scripts/` and
  `frontend/node_modules/` are deliberately ignored; an empty diff means both ecosystems.
  Output is an **Index** (per-ecosystem counts plus failed identifiers, capped at 30) followed
  by **Traces** for only the first 1–2 failures; the rest appear as one-line summaries.

Flags: `--backend` / `--frontend`, `--all`, `--gate0-only`, `--no-gate0`, `--local`,
`--json`, `--max-chars N`. Machine-readable reports land in `.cache/agent-test/`
(`backend.xml`, `frontend.json`) and the exit code is 1 if anything failed, errored, or the
runner itself failed.

**Scope:** the harness covers backend and frontend only. The Go service under
`services/indicator-service` is exercised by its own CI job.

### Raw per-ecosystem commands (fallback)

When the harness itself is broken, run the underlying commands inside the containers —
these are the same checks the harness and CI perform.

Backend (`docker compose exec backend …`):

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run ty check
uv run ruff format
uv run alembic revision --autogenerate -m "message"
```

Frontend (`docker compose exec frontend …`):

```bash
npm run dev
npm run build
npm run check
npm run lint
npm run test:run
```

### Migration rules

`src/AGENTS.md` makes migrations mandatory: **editing a backend model requires generating
and committing an Alembic migration**. All migration files must follow the standard
`<hash>_<description>.py` naming. For hand-written SQL, create a normal revision with the
autogenerate command and use `op.execute()` inside it rather than hand-authoring the file.

`migrations/env.py` imports every domain `model` module so all tables register on
`BaseModel.metadata`, and overrides `sqlalchemy.url` from `DATABASE_URL`, rewriting
`postgresql+asyncpg://` to synchronous `postgresql://` for Alembic's sync engine. Adding a
model class to an already-imported module needs no change here; adding a whole new domain
model module does. `tests/test_migrations_autogenerate.py` fails the suite when models and
migrations drift.

## CLI commands: seeding and market-data flush

Both admin commands are run inside the backend container and are idempotent-by-lookup
(they select before inserting rather than relying on constraint violations):

- **`python -m src.commands.seed` (`src/commands/seed.py`)** — always seeds reference data
  (`AccountTypeModel` and `InstitutionModel`). Only when `settings.environment == "dev"` does
  it additionally seed the test user (`test@example.com` / `test`), sample securities,
  accounts, positions, portfolios and integration users; in other environments it prints
  `Skipping dev-only seeding` and commits only the reference rows.
- **`python -m src.commands.flush_market_data`** — mutually exclusive `--security-id <uuid>`
  or `--all`. It counts rows in `PriceModel` and `IntradayPriceModel`, requires an
  interactive `[y/N]` confirmation, deletes the rows, and then invalidates the matching
  indicator cache (per-security `invalidate_security` or `flush_all`). This is the reset path
  when cached indicator/price history must be rebuilt from EODHD.

## Background jobs and the Huey dashboard

The worker is `huey_consumer src.worker.huey -w 2 --worker-type thread --periodic`
(dev wraps it in `watchfiles`). `src/worker.py` builds the Huey instance — `MemoryHuey` in
`test`, `RedisHuey` otherwise — and its `on_startup` handler registers the worker's own
`svcs` registry (with a `NullPool` session manager) and imports the task modules
`src.account.task`, `src.integration.task` and `src.market.task` so their tasks register.
Because the registry only exists inside a running worker, task bodies guard on
`huey.svcs_registry` and resolve services through `Container(huey.svcs_registry)`.

Scheduled work:

| Task | Trigger | Effect |
|------|---------|--------|
| `daily_price_update` | `crontab(hour="0", minute="0")` | Updates daily prices for all active securities |
| `hourly_intraday_price_update` | `crontab(minute="0")` | Updates intraday prices, then enqueues account-totals recalculation and price-alert evaluation (each enqueue isolated so one failure cannot abort the cascade) |
| `check_and_dispatch_price_alerts` | enqueued by the hourly task | Evaluates active alerts against the latest intraday close and enqueues one dispatch per triggered alert |
| `alert_email_dispatch_task` | enqueued per triggered alert | Sends the alert email then marks the alert triggered; declared `retries=3` for transient SMTP/DB failures |

On-demand tasks: `generate_note_title_task` (AI-generated note titles),
`sync_account_positions_task` (broker position sync on account import) and
`recalculate_all_account_totals_task` (totals recalculation + WebSocket broadcast).
The cascade detail lives in [Market Data & Indicators](../workflows/market-data-and-indicators.md)
and the sync flow in [Broker Connect & Sync](../workflows/broker-sync.md).

**Huey dashboard.** `src/main.py` mounts `worker_dashboard_router` at `/worker/api`, backed by
`huey-dashboard`'s task API (`/worker/api/tasks`, guarded by `current_user`) and a
WebSocket at `/worker/api/updates` that authenticates via a signed ticket or `auth_token`.
`init_worker_dashboard` creates the task table, binds signal handlers (`bind_signals=True`)
and starts a Redis pub/sub listener; the lifespan closes it on shutdown. In dev the
`worker` service sets `HUEY_DASHBOARD_WORKER: 1` so the consumer process emits the signal
events the dashboard subscribes to.

## CI: three independent jobs

`.github/workflows/ci.yml` runs on push to `main` and on pull request
opened/synchronize/reopened. The jobs are independent, so a Go failure does not mask a
backend one:

| Job | Toolchain | Steps |
|-----|-----------|-------|
| `backend` | Python 3.14 + `astral-sh/setup-uv` | `uv sync --dev` → `uv run ty check` → `uv run ruff check && uv run ruff format --check` → `uv run pytest` |
| `frontend` | Node 25 | `npm install` in `frontend/` → `npm run check` → `npm run lint` → `npm run test:run`, with job-level env `VITE_API_BASE_URL`, `VITE_INTERNAL_API_URL`, `VITE_ALLOWED_HOSTS`, `JWT_SECRET` |
| `indicator-service` | Go 1.27 (cache keyed on `services/indicator-service/go.sum`) | `go mod download` → `go vet ./...` → `go build ./...` → `go test ./...` |

No Redis or database service is declared for `backend`: Redis is replaced by the autouse
fake and PostgreSQL comes from the testcontainers fixture, which is why the suite must never
dial a real service. There is no CI job for OpenWiki — documentation is refreshed by its own
scheduled workflow.

## Deployment surface

`docker-compose.prod.yml` keeps the same service topology but swaps dev commands for built
images, fixed ports, `restart: always` and explicit `container_name`s:

| Service | Build / image | Published ports |
|---------|---------------|-----------------|
| `backend` | `build: .` (root `Dockerfile`) | `8000:8000` |
| `worker` | `build: .` | — ; runs `huey_consumer src.worker.huey -w 2 --worker-type thread` (no `--periodic`/`watchfiles`; dev-only) |
| `frontend` | `build: ./frontend` | `80:3000` |
| `postgres` | `postgres:18` | — (volume `postgres_data`) |
| `redis` | `redis:7-alpine` | — |
| `indicator-service` | `build: ./services/indicator-service` | `8085:8080` |

There is no mailcrab service in prod, and the prod file declares no `env_file` — the
backend/worker read their configuration from the process environment.

### Images

- **Backend (`Dockerfile`)** — a two-stage build. The builder copies `pyproject.toml`/`uv.lock`
  first and runs `uv sync --frozen --no-install-project --no-dev` to leverage layer caching,
  then copies the source and runs `uv sync --frozen --no-dev` to install the project; the final
  stage copies `/app/.venv` and the source, puts the venv on `PATH`, creates a non-root
  `appuser`, and declares `EXPOSE 8000`. The `CMD` is
  `uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-graceful-shutdown 30`.
  `.dockerignore` excludes `.env`, `.venv`, `.cache`, `frontend/` and caches from the build
  context.
- **Frontend (`frontend/Dockerfile`)** — `node:20-alpine` build stage (`npm ci`, `npm run build`
  with `VITE_API_BASE_URL`/`VITE_INTERNAL_API_URL` build args) into a runtime stage that runs
  `node build` on port 3000.
- **Indicator service (`services/indicator-service/Dockerfile`)** — `golang:1.27-alpine` builds a
  static binary (`CGO_ENABLED=0`), copied into `alpine:3.21` alongside `wget` (needed by the
  healthcheck) and run as a non-root user with `EXPOSE 8080`.
- `src/Dockerfile` is a separate, simpler variant of the backend image (single `uv sync --frozen
  --no-cache`, `EXPOSE 8000`, plain `uvicorn` with no worker count). Root `Dockerfile` is what
  `docker-compose.prod.yml` builds.

### Startup migrations and health probes

Migrations are not a deployment step: `lifespan_context` in `src/main.py` calls
`run_migrations()` through `asyncio.to_thread` unless `settings.environment == "test"`, and
`run_migrations()` runs `alembic.command.upgrade(Config("alembic.ini"), "head")`. **The
backend container therefore migrates the database as it starts**, so a rolling deploy runs
the upgrade on each new instance and the `postgres` service must be reachable from the
`depends_on` chain before uvicorn begins serving.

Probes (used both by Compose healthchecks and by orchestrators):

- `GET /health/live` returns `{"status": "alive"}` and is the check wired into the compose
  healthchecks and the Dockerfile `HEALTHCHECK` — it deliberately touches no dependency.
- `GET /health/ready` executes `select(1)` through the container-resolved `AsyncSession` and
  pings Redis, returning `200 {"status": "ready", "database": "ok", "redis": "ok"}` or
  `503 {"status": "degraded", …}` with per-dependency `ok`/`error` values.
- `GET /api/ping` is the human/app-level check reported in the README and quickstart.

The Go sidecar exposes `GET /health` (used by its compose healthcheck) and `POST /compute`;
it is internal-network-only with no authentication.

## Spec-driven change workflow (OpenSpec)

This repository uses OpenSpec in `spec-driven` mode (`openspec/config.yaml` declares
`schema: spec-driven`). Canonical specs live in `openspec/specs/<capability>/spec.md`
(11 capabilities today, from `account-holdings-view` through `technical-indicators`);
active changes live in `openspec/changes/<name>/` and, once archived, move to
`openspec/changes/archive/YYYY-MM-DD-<name>/`.

<!-- openwiki: mermaid parse failed and this diagram was converted to a text fence so it does not break rendering. Fix the diagram source and restore the mermaid fence. Parser error: Heuristic: a semicolon inside a label breaks rendering; rephrase the label. -->
```text
flowchart TD
    P["/opsx:propose<br/>openspec new change &lt;name&gt;"] --> A1["proposal.md"]
    A1 --> A2["design.md / delta specs"]
    A2 --> A3["tasks.md"]
    A3 --> AP["/opsx:apply<br/>implement tasks, mark - [x]"]
    AP --> AR["/opsx:archive<br/>sync delta specs, mv to archive/YYYY-MM-DD-name"]
    E["/opsx:explore<br/>thinking only, no application code"] -.-> P
```

Caption: the four-stage lifecycle. Each stage is one slash command and one mirrored skill;
`explore` can feed `propose` but is not a required step.

### Mirrored definitions

The same four stages exist in three mirrors — there is **no `.claude/` directory**;
`CLAUDE.md` is a stub that imports `AGENTS.md`:

| Stage | Slash command | Skill |
|-------|---------------|-------|
| Propose | `.agent/workflows/opsx-propose.md`, `.opencode/command/opsx-propose.md`, `.github/prompts/opsx-propose.prompt.md` (`/opsx:propose`) | `.agent/skills/openspec-propose/`, `.opencode/skills/openspec-propose/`, `.github/skills/openspec-propose/` |
| Explore | `…/opsx-explore.md` / `.prompt.md` | `openspec-explore/` |
| Apply | `…/opsx-apply.md` / `.prompt.md` | `openspec-apply-change/` |
| Archive | `…/opsx-archive.md` / `.prompt.md` | `openspec-archive-change/` |

`.agent/skills/` and `.opencode/skills/` hold a wider catalogue beyond OpenSpec
(`architecture-review`, `commit-message`, `feature-definition`, `orchestration`, `pr-review`,
`quality-check`, `ticket-execution`, `ticket-planning`, `ticket-writing`). `.opencode/opencode.json`
names the default agent (`orchestrator`) and per-agent models. When adding an OpenSpec stage,
add all three mirrors — a change to only one silently diverges per tool.

### Rules the workflows enforce

- Create changes with `openspec new change "<name>"`, never by hand; the scaffold places
  `.openspec.yaml` in `openspec/changes/<name>/`.
- Build artifacts in dependency order, driven by `openspec status --change <name> --json`
  (`applyRequires` / `artifacts`) and `openspec instructions <artifact-id> --change <name> --json`.
  Read completed dependency artifacts before writing a new one.
- `context` and `rules` from `openspec instructions` are **agent-only constraints** and must
  never be copied into the artifact files.
- In `apply`: read `contextFiles` first, keep changes minimal, and flip `- [ ]` → `- [x]`
  immediately as each task completes; pause and ask when a task is unclear or reveals a design
  issue rather than guessing.
- In `archive`: never auto-select a change — list active changes with `openspec list --json`
  and prompt when ambiguous. Warn (and require confirmation) on incomplete artifacts or
  unchecked tasks, and compare delta specs against `openspec/specs/<capability>/spec.md`
  before offering to sync. The move is
  `mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>` and fails if the
  target already exists.
- `explore` is a stance, not a workflow: investigation and OpenSpec artifacts are allowed,
  application code is not.

## Scheduled OpenWiki update

`.github/workflows/openwiki-update.yml` runs daily at 08:00 UTC (`cron: "0 8 * * *"`) and on
`workflow_dispatch`, with `contents: write` and `pull-requests: write` permissions:

1. Check out the repository; set up Node 22.
2. `npm install --global openwiki`.
3. `openwiki code --update --print` with `OPENWIKI_PROVIDER=openai-compatible`,
   `OPENAI_COMPATIBLE_BASE_URL=https://opencode.ai/zen/go/v1`, `OPENWIKI_MODEL_ID=deepseek-v4.1-flash`
   and the API key from the `OPENCODE_API_KEY` secret. The step also sets
   `NODE_OPTIONS: --import ./scripts/opencode-go-session-fetch.mjs`, a preload shim that wraps
   global `fetch` to add the `x-opencode-session` header the provider cannot send itself.
4. `peter-evans/create-pull-request@v7` opens a PR on the `openwiki/update` branch limited to
   `add-paths: openwiki` (`docs: update OpenWiki`).

Documentation therefore lands through review, never as a direct commit to `main`. The
generated `openwiki/` tree is refreshed by this workflow — `AGENTS.md` instructs agents not to
hand-edit generated pages, but to change source and docs and let OpenWiki regenerate.
