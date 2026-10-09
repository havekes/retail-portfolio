## Plan

**Approach:**
Add a configurable concurrency semaphore to `BackendClient` using a Go standard library buffered channel (`chan struct{}`) of capacity `MAX_CONCURRENCY` (defaulting to 10). In `BackendClient.get`, attempt a non-blocking acquire on the channel; if all slots are occupied, emit a structured `WARN` log event indicating the gateway is saturated and queuing behind the cap, then block awaiting an available slot or context cancellation. Release the acquired slot via `defer` upon completion of `BackendClient.get`, guaranteeing backpressure across all tools before and during backend response streaming.
Rejected alternative: `golang.org/x/sync/semaphore.Weighted` is viable, but a buffered channel is idiomatic standard library Go, requires no third-party package import, and natively supports non-blocking try-acquire with select. Updating `GET /health` with dynamic concurrency stats was rejected because `/health` is strictly a static liveness probe (`{"status":"ok"}`); an event-driven `WARN` log directly signals saturation without altering the liveness contract.

**Files:**
- `services/mcp-gateway/config.go` — modify: Add `defaultMaxConcurrency = 10`, `MaxConcurrency int` to `Config`, and parse/validate `MAX_CONCURRENCY` as a positive integer in `loadConfig`.
- `services/mcp-gateway/backendclient.go` — modify: Add `maxConcurrency int` and `sem chan struct{}` to `BackendClient`, enforce `maxConcurrency > 0` in `NewBackendClient`, and acquire/release the semaphore with saturation `WARN` logging in `BackendClient.get`.
- `services/mcp-gateway/main.go` — modify: Wire `cfg.MaxConcurrency` into `NewBackendClient` and log `max_concurrency` at startup and shutdown.
- `services/mcp-gateway/README.md` — modify: Document `MAX_CONCURRENCY` in the Configuration table and describe concurrency bounding and saturation logging behavior.
- `services/mcp-gateway/config_test.go` — modify: Add test cases for `MAX_CONCURRENCY` default value, valid parsing, invalid values ("0", "-5", "abc", "1.5"), and token leak prevention.
- `services/mcp-gateway/backendclient_test.go` — modify: Update `mustClient` helper with `defaultMaxConcurrency`, and add tests for invalid concurrency constructor validation, concurrency cap enforcement under load, saturation `WARN` logging without token/provider leaks, and context cancellation while queued.

**Steps:**
1. In `services/mcp-gateway/config.go`:
   - Define constant `defaultMaxConcurrency = 10`.
   - Add field `MaxConcurrency int` to struct `Config`.
   - In `loadConfig(getenv func(string) string)`: read `MAX_CONCURRENCY`; if non-empty, parse with `strconv.Atoi`. If `err != nil || val <= 0`, return `Config{}, fmt.Errorf("invalid MAX_CONCURRENCY %q: must be a positive integer", maxConcurrencyStr)`. If empty, assign `defaultMaxConcurrency`.
2. In `services/mcp-gateway/backendclient.go`:
   - Add fields `maxConcurrency int` and `sem chan struct{}` to struct `BackendClient`.
   - Update `NewBackendClient(baseURL, token string, maxConcurrency int, env ...string) (*BackendClient, error)`: return `errors.New("max concurrency must be greater than 0")` if `maxConcurrency <= 0`. Initialize `maxConcurrency: maxConcurrency` and `sem: make(chan struct{}, maxConcurrency)`. Add getter `MaxConcurrency() int`.
   - In `BackendClient.get(ctx context.Context, path string, query url.Values, out any) error`: after building `reqURL`, acquire semaphore slot:
     ```go
     select {
     case c.sem <- struct{}{}:
     case <-ctx.Done():
         bErr := &backendError{class: ErrProvider, detail: ctx.Err().Error()}
         slog.ErrorContext(ctx, "backend request failed", slog.String("url", reqURL), slog.Int("status", 0), slog.String("detail", bErr.Detail()))
         return bErr
     default:
         slog.WarnContext(ctx, "backend concurrency limit reached, queuing call", slog.Int("max_concurrency", c.maxConcurrency), slog.String("url", reqURL))
         select {
         case c.sem <- struct{}{}:
         case <-ctx.Done():
             bErr := &backendError{class: ErrProvider, detail: ctx.Err().Error()}
             slog.ErrorContext(ctx, "backend request failed", slog.String("url", reqURL), slog.Int("status", 0), slog.String("detail", bErr.Detail()))
             return bErr
         }
     }
     defer func() { <-c.sem }()
     ```
3. In `services/mcp-gateway/main.go`:
   - Update `NewBackendClient` invocation: `NewBackendClient(cfg.BackendBaseURL, cfg.ServiceToken, cfg.MaxConcurrency, cfg.Environment)`.
   - Add `slog.Int("max_concurrency", cfg.MaxConcurrency)` to startup and shutdown log calls.
4. In `services/mcp-gateway/README.md`:
   - Add row for `MAX_CONCURRENCY` to the Configuration table: optional, default `10`, description "Maximum concurrent outbound requests to the backend data plane. Must be a positive integer."
   - Under Outbound backend client logging / Backpressure, document that backend calls exceeding `MAX_CONCURRENCY` queue behind the semaphore and emit a `WARN` log record.
5. In `services/mcp-gateway/config_test.go`:
   - Update `TestLoadConfig/valid configuration` assertion to verify `cfg.MaxConcurrency == defaultMaxConcurrency`.
   - Add test cases for `MAX_CONCURRENCY`: default behavior on empty/whitespace, valid integer strings ("1", "5", "50", " 25 "), invalid values ("0", "-1", "-10", "abc", "1.5"), and assert error output never contains the secret token.
6. In `services/mcp-gateway/backendclient_test.go`:
   - Update helper `mustClient(t, baseURL, token string, env ...string)` to pass `defaultMaxConcurrency` to `NewBackendClient`.
   - Update `TestNewBackendClientRejectsBadBaseURL` to pass `defaultMaxConcurrency`.
   - Add `TestNewBackendClientRejectsInvalidMaxConcurrency(t *testing.T)` verifying 0 and -1 return errors.
   - Add `TestBackendClient_ConcurrencyCap(t *testing.T)`: spin up an `httptest.Server` with an atomic in-flight counter and high-water mark tracker, launch 10 concurrent requests through a client with `maxConcurrency = 2`, and assert that `maxInFlight <= 2` while all requests succeed.
   - Add `TestBackendClient_ConcurrencySaturationLogging(t *testing.T)`: configure test logger buffer, instantiate client with `maxConcurrency = 1`, hold one call in flight in stub backend, issue a second call in a separate goroutine, assert `WARN` level log `"backend concurrency limit reached, queuing call"` appears in the log buffer, and assert no secret tokens or provider names appear in the log.
   - Add `TestBackendClient_ContextCanceledWhileQueued(t *testing.T)`: with `maxConcurrency = 1`, occupy the slot, issue a second call with an already canceled context, assert it returns `ErrProvider` / context canceled without hanging.
7. Verification:
   - Run `go vet ./...` in `services/mcp-gateway`.
   - Run `go build ./...` in `services/mcp-gateway`.
   - Run `go test -v -race ./...` in `services/mcp-gateway`.

**Verification:**
- **AC1 (`MAX_CONCURRENCY` bounds concurrent backend calls & default documented):**
  - Run `go test -v -run TestBackendClient_ConcurrencyCap services/mcp-gateway` — verify passes with concurrency strictly capped at configured limit.
  - Verify `services/mcp-gateway/README.md` configuration table lists `MAX_CONCURRENCY` with default `10`.
- **AC2 (Invalid values fail at startup like other config errors):**
  - Run `go test -v -run TestLoadConfig services/mcp-gateway` — verify invalid values ("0", "-5", "abc", "1.5") fail configuration loading with clear errors and no token leakage.
  - Run `go test -v -run TestNewBackendClientRejectsInvalidMaxConcurrency services/mcp-gateway` — verify non-positive values fail constructor validation.
- **AC3 (Saturation is observable without changing the liveness contract):**
  - Run `go test -v -run TestBackendClient_ConcurrencySaturationLogging services/mcp-gateway` — verify `WARN` level log event with message `backend concurrency limit reached, queuing call` is emitted when queuing occurs.
  - Run `go test -v -run TestHealthEndpoint services/mcp-gateway` — verify `GET /health` continues returning fixed 200 `{"status":"ok"}`.
- **AC4 (Existing tests pass; new tests cover cap and config validation):**
  - Run `go test -v services/mcp-gateway` — verify all existing and new unit tests pass.
- **AC5 (Tooling pass):**
  - Run `go vet ./...`, `go build ./...`, and `go test -race ./...` inside `services/mcp-gateway` — all commands must succeed with exit code 0.

**Risks / watch-outs:**
- Context cancellation cleanup: when context is canceled while blocked on `c.sem`, the goroutine must return immediately without acquiring or leaking a channel slot. The nested select block cleanly guarantees this.
- Deadlock prevention in tests: stub servers in concurrency tests that hold requests open must use signaling channels with cleanup/timeouts (or `sync.WaitGroup`) so test failures do not hang `go test`.
- Sensitive token redaction: the new `slog.WarnContext` call in `BackendClient.get` logs `reqURL` and `max_concurrency`. `reqURL` contains path and query params only — `X-Service-Token` is set on headers and is never included in the URL or log line.
