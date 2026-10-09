## Plan
**Approach:** Extract the HTTP request/decode/error/logging pipeline from `BackendClient.get` into a reusable `Transport` and `RouteGroup` core (`transport.go`) supporting method-agnostic operations (GET + POST), parameterized path prefixes, and domain auth tokens. Consolidate variadic `env ...string` threading across server, client, and tools into a single `Config` struct initialized once by `loadConfig`. Re-point the five market-data client methods onto the route group and document the "add a new tool domain" recipe in `services/mcp-gateway/README.md`.
Rejected alternative: Keeping transport methods on `BackendClient` and passing route prefix per call causes domain leak across data domains; separating `Transport` and `RouteGroup` cleanly isolates domain route paths and auth tokens.

**Files:**
- `services/mcp-gateway/transport.go` — create: define `Transport` (`NewTransport(cfg Config)`) and `RouteGroup` (`NewRouteGroup(prefix, token)`) with method-agnostic `Do`, `Get`, and `Post`, preserving dev debug logging, error logging, and error classification (`classifyBackendError`).
- `services/mcp-gateway/transport_test.go` — create: unit tests for `Transport` and `RouteGroup` verifying GET, POST with JSON body serialization, query encoding, route group isolation, and log output.
- `services/mcp-gateway/backendclient.go` — modify: refactor `BackendClient` to wrap `*RouteGroup`, update `NewBackendClient(cfg Config)`, and delegate `Prices`, `SymbolSearch`, `OptionsChain`, `Fundamentals`, `Statements` to `c.group.Get`.
- `services/mcp-gateway/backendclient_test.go` — modify: update `mustClient` helper and `TestNewBackendClientRejectsBadBaseURL` to construct `Config` for `NewBackendClient`, preserving all existing test assertions unmodified.
- `services/mcp-gateway/mcpserver.go` — modify: update `newMCPServer(client *BackendClient, cfg Config)` removing `env ...string`.
- `services/mcp-gateway/tools.go` — modify: update `registerTools(server *mcp.Server, client *BackendClient, cfg Config)`, `statementHandler(client *BackendClient, toolName, statement string, cfg Config)`, and `runTool[In, Req](ctx context.Context, toolName string, cfg Config, ...)` removing `env ...string` and `env string`.
- `services/mcp-gateway/main.go` — modify: pass `cfg` directly to `NewBackendClient(cfg)` and `newMCPServer(client, cfg)`.
- `services/mcp-gateway/mcpserver_test.go` — modify: pass `Config{Environment: "dev"}` to `newMCPServer`.
- `services/mcp-gateway/middleware_test.go` — modify: pass `Config{Environment: "prod"}` to `newMCPServer`.
- `services/mcp-gateway/tools_test.go` — modify: update `newMCPServer` call sites to pass `Config`.
- `services/mcp-gateway/README.md` — modify: document the "Adding a new tool domain" recipe (route group → client file → registerTools wiring) and explain the generalized transport architecture.

**Steps:**
1. Create `services/mcp-gateway/transport.go`:
   - Implement `Transport` holding `baseURL *url.URL`, `httpClient *http.Client`, and `cfg Config`, with constructor `NewTransport(cfg Config) (*Transport, error)` validating `cfg.BackendBaseURL`.
   - Implement `RouteGroup` holding `transport *Transport`, `prefix string`, and `token string`, with `(t *Transport) NewRouteGroup(prefix, token string) *RouteGroup`.
   - Implement `(g *RouteGroup) Do(ctx context.Context, method, path string, query url.Values, body any, out any) error`:
     - Construct request URL from `transport.baseURL + prefix + path` and query string.
     - Serialize `body` to JSON if provided (`body != nil`), setting `Content-Type: application/json`.
     - Set headers: `X-Service-Token` (from `g.token`), `Accept: application/json`.
     - Emit dev-mode request debug log: `slog.DebugContext(ctx, "backend request", slog.String("method", method), slog.String("url", reqURL), slog.String("query", query.Encode()))`.
     - Execute via `g.transport.httpClient.Do(req)`. On network/transport error, log at `ERROR` level and return `&backendError{class: ErrProvider, detail: err.Error()}`.
     - Emit dev-mode response debug log: `slog.DebugContext(ctx, "backend response", slog.String("method", method), slog.String("url", reqURL), slog.Int("status", resp.StatusCode), slog.Duration("duration", duration))`.
     - Read body up to `maxResponseBytes = 8 << 20`.
     - Classify non-2xx status via `classifyBackendError`, log at `ERROR` level with URL, status, and detail, and return the error.
     - Decode JSON into `out` when `out != nil`. On unmarshal failure, log at `ERROR` level and return `ErrProvider`.
   - Implement `(g *RouteGroup) Get(ctx context.Context, path string, query url.Values, out any) error` and `(g *RouteGroup) Post(ctx context.Context, path string, query url.Values, body any, out any) error` wrapping `Do`.
2. Implement unit tests in `services/mcp-gateway/transport_test.go`:
   - Test GET and POST operations with query parameters and request bodies.
   - Test route group prefix and token isolation (two route groups with different prefixes and tokens on the same transport).
   - Test error classification and dev debug / non-2xx error log output.
3. Refactor `services/mcp-gateway/backendclient.go`:
   - Update `BackendClient` to hold `group *RouteGroup` (and `cfg Config`).
   - Update `NewBackendClient(cfg Config) (*BackendClient, error)`: instantiate `Transport` via `NewTransport(cfg)` and `RouteGroup` via `transport.NewRouteGroup(dataPlanePath, cfg.ServiceToken)`.
   - Re-point `Prices`, `SymbolSearch`, `OptionsChain`, `Fundamentals`, and `Statements` to `c.group.Get(ctx, path, query, &out)`.
4. Update `services/mcp-gateway/backendclient_test.go`:
   - Update test helper `mustClient(t, baseURL, token, env...)` to construct `Config{BackendBaseURL: baseURL, ServiceToken: token, Environment: ...}` and call `NewBackendClient(cfg)`.
   - Update `TestNewBackendClientRejectsBadBaseURL` to call `NewBackendClient(Config{BackendBaseURL: raw, ServiceToken: "token"})`.
   - Verify all existing tests in `backendclient_test.go` remain unmodified in their test logic.
5. Consolidate `env ...string` across server, client, and tools:
   - In `services/mcp-gateway/mcpserver.go`: change signature to `newMCPServer(client *BackendClient, cfg Config) *mcp.Server` and pass `cfg` to `registerTools`.
   - In `services/mcp-gateway/tools.go`: change signatures to `registerTools(server *mcp.Server, client *BackendClient, cfg Config)`, `statementHandler(client *BackendClient, toolName, statement string, cfg Config)`, and `runTool[In, Req](ctx context.Context, toolName string, cfg Config, ...)`.
   - In `services/mcp-gateway/main.go`: pass `cfg` directly to `NewBackendClient(cfg)` and `newMCPServer(client, cfg)`.
6. Update test call sites:
   - In `services/mcp-gateway/mcpserver_test.go`: update `newMCPServer(client, Config{Environment: "dev"})`.
   - In `services/mcp-gateway/middleware_test.go`: update `newMCPServer(client, Config{Environment: "prod"})`.
   - In `services/mcp-gateway/tools_test.go`: update `newMCPServer(client, Config{Environment: "dev"})` and `newMCPServer(client, Config{Environment: env})`.
7. Update documentation in `services/mcp-gateway/README.md`:
   - Add section `## Adding a new tool domain` detailing the 3-step workflow:
     1. Configure route group (prefix and token in `config.go` / `transport.NewRouteGroup`).
     2. Create domain client file (wrapping `*RouteGroup` and implementing typed domain methods).
     3. Register MCP tools (`registerTools` wiring closing over the domain client).
   - Document the generalized transport architecture and GET/POST support.
8. Run verification commands:
   - Run `cd services/mcp-gateway && go vet ./...`
   - Run `cd services/mcp-gateway && go test -v ./...`
   - Confirm all existing and new tests pass with zero regressions.

**Verification:**
- AC1 (Transport core GET/POST & wire behaviour): `cd services/mcp-gateway && go test -v -run "TestBackendClientEndpoints|TestBackendClientDecodesRealBackendShapes|TestTransport"` passes.
- AC2 (No variadic env ...string threading): Verify `git grep "env \.\.\.string" services/mcp-gateway` returns empty and `cd services/mcp-gateway && go vet ./...` succeeds.
- AC3 (Error classification & logging): `cd services/mcp-gateway && go test -v -run "TestBackendClientErrorTaxonomy|TestBackendClient_Logging|TestTools_ErrorLogging"` passes.
- AC4 (README documentation): Inspect `services/mcp-gateway/README.md` to confirm the "Adding a new tool domain" recipe is documented with route group, client file, and tool registration instructions.
- AC5 (All vet and test suites green): `cd services/mcp-gateway && go vet ./... && go test ./...` exits 0.

**Risks / watch-outs:**
- `io.LimitReader` body capping (`maxResponseBytes = 8 << 20`) and error detail truncation (`errorDetailLimit = 512`) must remain identical in `transport.go` so oversized response handling and log lines do not drift.
- `serviceTokenHeader` redaction must be maintained: never log `X-Service-Token` or the raw token value.
