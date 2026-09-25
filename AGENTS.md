## Communication Style

- Be sparse with words — straight to the point, no filler.
- Ask when unsure instead of inferring.

## Branch and Merge Protection

- **Agents NEVER merge into `main`.** Even if a prior user prompt says "merge when done" or all checks/reviews pass. Ticket PRs merge into their `feat/<slug>` integration branch; only the user merges that branch into `main`.
- Outside the ticket pipeline, stop, present the PR, and wait for explicit user confirmation before any merge into `main`.

## Agent workflow

Core skills live in `.ai/skills/`; `.claude/skills`, `.agent/skills` and `.opencode/skills` symlink each one (the `openspec-*` skills stay per-tool copies). Agents are in `.claude/agents/`, `.agent/agents/` and `.opencode/agents/`, kept thin and identical in intent. Start the pipeline with the `orchestration` skill (`[resume | <feature-slug> | arch [focus] | <idea>]`), or with the default `orchestrator` agent in opencode.

Branching: each feature, idea or arch batch gets a `feat/<slug>` integration branch cut from `main`. Ticket PRs target it and the orchestrator merges them once approved and green. At the end it opens one `feat/<slug>` → `main` PR for the user to review and merge.

| Artifact | Path | Status values | Template |
| --- | --- | --- | --- |
| Feature spec | `.ai/features/<slug>.md` | draft → ready → done | `feature-definition` skill |
| Arch review | `.ai/reviews/<YYYY-MM-DD>-architecture[-<focus>].md` | open → resolved | `architecture-review` skill |
| Ticket | GitHub issue, label `ticket` + `status:*` | label-driven | `spec-writing` skill |
| PR review | verdict appended to the ticket's `## Review feedback` | — | `pr-review` skill |
| Working notes | `.ai/notes/<id>-plan.md` (optional) | — | — |
| Scratch | `.ai/scratch/` (gitignored) | — | — |

## Project Guides

- **Backend work** (Python/FastAPI: `src/`, `tests/`, `migrations/`): follow `src/AGENTS.md`.
- **Frontend work** (SvelteKit: `frontend/`): follow `frontend/AGENTS.md`.
- **Go microservices work** (`services/indicator-service/`, `services/mcp-gateway/`): follow `services/<service>/README.md`.

Each guide holds the full command list (tests, migrations, linting, type checks) and architecture rules for its area.

**Testing rule (all areas)**: tests must never depend on external services. Mock all outbound I/O — Redis, HTTP APIs, and SMTP in the backend, and all API calls in the frontend. See the `## Testing` section in the relevant area guide.

## Development Commands

Backend and frontend development commands **must** be executed inside Docker: `docker compose exec <backend|frontend> <command>` — see the area guide above for the exact commands. Go microservice checks run via the Go toolchain (`go test ./...`, `go vet ./...`) or via `just`. CI runs the same checks.

## Testing with the agent harness

`./scripts/agent-test` is the primary test entrypoint for agents (shorthand: `just test …`). It runs inside Docker for you, sanitizes output (strips ANSI, timing/progress/vendor-frame noise), caps output at ~3000 chars, and only surfaces the failures that matter. Use it instead of raw `docker compose exec … pytest`/`vitest` when you want signal over volume.

- **While developing** — targeted, fail-fast, pre-flight included:
  - Backend: `./scripts/agent-test tests/routers/test_auth.py`
  - Frontend: `./scripts/agent-test frontend/src/lib/api/apiClient.test.ts`
  - Go services: `just test-indicator-service` / `just test-mcp-gateway` (or `cd services/<service> && go test ./...`)
- **Before finishing a task** — Gate 0 (lint/type) + full regression for the ecosystems auto-detected from the git diff:
  - `./scripts/agent-test` (add `--all` to force both backend and frontend)
  - Full parallel regression across all ecosystems (backend, frontend, Go microservices): `just test-all`
- **Pre-flight only** — `./scripts/agent-test --gate0-only` (or `just check`).
- **Flags** — `--backend` / `--frontend`, `--all`, `--no-gate0`, `--local`, `--json`, `--max-chars N`.

Gates: **Gate 0** runs linter + type checker; if it fails the harness halts and prints diagnostics only — no tests run, so fix the reported errors first. **Gate 1** (a path argument) runs only that target with fail-fast. **Gate 2** (no path argument) runs the full suite and prints a two-tier summary: an *Index* (counts + failed test IDs) and *Traces* for only the first 1–2 failures. The raw commands in the area guides remain the fallback if the harness itself is broken.

## Parallel Agent Development

If working on multiple tasks simultaneously, agents **must** use the Git worktree isolation workflow to avoid file and Docker conflicts.

1. **Setup Worktree**: `scripts/setup-agent-worktree.sh <worktree-path> <branch-name> [base-ref]` (`base-ref` defaults to `origin/main`)
   This script creates the worktree and generates a `.env` file with unique ports.
2. **Start Services**: `cd <worktree-path> && docker compose up -d`
3. **Run Commands**: Execute tests and operations normally within the worktree directory.

<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
