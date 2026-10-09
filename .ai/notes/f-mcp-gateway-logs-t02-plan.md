## Plan

**Approach:** Implement structured inbound HTTP logging middleware in `services/mcp-gateway/middleware.go` wrapping the router in `main.go`, instrument `runTool` and `statementHandler` in `tools.go` with invocation/completion debug logging and structured error logging using `backendError.Detail()`, and instrument `BackendClient.get` in `backendclient.go` with request/response debug logging and error logging while strictly redacting `X-Service-Token` and sensitive headers (`Authorization`, `Cookie`, `Set-Cookie`). This approach adheres strictly to standard library `log/slog` and `net/http` patterns, guarantees zero secret token leakage, and complies with the upstream provider-name rule across all log paths.
*Rejected alternatives:* Injecting logging into individual tool functions was rejected in favor of `runTool` and `statementHandler`, which already serve as the unified pipeline for input preparation, backend invocation, and error mapping; external HTTP middleware libraries were rejected to keep dependencies minimal and aligned with Go standard library `log/slog`.

**Files:**
- `services/mcp-gateway/middleware.go` — create: Inbound HTTP logging middleware wrapping `http.Handler` with response status/duration capture, sensitive header redaction (`Authorization`, `X-Service-Token`, `Cookie`, `Set-Cookie`), verbose debug logging in `ENVIRONMENT=dev`, and structured completion logging.
- `services/mcp-gateway/middleware_test.go` — create: Unit tests for HTTP logging middleware verifying status/duration logging, dev request detail logging, sensitive header redaction, token omission, and prod suppression.
- `services/mcp-gateway/backendclient.go` — modify: Add environment awareness (`env` string / dev check) to `BackendClient`, instrument `c.get` with DEBUG request/response logging in dev, and ERROR logging on non-2xx responses and network failures with `status` and `detail` while strictly redacting `X-Service-Token`.
- `services/mcp-gateway/backendclient_test.go` — modify: Add unit tests for outbound backend client debug logging in dev, error logging on 4xx/5xx/network errors, verification of `MARKET_DATA_SERVICE_TOKEN` redaction in logs, and compliance with the provider-name rule.
- `services/mcp-gateway/tools.go` — modify: Pass tool names into `runTool` and `statementHandler`, add debug logging for tool invocation and completion in dev, and add structured error logging at ERROR level with `tool`, `arguments`, `error_class`, `status`, and `detail` (using `backendError.Detail()`).
- `services/mcp-gateway/tools_test.go` — modify: Add tests for tool execution debug logging in dev, error logging on backend/validation failures, and verification that tool log entries adhere to the provider-name rule and contain no secret tokens.
- `services/mcp-gateway/mcpserver.go` — modify: Update `newMCPServer` to propagate environment to tool handlers and pass tool names to all `runTool` calls.
- `services/mcp-gateway/main.go` — modify: Pass `cfg.Environment` to `NewBackendClient` and `newMCPServer`, and wrap the router with `loggingMiddleware(router, cfg.Environment)`.
- `services/mcp-gateway/README.md` — modify: Document HTTP request logging, tool execution logging, outbound backend client logging, and header redaction behavior.

**Steps:**
1. Implement HTTP logging middleware in `services/mcp-gateway/middleware.go`:
   - Implement `responseWriter` wrapping `http.ResponseWriter` with `statusCode` tracking (defaulting to `http.StatusOK`), `wroteHeader` guard, and explicit `http.Flusher` delegation for SSE streaming compatibility.
   - Implement sensitive header check `isSensitiveHeader(name string) bool` matching `Authorization`, `X-Service-Token`, `Cookie`, and `Set-Cookie` case-insensitively, redacting matched values to `"[REDACTED]"`.
   - Implement `loggingMiddleware(next http.Handler, env string) http.Handler`:
     - In `ENVIRONMENT=dev` (`isDev`): read request body (up to 64KB, restoring `r.Body = io.NopCloser(bytes.NewReader(bodyBytes))`), sanitize headers, and log incoming request details (`method`, `path`, `headers`, `query`, `body`) at `slog.LevelDebug`.
     - Delegate to `next.ServeHTTP(rw, r)`.
     - Calculate duration with `time.Since(start)` and emit completion log at `slog.LevelInfo` with `method`, `path`, `remote_addr`, `status`, and `duration`.
2. Implement middleware unit tests in `services/mcp-gateway/middleware_test.go`:
   - Test structured log output on requests to `/health` and `/mcp` confirming presence of `method`, `path`, `remote_addr`, `status`, and `duration`.
   - Test `ENVIRONMENT=dev` emits DEBUG request details (headers, query, body) and `ENVIRONMENT=prod` suppresses DEBUG request details.
   - Test sensitive header redaction: verify `Authorization`, `X-Service-Token`, `Cookie`, and `Set-Cookie` are replaced with `"[REDACTED]"` and secret values never appear.
   - Test `http.Flusher` pass-through behavior on wrapped `responseWriter`.
3. Update `services/mcp-gateway/backendclient.go` to log outbound requests and errors:
   - Add optional environment configuration to `BackendClient` via `NewBackendClient(baseURL, token string, env ...string)` with helper `isDev() bool`.
   - In `c.get(ctx, path, query, out)`:
     - In `ENVIRONMENT=dev`: log outbound request (`method`, `url`, `query`) and response status + duration at `slog.LevelDebug`.
     - On network error (`httpClient.Do`), body read error, non-2xx status, or JSON decode error: log at `slog.LevelError` with `status`, `detail` (from `backendError.Detail()`), and endpoint URL.
     - Ensure `c.token` and `X-Service-Token` are never logged in any message or attribute.
     - Ensure generic vocabulary is used (no provider brands).
4. Update `services/mcp-gateway/backendclient_test.go`:
   - Test outbound request debug logging in `ENVIRONMENT=dev`: verify method, endpoint URL, query, and response status are captured in buffer.
   - Test outbound error logging on non-2xx statuses (404, 422, 500) and network errors: verify `status` and `detail` are emitted at ERROR level.
   - Assert `MARKET_DATA_SERVICE_TOKEN` and token values are absent from all log output.
   - Assert log records contain no provider names using `providerNames`.
5. Update `services/mcp-gateway/tools.go` for tool execution and error logging:
   - Update `runTool` signature to accept `toolName string` and `env string` (or `client`'s environment).
   - In `runTool`:
     - In `ENVIRONMENT=dev`: log tool invocation at `slog.LevelDebug` with `tool` and `arguments`.
     - On input validation failure (`prepare` error): log at `slog.LevelError` with `tool`, `arguments`, `error_class="ErrValidation"`, `status=400`, and `detail=err.Error()`.
     - On backend execution error:
       - If `errors.Is(err, ErrNoData)`: treat as success result per contract; in dev log completion at `slog.LevelDebug`.
       - For failures (`ErrValidation`, `ErrConfiguration`, `ErrProvider`, other): log at `slog.LevelError` with `tool`, `arguments`, `error_class`, `status` (from `backendErr.Status()`), and `detail` (from `backendErr.Detail()`).
     - On tool completion: in `ENVIRONMENT=dev`, log at `slog.LevelDebug` with `tool`, `duration`, and `response` payload content.
   - Update `statementHandler` and all `addTool` registrations in `registerTools` to pass their respective tool names to `runTool`.
6. Update `services/mcp-gateway/tools_test.go`:
   - Test tool execution in `ENVIRONMENT=dev`: verify `DEBUG` logs contain tool name, input arguments, execution duration, and response payload content.
   - Test tool execution errors (validation error, 422 backend validation, 401 configuration error, 500 provider error): verify `ERROR` logs contain `tool`, `arguments`, `error_class`, `status`, and `detail`.
   - Verify `ErrNoData` (404) does not emit ERROR logs and logs clean completion in dev.
   - Assert no tool log output contains upstream provider brands using `providerNames`.
7. Wire middleware and environment into `services/mcp-gateway/main.go` and `mcpserver.go`:
   - In `mcpserver.go`: update `newMCPServer(client *BackendClient, env ...string)` to propagate environment to tool handlers.
   - In `main.go`: pass `cfg.Environment` to `NewBackendClient` and `newMCPServer`.
   - Wrap the HTTP router with `loggingMiddleware(router, cfg.Environment)`.
8. Update documentation in `services/mcp-gateway/README.md`:
   - Document HTTP request logging middleware, dev verbose logging, sensitive header redaction, tool execution logging, and outbound backend client logging.
9. Verification and quality checks:
   - Run `go vet ./...` in `services/mcp-gateway`.
   - Run `go test -v ./...` in `services/mcp-gateway` to ensure all existing and new tests pass.

**Verification:**
- AC 1 (Inbound HTTP logging on `/health` and `/mcp`): Run `go test -v -run TestLoggingMiddleware_InboundRequests ./...` in `services/mcp-gateway` to verify structured HTTP log entries with method, path, remote address, status, and duration for `/health` and `/mcp`.
- AC 2 (Dev HTTP request details & header redaction): Run `go test -v -run TestLoggingMiddleware_DevAndRedaction ./...` in `services/mcp-gateway` to verify that `ENVIRONMENT=dev` logs safe headers, query, and body at DEBUG level, while `Authorization`, `X-Service-Token`, `Cookie`, and `Set-Cookie` are redacted with `"[REDACTED]"`, and verify DEBUG logs are suppressed in `ENVIRONMENT=prod`.
- AC 3 (Dev tool execution debug logging): Run `go test -v -run TestTools_DevExecutionLogging ./...` in `services/mcp-gateway` to verify tool name, input arguments, execution duration, and response payload content are emitted at DEBUG level in dev.
- AC 4 (Tool execution error logging): Run `go test -v -run TestTools_ErrorLogging ./...` in `services/mcp-gateway` to verify that tool failures emit ERROR log entries with `tool`, `arguments`, `error_class`, `status`, and `detail` (from `backendError.Detail()`), while `ErrNoData` emits no ERROR log.
- AC 5 (Outbound backend client error logging & token redaction): Run `go test -v -run TestBackendClient_Logging ./...` in `services/mcp-gateway` to verify outbound requests log at DEBUG level in dev, non-2xx responses and network failures log at ERROR level with `status` and `detail`, and `MARKET_DATA_SERVICE_TOKEN` value is never logged.
- AC 6 (Provider-name rule compliance): Run `go test -v -run "Test.*ProviderName.*" ./...` across all test suites to confirm no log messages, attributes, or tool outputs leak provider brands.
- AC 7 (Unit test coverage): Run `go test -v ./...` in `services/mcp-gateway` to confirm comprehensive passing test coverage across `middleware_test.go`, `tools_test.go`, `backendclient_test.go`, `logger_test.go`, and `config_test.go`.
- AC 8 (Build and vet): Run `go vet ./...` and `go build ./...` in `services/mcp-gateway` to confirm clean compilation with no warnings or errors.

**Risks / watch-outs:**
- Request body consumption in HTTP middleware: reading `r.Body` consumes the stream; `middleware.go` must replace `r.Body` with `io.NopCloser(bytes.NewReader(bodyBytes))` so downstream handlers (like `mcp.NewStreamableHTTPHandler`) can read the request. Body reads must also be bounded (e.g. `io.LimitReader(r.Body, 64<<10)`) to prevent memory exhaustion.
- `http.Flusher` support in `responseWriter`: the MCP streamable transport uses SSE streaming; the wrapped `responseWriter` must explicitly implement `http.Flusher` delegating to the underlying writer, or streaming responses will fail to flush chunks in real time.
- Diagnostic detail leak to MCP agents: ensure `backendError.Detail()` is passed only to `slog.ErrorContext` and never forwarded into `errorResult` returned to the MCP client session, preserving the contract of generic user-facing errors.
- Sensitive header case sensitivity: HTTP header lookups must be case-insensitive (e.g., matching `authorization`, `x-service-token`, `cookie`, `set-cookie` regardless of incoming case).
