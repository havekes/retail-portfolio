## Communication Style

- Be sparse with words — straight to the point, no filler.
- Ask when unsure instead of inferring.

## Project Guides

- **Backend work** (Python/FastAPI: `src/`, `tests/`, `migrations/`): follow `src/AGENTS.md`.
- **Frontend work** (SvelteKit: `frontend/`): follow `frontend/AGENTS.md`.

Each guide holds the full command list (tests, migrations, linting, type checks) and architecture rules for its area.

## Development Commands

All development commands **must** be executed inside Docker: `docker compose exec <backend|frontend> <command>` — see the area guide above for the exact commands. CI runs the same checks.

## Parallel Agent Development

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
