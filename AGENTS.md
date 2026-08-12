## Communication Style

- Be sparse with words — straight to the point, no filler.
- Ask when unsure instead of inferring.

## Development Commands

All development commands **must** be executed using Docker.

### Backend Commands

Execute backend commands inside the backend container using `docker compose exec backend`:

- **Run Tests (pytest)**: `docker compose exec backend uv run pytest`
- **Database Migrations (alembic)**:
  - Apply migrations: `docker compose exec backend uv run alembic upgrade head`
  - Generate migration: `docker compose exec backend uv run alembic revision --autogenerate -m "<message>"`
  - Roll back migration: `docker compose exec backend uv run alembic downgrade -1`
- **Linting & Formatting (ruff)**:
  - Run linter: `docker compose exec backend uv run ruff check`
  - Auto-fix lint errors: `docker compose exec backend uv run ruff check --fix`
  - Check formatting: `docker compose exec backend uv run ruff format --check`
  - Auto-format code: `docker compose exec backend uv run ruff format`
- **Type Check (ty)**:
  - Run type checker: `docker compose exec backend uv run ty check`

### Frontend Commands

Execute frontend commands inside the frontend container using `docker compose exec frontend`:

- **Type Check**: `docker compose exec frontend npm run check`
- **Lint & Format**:
  - Lint: `docker compose exec frontend npm run lint`
  - Format: `docker compose exec frontend npm run format`
- **Run Tests (vitest)**: `docker compose exec frontend npm run test:run`

### Parallel Agent Development

If working on multiple tasks simultaneously, agents **must** use the Git worktree isolation workflow to avoid file and Docker conflicts.

1. **Setup Worktree**: `scripts/setup-agent-worktree.sh <worktree-path> <branch-name>`
   This script creates the worktree and generates a `.env` file with unique ports.
2. **Start Services**: `cd <worktree-path> && docker compose up -d`
3. **Run Commands**: Execute tests and operations normally within the worktree directory.

<!-- OPENWIKI:START -->

## OpenWiki

This repository uses OpenWiki for recurring code documentation. Start with `openwiki/quickstart.md`, then follow its links to architecture, workflows, domain concepts, operations, integrations, testing guidance, and source maps.

The scheduled OpenWiki GitHub Actions workflow refreshes the repository wiki. Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting OpenWiki regenerate.

<!-- OPENWIKI:END -->
