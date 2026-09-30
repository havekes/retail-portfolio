---
name: quality-check
description: Run backend, frontend, or all lint, type-check, and test suites via ./scripts/agent-test and fix every reported issue.
---

# Quality Check & Fix

Argument `target`: `backend` | `frontend` | `all` (default: auto-detect from the git diff).

## Run

- Auto-detect: `./scripts/agent-test`
- Specific: `./scripts/agent-test --backend` | `--frontend` | `--all`
- Lint/types only: `./scripts/agent-test --gate0-only`

The harness runs inside Docker, sanitizes and caps output. Gate 0 (lint + types) halts before tests when it fails — fix those first.

## Fix loop

1. **Lint/format**: `docker compose exec backend uv run ruff check --fix` and `... uv run ruff format`; `docker compose exec frontend npm run format`, then fix remaining eslint errors by hand.
2. **Types**: fix signatures/annotations from the reported diagnostics.
3. **Tests**: iterate on one failure with `./scripts/agent-test <test file>`; fix root causes, not assertions.
4. Re-run the full command from **Run** until clean.

Tests never call external services — mock Redis/HTTP/SMTP (backend) and API calls (frontend). Captured logs → `.ai/scratch/`.
