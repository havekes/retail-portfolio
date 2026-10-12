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

# Indicator service regression (Go).
test-indicator-service:
    @cd services/indicator-service && go test ./...

# MCP gateway regression (Go).
test-mcp-gateway:
    @cd services/mcp-gateway && go test ./...

# Full regression across all ecosystems (parallel).
[parallel]
test-all: test-backend test-frontend test-indicator-service test-mcp-gateway

# Go format and static analysis gate for indicator-service and mcp-gateway.
lint-go:
    @test -z "$(gofmt -l services/indicator-service services/mcp-gateway)" || (echo "Unformatted Go files:" && gofmt -l services/indicator-service services/mcp-gateway && exit 1)
    @cd services/indicator-service && go run honnef.co/go/tools/cmd/staticcheck@v0.8.1 ./...
    @cd services/mcp-gateway && go run honnef.co/go/tools/cmd/staticcheck@v0.8.1 ./...
    @cd services/indicator-service && go run golang.org/x/vuln/cmd/govulncheck@v1.8.0 ./...
    @cd services/mcp-gateway && go run golang.org/x/vuln/cmd/govulncheck@v1.8.0 ./...

# Lint + type checks only (Gate 0) for auto-detected ecosystems.
check:
    @./scripts/agent-test --gate0-only
    @just lint-go

# Start services with the host's real docker socket gid so in-container tests
# can reach testcontainers (see docker-compose.yml group_add).
up:
    @DOCKER_GID=$(./scripts/docker-gid.sh) docker compose up -d
