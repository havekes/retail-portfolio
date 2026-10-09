## Plan

**Approach:**
Implement an HTTP request logging middleware in `services/indicator-service/middleware.go` that intercepts requests to `/health`, `/compute`, and unmatched routes. The middleware propagates or generates an RFC 4122 v4 UUID `X-Request-ID` (attaching it to response headers and context), wraps `http.ResponseWriter` to record status code and duration, and conditionally buffers the `/compute` request body in dev mode (`logger.Enabled(ctx, slog.LevelDebug)`) to emit verbose DEBUG logs while ensuring the stream remains readable by downstream handlers. In `services/indicator-service/handlers.go`, instrument `HealthHandler` and `ComputeHandler` to log 405 Method Not Allowed, 400 Malformed JSON, and 400 Calculation Failure errors using `slog.Warn` / `slog.Error` with structured attributes (`request_id`, `path`, `error`), and wire the middleware into `NewRouter` in `handlers.go` and `main.go`.

**Files:**
- `services/indicator-service/middleware.go` — create: Implement `LoggingMiddleware(logger *slog.Logger) func(http.Handler) http.Handler`, `statusResponseWriter`, `generateRequestID() string`, context helpers (`RequestIDFromContext`, `LoggerFromContext`, `WithRequestID`), request duration timing, and level-aware logging (DEBUG with payload for dev `/compute`, INFO for prod normal requests, WARN/ERROR for 4xx/5xx).
- `services/indicator-service/middleware_test.go` — create: Unit tests for request logging middleware: status code capture, duration recording, `X-Request-ID` propagation and generation, dev mode payload logging with uncorrupted body replay, prod mode suppression of payload dumps, and structured error logging.
- `services/indicator-service/handlers.go` — modify: Update `NewRouter(loggers ...*slog.Logger) http.Handler` to wrap routes with `LoggingMiddleware`; update `HealthHandler` and `ComputeHandler` to retrieve request ID from context and emit structured `slog.Warn` / `slog.Error` logs with `(request_id, path, error)` for invalid methods (405), malformed JSON (400), and indicator calculation failures (400).
- `services/indicator-service/handlers_test.go` — modify: Add assertions and tests verifying structured error logs on 405 invalid methods, 400 invalid JSON, and 400 calculation errors, and ensure all existing handler tests pass through the middleware-wrapped router.
- `services/indicator-service/main.go` — modify: Pass initialized `logger` into `NewRouter(logger)` to explicitly bind the configured logger to the HTTP middleware and router.

**Steps:**
1. Create `services/indicator-service/middleware.go`:
   - Define context key types and context helper functions:
     - `type contextKey string`
     - `const requestIDKey contextKey = "request_id"`, `const loggerKey contextKey = "logger"`
     - `RequestIDFromContext(ctx context.Context) string`
     - `LoggerFromContext(ctx context.Context) *slog.Logger`
   - Implement `generateRequestID() string`:
     - Read 16 cryptographically random bytes via `crypto/rand.Read`.
     - Set RFC 4122 version 4 and variant 1 bits.
     - Return formatted UUID string: `%08x-%04x-%04x-%04x-%012x`.
   - Implement `statusResponseWriter`:
     - Embed `http.ResponseWriter`.
     - Track `statusCode int` (default `http.StatusOK`) and `written bool`.
     - Implement `WriteHeader(statusCode int)` and `Write(b []byte) (int, error)`.
     - Implement `Unwrap() http.ResponseWriter` for middleware compatibility.
   - Implement `LoggingMiddleware(logger *slog.Logger) func(http.Handler) http.Handler`:
     - Fall back to `slog.Default()` if `logger` is nil.
     - Extract `X-Request-ID` header; if missing or empty, generate new ID via `generateRequestID()`.
     - Set `w.Header().Set("X-Request-ID", reqID)` immediately (before handler execution).
     - Attach request ID and scoped logger (`logger.With(slog.String("request_id", reqID))`) to `r.Context()`.
     - If debug logging is enabled (`logger.Enabled(r.Context(), slog.LevelDebug)`) and request has a body (e.g. `/compute`): read up to 10MB into memory via `io.ReadAll`, replace `r.Body` with `io.NopCloser(bytes.NewReader(bodyBytes))`, and retain `bodyBytes` for debug logging.
     - Record start time with `time.Now()`.
     - Execute downstream handler with wrapped `statusResponseWriter`.
     - Compute duration via `time.Since(start)`.
     - Determine log record:
       - If `logger.Enabled(r.Context(), slog.LevelDebug)`: log at DEBUG level with `method`, `path`, `status`, `duration_ms` (or `duration`), `remote_addr`, `request_id`, and `body` (if present and path is `/compute`).
       - If prod/info level:
         - For normal requests (status < 400): log at INFO level with `method`, `path`, `status`, `duration_ms`, `remote_addr`, `request_id` (omitting body dump).
         - For client errors (400 <= status < 500): log at WARN level with `method`, `path`, `status`, `duration_ms`, `remote_addr`, `request_id`.
         - For server errors (status >= 500): log at ERROR level with `method`, `path`, `status`, `duration_ms`, `remote_addr`, `request_id`.
2. Update `services/indicator-service/handlers.go`:
   - Change `NewRouter(loggers ...*slog.Logger) http.Handler`:
     - Resolve logger: use `loggers[0]` if provided, else `slog.Default()`.
     - Register `mux.HandleFunc("/health", HealthHandler)` and `mux.HandleFunc("/compute", ComputeHandler)`.
     - Return `LoggingMiddleware(logger)(mux)`.
   - Update `HealthHandler(w http.ResponseWriter, r *http.Request)`:
     - Retrieve `reqID := RequestIDFromContext(r.Context())` and `logger := LoggerFromContext(r.Context())`.
     - On non-GET method: log warning before returning 405:
       `logger.Warn("method not allowed", slog.String("request_id", reqID), slog.String("path", r.URL.Path), slog.String("error", "method not allowed"))`.
   - Update `ComputeHandler(w http.ResponseWriter, r *http.Request)`:
     - Retrieve `reqID := RequestIDFromContext(r.Context())` and `logger := LoggerFromContext(r.Context())`.
     - On non-POST method: log warning before returning 405:
       `logger.Warn("method not allowed", slog.String("request_id", reqID), slog.String("path", r.URL.Path), slog.String("error", "method not allowed"))`.
     - On JSON decode error (`dec.Decode(&req)`): log error before returning 400:
       `logger.Error("malformed json payload", slog.String("request_id", reqID), slog.String("path", r.URL.Path), slog.String("error", err.Error()))`.
     - On indicator calculation error (`ComputeIndicator(...)`): log error before returning 400:
       `logger.Error("indicator calculation failed", slog.String("request_id", reqID), slog.String("path", r.URL.Path), slog.String("error", err.Error()))`.
3. Update `services/indicator-service/main.go`:
   - Pass configured `logger` into `NewRouter(logger)`:
     `router := NewRouter(logger)`.
4. Create unit tests in `services/indicator-service/middleware_test.go`:
   - `TestLoggingMiddleware_RequestIDPropagation`: send request with `X-Request-ID: existing-id-123`; assert response header has `X-Request-ID: existing-id-123` and log buffer contains `request_id="existing-id-123"`.
   - `TestLoggingMiddleware_RequestIDGeneration`: send request without `X-Request-ID`; assert response header contains valid 36-character UUIDv4, and log buffer contains matching `request_id`.
   - `TestLoggingMiddleware_StatusCodeAndDuration`: send requests producing 200, 404, 405; assert recorded status code and duration in log attributes match the HTTP response.
   - `TestLoggingMiddleware_DevPayloadLogging`: configure logger with `SetupLogger("dev", "", buf)`; send POST `/compute` with JSON payload; verify DEBUG log record contains `body` matching the request content, and handler successfully computes indicators.
   - `TestLoggingMiddleware_ProdNormalRequest_NoBodyDump`: configure logger with `SetupLogger("prod", "", buf)`; send POST `/compute`; verify INFO log record is emitted with status 200, duration, request_id, and assert request body is NOT present in log output.
   - `TestLoggingMiddleware_ErrorStatusCodes`: configure logger with `SetupLogger("prod", "", buf)`; send request triggering 400; verify WARN log is emitted with `request_id`, `path`, and status.
5. Update tests in `services/indicator-service/handlers_test.go`:
   - Add test verifying `HealthHandler` logs 405 WARN with `request_id`, `path`, `error`.
   - Add test verifying `ComputeHandler` logs 405 WARN with `request_id`, `path`, `error`.
   - Add test verifying `ComputeHandler` logs 400 ERROR with `request_id`, `path`, `error` on malformed JSON (`TestComputeHandler_InvalidJSON`).
   - Add test verifying `ComputeHandler` logs 400 ERROR with `request_id`, `path`, `error` on calculation failure (`TestComputeHandler_UnknownIndicator`).
   - Ensure all existing tests in `handlers_test.go` continue to pass through `NewRouter()`.

**Verification:**
- `cd services/indicator-service && go test -v ./...`: Runs all unit tests (calculator, timeframe, logger, handlers, middleware) and verifies 100% pass rate.
- `cd services/indicator-service && go vet ./...`: Runs Go static analysis with zero warnings or errors.
- `cd services/indicator-service && go build ./...`: Compiles the binary cleanly.
- Acceptance Criteria mapping:
  - AC 1 (HTTP middleware wraps all endpoints, recording status code and request duration): Verified by `TestLoggingMiddleware_StatusCodeAndDuration` and `TestHealthHandler`/`TestComputeHandler` through router.
  - AC 2 (X-Request-ID propagation and generation): Verified by `TestLoggingMiddleware_RequestIDPropagation` and `TestLoggingMiddleware_RequestIDGeneration`.
  - AC 3 (Dev mode DEBUG logging with request content for /compute): Verified by `TestLoggingMiddleware_DevPayloadLogging`.
  - AC 4 (Prod mode no body dump on normal requests; 4xx/5xx logged with structured fields): Verified by `TestLoggingMiddleware_ProdNormalRequest_NoBodyDump` and `TestLoggingMiddleware_ErrorStatusCodes`.
  - AC 5 (Malformed JSON and indicator calculation failures emit structured error logs): Verified by `TestComputeHandler_InvalidJSON` and `TestComputeHandler_UnknownIndicator` in `handlers_test.go`.
  - AC 6 (Unit tests verify middleware request logging, X-Request-ID propagation, dev payload logging, error logging): Verified by `middleware_test.go` and `handlers_test.go`.
  - AC 7 (Build passes and relevant tests pass): Verified by `go vet ./...` and `go test -v ./...`.

**Risks / watch-outs:**
- **Request body draining:** In dev mode, reading `r.Body` for debug logging consumes the stream. It MUST be replaced with `io.NopCloser(bytes.NewReader(bodyBytes))` before invoking downstream handlers so `ComputeHandler` can decode JSON without EOF errors.
- **Response header timing:** In Go `net/http`, `w.Header().Set("X-Request-ID", ...)` MUST be called before calling `next.ServeHTTP(rw, r)` or before any `WriteHeader` invocation; otherwise the response header is discarded.
- **Variadic NewRouter signature:** Defining `NewRouter(loggers ...*slog.Logger) http.Handler` ensures backwards compatibility with existing test call sites (`NewRouter()`) while allowing `main.go` or tests to pass a custom logger (`NewRouter(logger)`).
