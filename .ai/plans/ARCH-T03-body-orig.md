## Meta
- id: ARCH-T03
- depends_on: []
- branch: feat/arch-t03-mcp-gateway-validation-errors
- source: ".agent/reviews/2026-09-24-architecture.md"

## Objective

Distinguish HTTP 422 (Unprocessable Entity) from HTTP 404 (Not Found) in the Go MCP gateway client. This ensures that parameter validation failures return actionable tool errors to AI agents rather than falsely reporting that no market data exists.

## Scope

**In scope:**
- Introduce `ErrValidation` in `services/mcp-gateway/backendclient.go` to classify HTTP 422 separately from `ErrNoData` (HTTP 404).
- Update `classifyBackendError` in `backendclient.go` to map 422 to `ErrValidation` instead of `ErrNoData`.
- Update `mapBackendError` in `services/mcp-gateway/tools.go` to return an error result (`result.SetError`) for `ErrValidation`, retaining the descriptive validation message from the backend.
- Update tests in `backendclient_test.go` and `tools_test.go`.

**Out of scope:**
- Changing backend validation rules in FastAPI.
- Changing MCP tool parameter schemas.

## Acceptance criteria

- [ ] `classifyBackendError(422, body)` returns an error unwrapping to `ErrValidation`, not `ErrNoData`.
- [ ] An MCP tool call that triggers a backend 422 returns an MCP tool error result with error status, not a successful "No market data is available" message.
- [ ] An MCP tool call that triggers a backend 404 continues to return a successful "No market data is available for this request." message.
- [ ] Go tests (`go test ./...` in `services/mcp-gateway`) pass

## Technical notes

See Finding 3 in `.agent/reviews/2026-09-24-architecture.md`. Relevant files: `services/mcp-gateway/backendclient.go`, `services/mcp-gateway/tools.go`, `services/mcp-gateway/backendclient_test.go`, `services/mcp-gateway/tools_test.go`.

## Plan



## Review feedback


