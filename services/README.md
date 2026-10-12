# Go Service Conventions

This document specifies repository-wide conventions for Go microservices in `services/`.
These conventions were piloted in `indicator-service` (ARCH-T35) and apply across all Go services (with `mcp-gateway` aligning via ARCH-T37/ARCH-T38).

## 1. Directory Layout

Each microservice is an independent Go module with a `cmd/` + `internal/` layout:

```text
services/<service>/
  cmd/<service>/
    main.go             # Entrypoint: configuration, logger init, router setup, lifecycle/graceful shutdown
  internal/
    config/             # Config struct, Load(getenv)
    logging/            # slog configuration and log-level parsing
    httpapi/            # HTTP handlers, router, middleware, wire DTOs
    <domain>/           # Domain logic (e.g. indicators calculation) — no net/http dependencies
  Dockerfile
  go.mod
  go.sum
  README.md
```

- **`cmd/<service>/`**: Houses the `main` package containing entrypoint wiring only.
- **`internal/`**: Enforces Go's internal package visibility rules; no external module can import internal packages.
- **Independent modules**: Each service maintains its own `go.mod` and dependency tree.

## 2. Configuration via `Load(getenv)`

Configuration is parsed using an injected `getenv` function (`func(string) string`):

```go
type Config struct {
    Port        string
    Environment string
    LogLevel    string
    // ... service-specific configuration
}

func Load(getenv func(string) string) (Config, error) {
    // Reads and validates environment variables
}
```

- Injecting `getenv` allows comprehensive unit tests without modifying the process environment (`os.Setenv`).
- In `cmd/<service>/main.go`, `config.Load(os.Getenv)` is invoked at startup.
- **Fail-fast validation**: Missing required values or invalid formats (such as invalid `LOG_LEVEL` or non-numeric port) return an error naming the offending variable (e.g. `invalid LOG_LEVEL "nope"`).

## 3. Structured Logging (`slog`)

Logging uses the standard library `log/slog`:

- **Production (`ENVIRONMENT=prod`)**: JSON handler with default level `INFO`.
- **Development (`ENVIRONMENT=dev` or unset)**: Human-readable text handler with default level `DEBUG`.
- **`LOG_LEVEL` override**: Explicitly setting `LOG_LEVEL` (`DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`) overrides the environment default.
- Invalid `LOG_LEVEL` values cause configuration loading to return an error naming `LOG_LEVEL`.

## 4. HTTP Access Logging & Status Levels

All incoming HTTP requests pass through logging middleware that tracks duration, status code, client remote address, and request ID.

Access-log records use severity levels determined by HTTP response status:
- `2xx` / `3xx` (Success & Redirection): Logged at `INFO`.
- `4xx` (Client Errors): Logged at `WARN`.
- `5xx` (Server Errors): Logged at `ERROR`.

When `DEBUG` logging is enabled, requests may emit diagnostic payloads (e.g. body dumps) at `DEBUG` level.

## 5. `X-Request-ID` Convention

Every HTTP request carries a correlation ID:
- If the incoming request has an `X-Request-ID` header, that value is propagated.
- If absent, an RFC 4122 version 4 UUID is generated.
- The ID is attached to the outgoing response header (`X-Request-ID`).
- The ID is stored in the `context.Context` alongside a logger pre-populated with `request_id`. Handlers retrieve the scoped logger via context helper functions.

*Note*: Adopted in `indicator-service`; `mcp-gateway` adopts request IDs as part of ARCH-T37 / #586 (OpenTelemetry tracing).

## 6. Server Lifecycle & Graceful Shutdown

HTTP servers handle process termination signals (`SIGINT`, `SIGTERM`) gracefully:
- Listen for OS interrupt signals on a dedicated signal channel.
- Upon receiving a termination signal, trigger `server.Shutdown(ctx)` with a bounded timeout (typically 10 seconds).
- Log a warning if the shutdown deadline expires before connections drain.
- Exit with code 0 on clean shutdown; log fatal errors and exit non-zero if startup fails.

## 7. Docker Build Target

Dockerfiles use multi-stage builds (`golang:<version>-alpine` builder to minimal `alpine:<version>` runtime):
- The Go build command must target `./cmd/<svc>`:
  ```dockerfile
  RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o <svc> ./cmd/<svc>
  ```
- Binaries run as an unprivileged application user (`appuser`).
- Container exposes health checks via `GET /health`.

## 8. Why No Shared Module

A shared Go module across microservices was evaluated and rejected (Finding 8, Architecture Review):
- Microservices in this repository have distinct lifecycles and minimal code overlap.
- Shared internal modules create versioning lockstep, cross-service coupling, and build complexity.
- Maintaining independent modules preserves isolated dependencies and rapid individual iteration. Conventions are shared through documentation rather than coupled code dependencies.
