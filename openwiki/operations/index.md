# Files

- [Testing & Verification](testing.md) - How correctness is verified in retail-portfolio: the pytest domain/layer layout, PostgreSQL testcontainer and session-isolation fixtures, the global Redis/Huey/WebSocket mocks, the Vitest/jsdom setup with its shim set, the agent-test harness gates, and the three CI jobs.
- [Development, CI & Change Workflows](workflows.md) - How to run, ship and change retail-portfolio: the Docker Compose-only dev stack and root .env contract, the agent-test harness gates, git-worktree isolation for parallel agents, migration rules, CLI commands, background jobs and the Huey dashboard, the three CI jobs, the deployment surface, the OpenSpec spec-driven workflow, and the scheduled OpenWiki refresh.
