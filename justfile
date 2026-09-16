# Agent-optimized test harness. See AGENTS.md → "Testing with the agent harness".
# `just` with no recipe runs `just test`. Extra args are passed through, e.g.
#   just test tests/routers/test_auth.py
#   just test frontend/src/lib/api/apiClient.test.ts

# Gate 0 + full regression for ecosystems auto-detected from the git diff.
test *ARGS:
    @./scripts/agent-test {{ARGS}}

# Full backend regression (Gate 0 + Gate 2).
test-backend:
    @./scripts/agent-test backend

# Full frontend regression (Gate 0 + Gate 2).
test-frontend:
    @./scripts/agent-test frontend

# Full regression for both ecosystems.
test-all:
    @./scripts/agent-test --all

# Lint + type checks only (Gate 0) for auto-detected ecosystems.
check:
    @./scripts/agent-test --gate0-only

# Start services with the host's real docker socket gid so in-container tests
# can reach testcontainers (see docker-compose.yml group_add).
up:
    @DOCKER_GID=$(./scripts/docker-gid.sh) docker compose up -d
