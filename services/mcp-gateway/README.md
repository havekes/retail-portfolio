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

## Configuration

| Variable                    | Required | Default | Description                                                       |
| --------------------------- | -------- | ------- | ----------------------------------------------------------------- |
| `BACKEND_BASE_URL`          | yes      | —       | Backend origin, e.g. `http://backend:8000`.                       |
| `MARKET_DATA_SERVICE_TOKEN` | yes      | —       | Shared secret sent as `X-Service-Token` to the data plane.        |
| `PORT`                      | no       | `8080`  | HTTP listen port.                                                 |
| `ENVIRONMENT`               | no       | `dev`   | Deployment environment (`prod` or `dev`). Configures logging handler and default level. |
| `LOG_LEVEL`                 | no       | —       | Log level override (`DEBUG`, `INFO`, `WARN`/`WARNING`, `ERROR`).  |
| `MAX_CONCURRENCY`           | no       | `10`    | Maximum concurrent outbound requests to the backend data plane. Must be a positive integer. |

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

MCP tool calls in `tools.go` are instrumented:
- In `ENVIRONMENT=dev`: tool invocations are logged at `DEBUG` level with `tool` and `arguments`. Tool completions are logged at `DEBUG` level with `tool`, `duration`, and `response` payload content.
- Tool execution errors (validation failures, 422 backend parameter errors, 401 configuration issues, 500 provider errors) are logged at `ERROR` level with `tool`, `arguments`, `error_class`, `status`, and diagnostic `detail` (from Go-side `backendError.Detail()`).
- Diagnostic `detail` is retained only for Go-side logging and is never exposed in user-facing tool error results.
- `ErrNoData` (404) is classified as a normal outcome and does not emit `ERROR` logs.

### Outbound backend client logging / Backpressure

Outbound HTTP calls to the backend data plane in `backendclient.go` are instrumented:
- In `ENVIRONMENT=dev`: outbound requests (`method`, `url`, `query`) and responses (`method`, `url`, `status`, `duration`) are logged at `DEBUG` level.
- Non-2xx responses and transport/network errors are logged at `ERROR` level with `status`, `detail`, and endpoint `url`.
- Outbound backend calls exceeding `MAX_CONCURRENCY` queue behind the semaphore and emit a `WARN` log record (`"backend concurrency limit reached, queuing call"`).
- `MARKET_DATA_SERVICE_TOKEN` and the `X-Service-Token` header value are never logged.

## Backend data plane

Every request is sent to `BACKEND_BASE_URL + /api/v1/market/data/...` with the
`X-Service-Token` header and `Accept: application/json`. The route paths and
query parameter names are a stable contract defined in
`src/market/data_router.py` and published as an OpenAPI contract snapshot artifact at
[`tests/market/contracts/data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json).
The artifact is the committed source of truth; parity is verified by both
backend contract tests (`tests/market/test_data_plane_contract.py`) and Go
client tests (`services/mcp-gateway/contract_test.go`). Do not rename or alter
routes and query parameters without updating the contract snapshot.

| Client method  | Backend route                                                   | Query                                               | Contract snapshot                                                                 |
| -------------- | --------------------------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------- |
| `Prices`       | `GET /api/v1/market/data/prices/{symbol}`                       | `from`, `to`, `exchange`                            | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `SymbolSearch` | `GET /api/v1/market/data/symbols/search`                        | `q`                                                 | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `OptionsChain` | `GET /api/v1/market/data/options/{symbol}`                      | `expiry`, `option_type`, `strike_min`, `strike_max` | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `Fundamentals` | `GET /api/v1/market/data/fundamentals/{symbol}`                 | `exchange`                                          | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |
| `Statements`   | `GET /api/v1/market/data/fundamentals/{symbol}/statements`      | `statement`, `period`, `limit`, `exchange`          | [`data_plane_openapi.json`](../../tests/market/contracts/data_plane_openapi.json) |

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

Tools are registered by a single `tools.go::registerTools(*mcp.Server,
*BackendClient)` function using the SDK's generic `mcp.AddTool` with typed input
structs (the SDK infers and validates the input schema). `newMCPServer` (in
`mcpserver.go`) accepts the `*BackendClient` so the tool handlers can close over
it. Every tool name, description and result string is provider-agnostic.

| Tool                       | Inputs                                                          | Backend route                                                   | Returns                                   |
| -------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- | ----------------------------------------- |
| `get_price_history`        | `symbol`, `from`, `to`, `exchange?`                             | `GET /api/v1/market/data/prices/{symbol}`                       | Daily OHLC history                        |
| `get_fundamentals`         | `symbol`, `exchange?`                                           | `GET /api/v1/market/data/fundamentals/{symbol}`                 | Profile + key metrics + ratios aggregate  |
| `get_options_chain`        | `symbol`, `expiry?`, `option_type?`, `strike_min?`, `strike_max?` | `GET /api/v1/market/data/options/{symbol}`                      | Options chain                             |
| `get_income_statement`     | `symbol`, `period?`, `limit?`, `exchange?`                      | `GET /api/v1/market/data/fundamentals/{symbol}/statements`      | Income statements                         |
| `get_balance_sheet`        | `symbol`, `period?`, `limit?`, `exchange?`                      | `GET /api/v1/market/data/fundamentals/{symbol}/statements`      | Balance sheets                            |
| `get_cash_flow_statement`  | `symbol`, `period?`, `limit?`, `exchange?`                      | `GET /api/v1/market/data/fundamentals/{symbol}/statements`      | Cash-flow statements                      |
| `get_key_metrics`          | `symbol`, `exchange?`                                           | `GET /api/v1/market/data/fundamentals/{symbol}`                 | Key-metrics projection of the aggregate   |
| `get_financial_ratios`     | `symbol`, `exchange?`                                           | `GET /api/v1/market/data/fundamentals/{symbol}`                 | Ratios projection of the aggregate        |
| `get_company_details`      | `symbol`, `exchange?`                                           | `GET /api/v1/market/data/fundamentals/{symbol}`                 | Profile projection of the aggregate       |
| `search_symbols`           | `q`                                                             | `GET /api/v1/market/data/symbols/search`                        | Symbol lookup results                     |

Inputs are validated or clamped in the handler before any backend call, so most
bad arguments never reach the backend. A backend `422` that still occurs is
classified as `ErrValidation` — not `ErrNoData` — so it is reported as an
actionable error rather than "no data":

- `symbol` is trimmed, required, and at most 32 characters.
- `get_price_history` requires `from <= to`; both parse as `YYYY-MM-DD`.
- `get_options_chain` accepts `option_type` of `call` or `put`, parses `expiry`
  as `YYYY-MM-DD`, and requires `strike_min <= strike_max`.
- statement tools accept `period` of `annual` (default) or `quarter`; `limit` is
  clamped to 1–20 with a default of 5.
- `search_symbols` requires a trimmed query of 1–100 characters.

### Tool result contract

- Success: a single `mcp.TextContent` holding the JSON-encoded payload.
- **`ErrNoData` is a successful result** whose text is `No market data is
  available for this request.` A 404 may be a cached empty result within the
  cache TTL, so it is never phrased as "invalid symbol".
- `ErrValidation` becomes `result.SetError(err)` carrying the backend's parsed
  validation message (or the generic sentinel text when the body is
  unparsable).
- `ErrConfiguration` / `ErrProvider` become `result.SetError(err)` carrying the
  client's generic sentinel text. Backend status/body detail, the service token,
  and any provider name never reach the tool result.

## Development

```sh
go mod tidy
go vet ./...
go build ./...
go test ./...
```

Build the image from this directory:

```sh
docker build -t mcp-gateway .
```
