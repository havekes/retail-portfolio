---
name: quality-check
description: Run backend, frontend, or all linting, type checking, and test suites, and fix any detected issues.
---

# Quality Check & Fix

Run quality checks (linting, type checking, tests) for backend, frontend, or both, then fix any issues.

## Arguments
- `target` (optional): `backend` | `frontend` | `all` (default: `all` if unspecified)

## 1. Commands

### Backend (`target` = `backend` or `all`)
- **Lint**: `uv run ruff check`
- **Format**: `uv run ruff format --check`
- **Types**: `uv run ty check`
- **Tests**: `uv run pytest`

*(If using Docker Compose: `docker compose exec backend uv run <command>`)*

### Frontend (`target` = `frontend` or `all`, in `frontend/`)
- **Lint**: `npm run lint`
- **Types**: `npm run check`
- **Tests**: `npm run test:run`

## 2. Execution Workflow

1. **Parse Target**: Determine whether to run `backend`, `frontend`, or `all` based on input.
2. **Run Checks**: Execute specified target commands.
3. **Fix Issues**:
   - **Lint**: Run `uv run ruff check --fix` / `uv run ruff format` or fix code/Svelte lint errors.
   - **Types**: Inspect `ty check` / `npm run check` errors and fix type signatures or annotations.
   - **Tests**: Inspect failure tracebacks from `pytest` / `npm run test:run` and fix root causes.
4. **Re-verify**: Re-run targeted check commands until all pass with zero errors.
