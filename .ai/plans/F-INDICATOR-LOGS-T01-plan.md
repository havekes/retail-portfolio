## Plan

**Approach:**
Implement a lightweight standard library `log/slog` initialization helper `SetupLogger` (and `ParseLogLevel`) in `services/indicator-service/logger.go` that configures `slog.NewJSONHandler` for `prod` and `slog.NewTextHandler` for `dev` or unset, supporting an optional `LOG_LEVEL` environment variable override. In `services/indicator-service/main.go`, replace all legacy stdlib `log` calls with structured `slog` logging emitting `service`, `port`, and `environment` attributes during startup, shutdown timeout, shutdown error, and shutdown completion. Finally, wire `ENVIRONMENT` into `indicator-service` configurations in `docker-compose.yml` and `docker-compose.prod.yml`, and cover all permutations with unit tests in `services/indicator-service/logger_test.go`.

**Files:**
- `services/indicator-service/logger.go` — create: Implement `SetupLogger(env, logLevel string, out io.Writer) *slog.Logger` and `ParseLogLevel(levelStr string, defaultLevel slog.Level) slog.Level` configuring JSON/Text handlers and log level resolution.
- `services/indicator-service/logger_test.go` — create: Table-driven unit tests verifying JSON vs Text handler selection, default levels across `prod` and `dev`/unset, `LOG_LEVEL` overrides, case-insensitivity, and fallback behavior.
- `services/indicator-service/main.go` — modify: Initialize structured `slog` logger with `os.Getenv("ENVIRONMENT")` and `os.Getenv("LOG_LEVEL")`, set it as default via `slog.SetDefault`, and replace all legacy `log` calls with structured `logger.Info` / `logger.Warn` / `logger.Error` calls including `service`, `port`, and `environment` attributes.
- `docker-compose.yml` — modify: Add `ENVIRONMENT: "${ENVIRONMENT:-dev}"` under `indicator-service.environment`.
- `docker-compose.prod.yml` — modify: Add `ENVIRONMENT: "${ENVIRONMENT:-prod}"` under `indicator-service.environment`.

**Steps:**
1. Create `services/indicator-service/logger.go`:
   - Define `ParseLogLevel(levelStr string, defaultLevel slog.Level) slog.Level` parsing `DEBUG`, `INFO`, `WARN`/`WARNING`, and `ERROR` case-insensitively, falling back to `defaultLevel`.
   - Define `SetupLogger(env, logLevel string, out io.Writer) *slog.Logger`:
     - Default `out` to `os.Stdout` if nil.
     - Determine handler type and default level: if `strings.EqualFold(strings.TrimSpace(env), "prod")`, use `slog.NewJSONHandler` with default `slog.LevelInfo`; otherwise use `slog.NewTextHandler` with default `slog.LevelDebug`.
     - Resolve active level by passing `logLevel` and default level to `ParseLogLevel`.
     - Construct and return `slog.New(handler)`.
2. Create unit tests in `services/indicator-service/logger_test.go`:
   - Test table covering permutations of `ENVIRONMENT` (`prod`, `dev`, `""`, `"PROD"`) and `LOG_LEVEL` (`""`, `"DEBUG"`, `"INFO"`, `"WARN"`, `"ERROR"`, `"debug"`, invalid).
   - Verify handler formatting: assert output from `prod` parses as valid JSON with keys `"time"`, `"level"`, `"msg"`; assert output from `dev`/unset contains text key-value formatting (`level=... msg=...`).
   - Verify level filtering: assert messages below configured level are suppressed and messages at or above configured level are emitted.
3. Update `services/indicator-service/main.go`:
   - Remove `"log"` import; import `"log/slog"`.
   - Read `ENVIRONMENT`, `LOG_LEVEL`, and `PORT` environment variables.
   - Initialize logger using `logger := SetupLogger(env, logLevel, os.Stdout)` and call `slog.SetDefault(logger)`.
   - Replace `log.Printf("indicator-service listening on port %s\n", port)` with `logger.Info("indicator-service listening", slog.String("service", "indicator-service"), slog.String("port", port), slog.String("environment", env))`.
   - Replace `log.Fatalf("server failed to start: %v\n", err)` with `logger.Error("server failed to start", slog.String("service", "indicator-service"), slog.String("port", port), slog.String("environment", env), slog.String("error", err.Error()))` followed by `os.Exit(1)`.
   - Replace `log.Println("graceful shutdown timed out.. forcing exit.")` with `logger.Warn("graceful shutdown timed out.. forcing exit", slog.String("service", "indicator-service"), slog.String("port", port), slog.String("environment", env))`.
   - Replace `log.Printf("server shutdown error: %v\n", err)` with `logger.Error("server shutdown error", slog.String("service", "indicator-service"), slog.String("port", port), slog.String("environment", env), slog.String("error", err.Error()))`.
   - Replace `log.Println("indicator-service stopped")` with `logger.Info("indicator-service stopped", slog.String("service", "indicator-service"), slog.String("port", port), slog.String("environment", env))`.
4. Update Docker Compose files:
   - In `docker-compose.yml`, add `environment:` section to `indicator-service` with `ENVIRONMENT: "${ENVIRONMENT:-dev}"`.
   - In `docker-compose.prod.yml`, add `environment:` section to `indicator-service` with `ENVIRONMENT: "${ENVIRONMENT:-prod}"`.
5. Run verification suite:
   - Run `cd services/indicator-service && go vet ./...` to verify Go code cleanliness.
   - Run `cd services/indicator-service && go test -v ./...` to verify all existing and new unit tests pass.
   - Run `cd services/indicator-service && go build ./...` to verify binary compiles.
   - Run `docker compose config` and `docker compose -f docker-compose.prod.yml config` to verify compose syntax.

**Verification:**
- Unit tests & coverage: `cd services/indicator-service && go test -v ./...` passes, including all permutations of `ENVIRONMENT` and `LOG_LEVEL` in `logger_test.go`.
- Static analysis & vet: `cd services/indicator-service && go vet ./...` reports zero issues.
- Service build: `cd services/indicator-service && go build ./...` compiles cleanly without warnings or errors.
- Compose syntax: `docker compose config` and `docker compose -f docker-compose.prod.yml config` validate successfully, showing `ENVIRONMENT` configured for `indicator-service`.
- AC check:
  - AC 1 & 2: Verified by `TestSetupLogger_HandlerAndLevel` in `logger_test.go`.
  - AC 3: Verified by `main.go` code inspection and clean compile.
  - AC 4 & 5: Verified by `docker compose config` output.
  - AC 6 & 7: Verified by test and build commands above.

**Risks / watch-outs:**
- `log.Fatalf` implicitly exits the program with status code 1. When replacing it with `logger.Error(...)`, an explicit `os.Exit(1)` must be called so startup failure exits the container immediately.
- Handler output validation in tests should handle newline delimiter when parsing multiple JSON log records from a `bytes.Buffer`.
