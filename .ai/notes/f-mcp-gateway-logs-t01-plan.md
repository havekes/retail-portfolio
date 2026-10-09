## Plan

**Approach:** Add `Environment` and `LogLevel` fields to `Config` in `services/mcp-gateway/config.go` with defaults (`dev` environment) and validation. Implement a standard library `log/slog` helper in `services/mcp-gateway/logger.go` selecting `slog.NewJSONHandler` at `slog.LevelInfo` for `ENVIRONMENT=prod` and `slog.NewTextHandler` at `slog.LevelDebug` for `ENVIRONMENT=dev` or unset, with optional `LOG_LEVEL` overriding default levels. In `services/mcp-gateway/main.go`, replace standard `log` calls with structured `slog` logging for startup and shutdown (emitting `service`, `port`, `backend_url`, `environment` while strictly omitting sensitive tokens), and wire `ENVIRONMENT` into Docker Compose configurations and service documentation.

**Alternative considered:** Configuring logging directly inside `config.go` or inline in `main.go` was rejected in favor of a dedicated `logger.go` helper to keep configuration parsing decoupled from logging handler instantiation and allow clean, isolated unit testing of handler formats and log levels.

**Files:**
- `services/mcp-gateway/config.go` — modify: add `Environment` and `LogLevel` fields to `Config`, parse `ENVIRONMENT` (default `dev`) and optional `LOG_LEVEL` (`DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`) with validation in `loadConfig`.
- `services/mcp-gateway/config_test.go` — modify: add tests for `ENVIRONMENT` defaults, overrides, whitespace trimming, and `LOG_LEVEL` parsing and validation.
- `services/mcp-gateway/logger.go` — create: implement `newLogger(w io.Writer, env string, levelStr string) (*slog.Logger, error)` and `initLogger(cfg Config) (*slog.Logger, error)` setting `slog.SetDefault()`.
- `services/mcp-gateway/logger_test.go` — create: add unit tests verifying handler type (`*slog.JSONHandler` in prod vs `*slog.TextHandler` in dev/unset), default log levels (`INFO` vs `DEBUG`), `LOG_LEVEL` overrides, output formatting, and token omission.
- `services/mcp-gateway/main.go` — modify: replace standard `log` package with `log/slog` calls, initialize slog via `initLogger(cfg)`, emit structured startup and shutdown events with attributes (`service`, `port`, `backend_url`, `environment`), and handle exit on failures.
- `docker-compose.yml` — modify: add `ENVIRONMENT: "${ENVIRONMENT:-dev}"` under `services.mcp-gateway.environment`.
- `docker-compose.prod.yml` — modify: add `ENVIRONMENT: "${ENVIRONMENT:-prod}"` under `services.mcp-gateway.environment`.
- `services/mcp-gateway/README.md` — modify: document `ENVIRONMENT` and `LOG_LEVEL` in configuration table and description.

**Steps:**
1. **Extend `Config` in `services/mcp-gateway/config.go`:**
   - Add `Environment string` and `LogLevel string` fields to `Config` struct.
   - Define `defaultEnvironment = "dev"`.
   - In `loadConfig(getenv)`:
     - Read `ENVIRONMENT`, trim whitespace, lowercase it; default to `dev` if empty.
     - Read optional `LOG_LEVEL`, trim whitespace, uppercase it.
     - Validate that if `LOG_LEVEL` is non-empty, it must be one of `DEBUG`, `INFO`, `WARN`, `WARNING`, `ERROR`; return an error otherwise.
2. **Add configuration unit tests in `services/mcp-gateway/config_test.go`:**
   - Test default `Environment` is `"dev"` when unset or whitespace.
   - Test `Environment` parsed as `"prod"` and `"dev"`.
   - Test optional `LOG_LEVEL` parsing for valid values (`DEBUG`, `INFO`, `WARN`, `ERROR`).
   - Test invalid `LOG_LEVEL` returns an error mentioning `LOG_LEVEL` without leaking tokens.
3. **Implement logger helper in `services/mcp-gateway/logger.go`:**
   - Define `parseLogLevel(levelStr string, defaultLevel slog.Level) (slog.Level, error)` to parse `LOG_LEVEL` strings into `slog.Level`.
   - Implement `newLogger(w io.Writer, env string, levelStr string) (*slog.Logger, error)`:
     - If `env == "prod"`, default level is `slog.LevelInfo`, handler is `slog.NewJSONHandler(w, opts)`.
     - Otherwise (`dev` or unset), default level is `slog.LevelDebug`, handler is `slog.NewTextHandler(w, opts)`.
     - If `levelStr != ""`, override default level with `parseLogLevel`.
     - Return `slog.New(handler), nil`.
   - Implement `initLogger(cfg Config) (*slog.Logger, error)`:
     - Call `newLogger(os.Stdout, cfg.Environment, cfg.LogLevel)`.
     - Call `slog.SetDefault(logger)`.
     - Return `logger, nil`.
4. **Implement unit tests in `services/mcp-gateway/logger_test.go`:**
   - Verify handler type: assert `*slog.JSONHandler` when `env="prod"` and `*slog.TextHandler` when `env="dev"` or `env=""`.
   - Verify log levels: in `prod`, DEBUG logs are suppressed while INFO logs are written; in `dev`, DEBUG logs are written.
   - Verify `LOG_LEVEL` override: `env="prod", level="DEBUG"` outputs DEBUG logs; `env="dev", level="WARN"` suppresses INFO logs.
   - Verify output format: `prod` generates valid JSON lines (`json.Valid`), `dev` generates text lines (`key=value`).
   - Verify token redaction: assert logs never contain `MARKET_DATA_SERVICE_TOKEN` or its token value.
5. **Update `services/mcp-gateway/main.go` to use `slog`:**
   - Remove `"log"` import and replace with `"log/slog"`.
   - After `loadConfig`, call `initLogger(cfg)`. On config/logger error, log via `slog.Error` and call `os.Exit(1)`.
   - On backend client initialization error, replace `log.Fatalf` with `slog.Error` and `os.Exit(1)`.
   - On startup (before `server.ListenAndServe`), log `slog.Info("mcp-gateway listening", slog.String("service", "mcp-gateway"), slog.String("port", cfg.Port), slog.String("backend_url", cfg.BackendBaseURL), slog.String("environment", cfg.Environment))`.
   - In signal shutdown handler, log `slog.Info("mcp-gateway shutting down", slog.String("service", "mcp-gateway"), slog.String("port", cfg.Port), slog.String("backend_url", cfg.BackendBaseURL), slog.String("environment", cfg.Environment))` and replace shutdown error/timeout `log.` calls with `slog.Error`.
   - On graceful shutdown completion, replace `log.Println("mcp-gateway stopped")` with `slog.Info("mcp-gateway stopped", slog.String("service", "mcp-gateway"), slog.String("port", cfg.Port), slog.String("backend_url", cfg.BackendBaseURL), slog.String("environment", cfg.Environment))`.
   - Ensure `MARKET_DATA_SERVICE_TOKEN` is never passed to any log statement.
6. **Update Docker Compose files:**
   - In `docker-compose.yml`, add `ENVIRONMENT: "${ENVIRONMENT:-dev}"` to `services.mcp-gateway.environment`.
   - In `docker-compose.prod.yml`, add `ENVIRONMENT: "${ENVIRONMENT:-prod}"` to `services.mcp-gateway.environment`.
7. **Update documentation in `services/mcp-gateway/README.md`:**
   - Add `ENVIRONMENT` and `LOG_LEVEL` rows to the Configuration table.
   - Document behavior: `prod` enables JSON handler at `INFO` level; `dev` (default) enables Text handler at `DEBUG` level; `LOG_LEVEL` overrides the default.
8. **Run verification and tests:**
   - Run `go vet ./...` and `go test -v ./...` in `services/mcp-gateway/`.
   - Verify all tests pass, formatting adheres to conventions, and no provider names or tokens are emitted.

**Verification:**
- **AC 1 (Handler selection & default levels):** Run `go test -v -run TestLogger_HandlerSelection ./...` in `services/mcp-gateway` to verify JSON handler at INFO level for `ENVIRONMENT=prod` and text handler at DEBUG level for `ENVIRONMENT=dev` or unset.
- **AC 2 (LOG_LEVEL override):** Run `go test -v -run TestLogger_LogLevelOverride ./...` in `services/mcp-gateway` to verify that `LOG_LEVEL=DEBUG` in prod enables debug logs and `LOG_LEVEL=WARN` in dev suppresses debug/info logs.
- **AC 3 (Structured startup/shutdown & token redaction):** Run `go test -v -run TestLogger_TokenRedaction ./...` and inspect `services/mcp-gateway/main.go` to ensure startup and shutdown log `service`, `port`, `backend_url`, and `environment`, and verify `MARKET_DATA_SERVICE_TOKEN` never appears.
- **AC 4 (docker-compose.yml):** Run `git diff docker-compose.yml` to confirm `ENVIRONMENT: "${ENVIRONMENT:-dev}"` is present under `mcp-gateway.environment`.
- **AC 5 (docker-compose.prod.yml):** Run `git diff docker-compose.prod.yml` to confirm `ENVIRONMENT: "${ENVIRONMENT:-prod}"` is present under `mcp-gateway.environment`.
- **AC 6 (Unit test coverage):** Run `go test -v ./...` in `services/mcp-gateway` to verify test coverage across `ENVIRONMENT` and `LOG_LEVEL` permutations in `config_test.go` and `logger_test.go`.
- **AC 7 (Build and vet):** Run `go vet ./...` and `go build ./...` in `services/mcp-gateway` to ensure clean compilation with no warnings or errors.

**Risks / watch-outs:**
- Standard library `log` calls: ensure all `log.Fatalf`, `log.Printf`, and `log.Println` calls in `main.go` are completely removed so the `log` package is no longer imported or used.
- `MARKET_DATA_SERVICE_TOKEN` security: verify `cfg.ServiceToken` is never passed into any `slog` attribute or message during startup, runtime, or shutdown.
- Upstream provider naming: all log messages and documentation must adhere to the provider-name rule, using generic "market data" vocabulary and avoiding provider brands.
