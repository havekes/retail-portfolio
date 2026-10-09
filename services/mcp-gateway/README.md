# MCP Gateway

A Go sidecar that exposes the backend's provider-agnostic market data as an
[MCP](https://modelcontextprotocol.io) server over the **streamable HTTP**
transport. An AI agent connects to `/mcp` and calls generic market-data tools;
it never learns which upstream provider serves the data.

The service is a thin transport and client layer only. It holds no provider
credentials, calls no provider directly, and talks exclusively to the backend's
service-to-service data plane.

## Endpoints

### `GET /health`

Liveness probe. Returns `200` with `{"status":"ok"}`. It does not depend on
backend reachability.

Any other method returns `405` with `Allow: GET`.

### `POST|GET /mcp`

The MCP streamable HTTP endpoint. It is **unauthenticated**: the shared-secret
trust boundary is the backend data plane, not the MCP listener. Run it on the
internal network only.

Browser cross-origin requests are rejected via Go standard library
`http.NewCrossOriginProtection`: requests carrying `Sec-Fetch-Site: cross-site`
or a mismatched `Origin` header receive `403 Forbidden`. Non-browser MCP
agents without those headers connect normally. Idle sessions are closed after
`SESSION_IDLE_TIMEOUT`.

## Configuration

| Variable                    | Required | Default | Description                                                       |
| --------------------------- | -------- | ------- | ----------------------------------------------------------------- |
| `BACKEND_BASE_URL`          | yes      | —       | Backend origin, e.g. `http://backend:8000`.                       |
| `MARKET_DATA_SERVICE_TOKEN` | yes      | —       | Shared secret sent as `X-Service-Token` to the data plane.        |
| `PORT`                      | no       | `8080`  | HTTP listen port.                                                 |
| `ENVIRONMENT`               | no       | `dev`   | Deployment environment (`prod` or `dev`). Configures logging handler and default level. |
| `LOG_LEVEL`                 | no       | —       | Log level override (`DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`).  |
| `MAX_CONCURRENCY`           | no       | `10`    | Maximum concurrent outbound requests to the backend data plane. Must be a positive integer. |
| `SESSION_IDLE_TIMEOUT`      | no       | `30m`   | Idle timeout after which inactive MCP sessions are closed. Must be a positive Go duration string (e.g. `5m`, `1h`). |

A missing or unusable required value is a startup error. The token value is
never logged and never appears in an error message.

Structured logging uses Go standard library `log/slog`. When `ENVIRONMENT=prod`,
logging emits JSON lines via `slog.NewJSONHandler` with a default level of `INFO`.
When `ENVIRONMENT=dev` (or unset), logging emits human-readable text via
`slog.NewTextHandler` with a default level of `DEBUG`. Setting `LOG_LEVEL`
overrides the default log level for the active handler.

### HTTP request logging middleware

All inbound HTTP requests to `/health` and `/mcp` pass through structured logging middleware:
- Every request completion is logged at `INFO` level with `method`, `path`, `remote_addr`, `status`, and `duration`.
- In `ENVIRONMENT=dev`, incoming request details are logged at `DEBUG` level with `method`, `path`, `headers`, `query`, and request `body` (bounded up to 64KB).
- Sensitive headers (`Authorization`, `X-Service-Token`, `Cookie`, `Set-Cookie`) are automatically redacted with `"[REDACTED]"` in log output.
- The middleware supports `http.Flusher` pass-through so real-time MCP streaming SSE responses are flushed immediately.

### Tool execution logging

MCP tool calls in `internal/tools/registry.go` are instrumented:
- Debug logging follows the logger level alone: tool invocations are logged at `DEBUG` level with `tool` and `arguments`, and tool completions are logged at `DEBUG` level with `tool`, `duration`, and `response` payload content. With `LOG_LEVEL=DEBUG` (including in `ENVIRONMENT=prod`), tool invocation and completion debug records appear. In `ENVIRONMENT=prod` with default `LOG_LEVEL=INFO`, they are suppressed.
- Tool execution errors (validation failures, 422 backend parameter errors, 401 configuration issues, 500 provider errors) are logged at `ERROR` level with `tool`, `arguments`, `error_class`, `status`, and diagnostic `detail` (from Go-side `backend.Error.Detail()`).
- Diagnostic `detail` is retained only for Go-side logging and is never exposed in user-facing tool error results.
- `ErrNoData` (404) is classified as a normal outcome and does not emit `ERROR` logs.

### Outbound backend transport logging / Backpressure

Outbound HTTP calls to backend data planes in `internal/backend/transport.go` are instrumented:
- Outbound requests (`method`, `url`, `query`) and responses (`method`, `url`, `status`, `duration`) are logged at `DEBUG` level. Gated by the logger level alone: with `LOG_LEVEL=DEBUG` (including in `ENVIRONMENT=prod`), outbound debug lines appear. Both `GET` and `POST` operations are supported and logged.
- Non-2xx responses and transport/network errors are logged at `ERROR` level with `status`, `detail`, and endpoint `url`.
- Outbound backend calls exceeding `MAX_CONCURRENCY` queue behind the shared transport semaphore and emit a `WARN` log record (`"backend concurrency limit reached, queuing call"`).
- `MARKET_DATA_SERVICE_TOKEN` and any domain `X-Service-Token` header values are never logged.

## Generalized transport architecture

All outbound backend communication flows through a centralized `Transport` (`internal/backend/transport.go`) that manages:
- HTTP client lifecycle, timeouts (`15s`), and headers (`Accept: application/json`).
- Outbound concurrency bounding across all route groups via a semaphore channel sized by `MAX_CONCURRENCY`.
- Method-agnostic execution (`Get` and `Post` wrapping `Do`) with automatic JSON request body serialization and JSON response decoding.
- Response size limiting (`8 MiB` max buffered) and error detail truncation (`512` characters).
- Standardized error classification (`ErrNoData`, `ErrValidation`, `ErrConfiguration`, `ErrProvider`).
- Development and production logging with automatic token redaction.

On top of the shared `Transport`, domains isolate their path prefix and service authentication token using `RouteGroup` instances via `transport.NewRouteGroup(prefix, token)`.

## Backend data plane

Every request is sent to `BACKEND_BASE_URL + /api/v1/market/data/...` with the
`X-Service-Token` header and `Accept: application/json`. The route paths and
query parameter names are a stable contract defined in
`src/market/data_router.py` and published as an OpenAPI contract snapshot artifact at
[`tests/market/contracts/data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json).
The artifact is the committed source of truth; parity is verified by both
backend contract tests (`tests/market/test_data_plane_contract.py`) and Go
client tests (`services/mcp-gateway/internal/backend/contract_test.go`). Do not rename or alter
routes and query parameters without updating the contract snapshot.

| Client method  | Backend route                                                   | Query                                               | Contract snapshot                                                                 |
| -------------- | --------------------------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------- |
| `Prices`       | `GET /api/v1/market/data/prices/{symbol}`                       | `from`, `to`, `exchange`                            | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `SymbolSearch` | `GET /api/v1/market/data/symbols/search`                        | `q`                                                 | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `OptionsChain`      | `GET /api/v1/market/data/options/{symbol}`                      | `expiry`, `option_type`, `strike_min`, `strike_max` | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `OptionExpirations` | `GET /api/v1/market/data/options/{symbol}/expirations`          |                                                     | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `Fundamentals`      | `GET /api/v1/market/data/fundamentals/{symbol}`                 | `exchange`                                          | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `Statements`        | `GET /api/v1/market/data/fundamentals/{symbol}/statements`      | `statement`, `period`, `limit`, `exchange`          | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |

### Error taxonomy

The client normalizes every failure into one of four classes (`errors.Is`):

- **`ErrNoData`** — HTTP 404. There is no data for this request *right
  now*. A 404 may be a cached empty result within the cache TTL, so it is
  **not** "invalid symbol".
- **`ErrValidation`** — HTTP 422. The request's parameters failed backend
  validation. A parsed, agent-safe validation message is forwarded so the caller
  can retry with corrected parameters (unlike `ErrNoData`).
- **`ErrConfiguration`** — HTTP 401/403. The service token was rejected; this
  is an operator problem.
- **`ErrProvider`** — HTTP 5xx, unexpected statuses, non-JSON bodies, timeouts,
  and connection failures.

The sentinel messages are generic on purpose. Diagnostic detail (status and a
truncated body) is retained on the error for Go-side logging only and is
excluded from `Error()`, so forwarding `err.Error()` to an agent cannot leak
internals.

## Provider-name rule

Tool names, descriptions, log lines, error strings, and this README must never
mention an upstream provider brand. Keep the vocabulary provider-agnostic
("market data"). This applies to the whole module, including test files.

## Tools

Tools are registered by `tools.Register(*mcp.Server, *backend.MarketClient)` (in
`internal/tools/registry.go`) using `addTool` with typed input structs (the SDK
infers and validates the input schema from struct fields and `jsonschema` tags).
`server.New` (in `internal/server/server.go`) accepts the `*backend.MarketClient` so the tool
handlers can close over it. Every tool name, description and result string is
provider-agnostic.

| Tool                       | Inputs                                                                                                   | Backend route                                               | Returns                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------ |
| `resolve_symbol`           | `query`, `exchange?`                                                                                     | `GET /api/v1/market/data/symbols/search`                    | Best matching symbol and alternatives            |
| `get_quote`                | `symbol`, `exchange?`                                                                                    | `GET /api/v1/market/data/quote/{symbol}`                    | Live quote snapshot                              |
| `get_price_history`        | `symbol`, `from?`, `to?`, `interval?`, `exchange?`                                                       | `GET /api/v1/market/data/prices/{symbol}`                   | Daily, weekly, or monthly OHLC history           |
| `get_fundamentals`         | `symbol`, `sections?`, `exchange?`                                                                       | `GET /api/v1/market/data/fundamentals/{symbol}`             | Profile + key metrics + ratios aggregate         |
| `get_financial_statements` | `symbol`, `statement`, `period?`, `limit?`, `exchange?`                                                  | `GET /api/v1/market/data/fundamentals/{symbol}/statements`  | Financial statements (income, balance, cashflow) |
| `get_option_expirations`   | `symbol`                                                                                                 | `GET /api/v1/market/data/options/{symbol}/expirations`      | Option expiration dates                          |
| `get_options_chain`        | `symbol`, `expiry`, `option_type?`, `strike_min?`, `strike_max?`                                         | `GET /api/v1/market/data/options/{symbol}`                  | Options chain                                    |
| `get_technical_indicator`  | `symbol`, `indicator`, `period?`, `fast?`, `slow?`, `signal?`, `std_dev?`, `from?`, `to?`, `exchange?`    | `GET /api/v1/market/data/indicators/{symbol}`               | Technical indicator series                       |

Inputs are validated or clamped in the handler before any backend call, so most
bad arguments never reach the backend. A backend `422` that still occurs is
classified as `ErrValidation` — not `ErrNoData` — so it is reported as an
actionable error rather than "no data":

- `symbol` is required, at most 32 characters, and must match `^\^?[A-Za-z0-9][A-Za-z0-9.\-=]{0,30}$` (alphanumeric ticker with optional leading `^` and internal `.`, `-`, `=`).
- `resolve_symbol` requires a trimmed query of 1–100 characters and optional supported exchange (NYSE, NASDAQ, NYSEARCA, AMEX, TSX, LSE). Use this first before calling price or fundamentals tools.
- `get_quote` requires a symbol and optional supported exchange; returns timestamp and price in listing currency.
- `get_price_history` requires `from <= to`; accepts optional `interval` (`day`, `week`, `month`) and caps results at 2,000 bars.
- `get_fundamentals` accepts optional `sections` subset of `profile`, `key_metrics`, `ratios` (default all).
- `get_financial_statements` requires `statement` (`income`, `balance`, or
  `cashflow`), accepts `period` of `annual` (default) or `quarter`, and clamps
  `limit` to 1–20 with a default of 5.
- `get_option_expirations` requires an underlying symbol.
- `get_options_chain` requires `expiry` (`YYYY-MM-DD`; use `get_option_expirations` to
  discover valid dates), accepts `option_type` of `call` or `put`, and requires
  `strike_min <= strike_max`.
- `get_technical_indicator` requires `indicator` (`sma`, `ema`, `rsi`, `macd`, or `bollinger`),
  clamps optional periods (`period`, `fast`, `slow`, `signal`) to 2–400, requires `std_dev > 0`,
  and requires `from <= to` when provided.

### Tool descriptions and annotations

Every tool is registered with `toolSpec{Name, Title, Description}` via `addTool`:
- **Annotations**: always sets `ReadOnlyHint: true`, `IdempotentHint: true`, and `Title: <title>` so MCP clients identify tools as safe, idempotent, and titled.
- **Descriptions**: follow a structured 4-part convention:
  - **`Use when:`** — guidance on when an agent should invoke the tool, default behavior, and constraints (e.g. "USE THIS FIRST" for `resolve_symbol`, 2,000-bar cap for `get_price_history`).
  - **`Examples:`** — at least two plain-language queries mapped to parameter JSON (`"..." -> {...}`) using supported exchanges.
  - **`Returns:`** — top-level response keys, noting decimal strings in the response's `currency` field, quote `timestamp`, or `truncated` semantics.
  - **`See also:`** — related registered tools.

### Tool result contract

- Success: a single `mcp.TextContent` holding the JSON-encoded payload.
  Backend responses are passed through directly as raw JSON: `get_financial_statements`
  validates `date`/`symbol` headers and passes statement items through untouched,
  while `get_fundamentals` filters requested sections verbatim, preserving
  unknown fields and exact numeric representations.
- **`ErrNoData` is a successful result** whose text is `No market data is
  available for this request.` A 404 may be a cached empty result within the
  cache TTL, so it is never phrased as "invalid symbol".
- `ErrValidation` becomes `result.SetError(err)` carrying the backend's parsed
  validation message (or the generic sentinel text when the body is
  unparsable).
- `ErrConfiguration` / `ErrProvider` become `result.SetError(err)` carrying the
  client's generic sentinel text. Backend status/body detail, the service token,
  and any provider name never reach the tool result.

## Adding a new tool domain

Adding a second data plane or domain (for example, portfolios, watchlists, or orders) follows a clean 3-step workflow using the generalized transport without modifying existing client methods:

1. **Configure route group and token**:
   Define domain-specific service tokens and prefix configurations in `internal/config/config.go` (e.g. `PORTFOLIO_SERVICE_TOKEN`). When initializing the service, create a new `RouteGroup` from the shared `Transport`:
   ```go
   portfolioGroup := transport.NewRouteGroup("/api/v1/portfolio", cfg.PortfolioServiceToken)
   ```

2. **Create domain client**:
   Create a dedicated domain client file in `internal/backend/<domain>.go` (e.g. `internal/backend/portfolio.go`) wrapping `*RouteGroup`. Implement typed domain methods calling `group.Get` or `group.Post`:
   ```go
   package backend

   type PortfolioClient struct {
       group *RouteGroup
   }

   func NewPortfolioClient(transport *Transport, token string) *PortfolioClient {
       return &PortfolioClient{
           group: transport.NewRouteGroup("/api/v1/portfolio", token),
       }
   }

   func (c *PortfolioClient) CreatePosition(ctx context.Context, req CreatePositionRequest) (json.RawMessage, error) {
       var out json.RawMessage
       if err := c.group.Post(ctx, "/positions", nil, req, &out); err != nil {
           return nil, err
       }
       return out, nil
   }
   ```

3. **Register MCP tools**:
   Define typed tool inputs and register tools in a dedicated per-family file in `internal/tools/<domain>.go` (e.g. `internal/tools/portfolio.go`) with a `register<Family>Tools` registration function (e.g. `registerPortfolioTools`) closing over the domain client using `toolSpec`, and call it from `tools.Register` in `internal/tools/registry.go`:
   ```go
   const descCreatePosition = `Create a new position in the portfolio.

   Use when:
   Adding a newly executed trade to the portfolio holdings.

   Examples:
   - "Add 10 shares of Apple at $150" -> {"symbol": "AAPL", "quantity": 10, "price": "150.00"}
   - "Buy 5 shares of Microsoft" -> {"symbol": "MSFT", "quantity": 5}

   Returns:
   Top-level fields:
   - position_id: identifier of the created position.
   - symbol: ticker symbol.
   - quantity: position size.

   See also:
   get_quote, resolve_symbol`

   func registerPortfolioTools(server *mcp.Server, portfolioClient *PortfolioClient, cfg Config) {
       addTool(server, toolSpec{
           Name:        "create_position",
           Title:       "Create Position",
           Description: descCreatePosition,
       }, func(ctx context.Context, _ *mcp.CallToolRequest, in createPositionInput) (*mcp.CallToolResult, any, error) {
           return runTool(ctx, "create_position", cfg, in, createPositionInput.prepare, func(ctx context.Context, r createPositionRequest) (any, error) {
               return portfolioClient.CreatePosition(ctx, r)
           })
       })
   }
   ```

## Running with Docker Compose

From the repository root:

```bash
docker compose up mcp-gateway
```

- Dev compose (`docker-compose.yml`): published on
  `127.0.0.1:${MCP_GATEWAY_PORT:-8005}` on the host, mapped to container port
  `8080`. Override with `MCP_GATEWAY_PORT=9090 docker compose up mcp-gateway`.
- Prod compose (`docker-compose.prod.yml`): internal network only, no host port
  published, container name `retail-portfolio-mcp-gateway`, `restart: always`.
- Both compose files healthcheck `GET /health` via `wget` every 30s
  (timeout 5s, 3 retries, 5s start period).

## Development

```sh
go mod tidy
go vet ./...
go build ./cmd/mcp-gateway
go run ./cmd/mcp-gateway
go test ./...
```

Build the image from this directory:

```sh
docker build -t mcp-gateway .
```
