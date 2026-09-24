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

A missing or unusable required value is a startup error. The token value is
never logged and never appears in an error message.

## Backend data plane

Every request is sent to `BACKEND_BASE_URL + /api/v1/market/data/...` with the
`X-Service-Token` header and `Accept: application/json`. The route paths and
query parameter names are a stable contract defined in
`src/market/data_router.py`; do not rename them.

| Client method  | Backend route                                              | Query                                            |
| -------------- | ---------------------------------------------------------- | ------------------------------------------------ |
| `Prices`       | `GET /prices/{symbol}`                                     | `from`, `to`, `exchange`                         |
| `SymbolSearch` | `GET /symbols/search`                                      | `q`                                              |
| `OptionsChain` | `GET /options/{symbol}`                                    | `expiry`, `option_type`, `strike_min`, `strike_max` |
| `Fundamentals` | `GET /fundamentals/{symbol}`                               | `exchange`                                       |
| `Statements`   | `GET /fundamentals/{symbol}/statements`                    | `statement`, `period`, `limit`, `exchange`       |

### Error taxonomy

The client normalizes every failure into one of three classes (`errors.Is`):

- **`ErrNoData`** — HTTP 404/422. There is no data for this request *right
  now*. A 404 may be a cached empty result within the cache TTL, so it is
  **not** "invalid symbol".
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

| Tool                       | Inputs                                                          | Backend route                               | Returns                                   |
| -------------------------- | --------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------- |
| `get_price_history`        | `symbol`, `from`, `to`, `exchange?`                             | `GET /prices/{symbol}`                      | Daily OHLC history                        |
| `get_fundamentals`         | `symbol`, `exchange?`                                           | `GET /fundamentals/{symbol}`                | Profile + key metrics + ratios aggregate  |
| `get_options_chain`        | `symbol`, `expiry?`, `option_type?`, `strike_min?`, `strike_max?` | `GET /options/{symbol}`                     | Options chain                             |
| `get_income_statement`     | `symbol`, `period?`, `limit?`, `exchange?`                      | `GET /fundamentals/{symbol}/statements`     | Income statements                         |
| `get_balance_sheet`        | `symbol`, `period?`, `limit?`, `exchange?`                      | `GET /fundamentals/{symbol}/statements`     | Balance sheets                            |
| `get_cash_flow_statement`  | `symbol`, `period?`, `limit?`, `exchange?`                      | `GET /fundamentals/{symbol}/statements`     | Cash-flow statements                      |
| `get_key_metrics`          | `symbol`, `exchange?`                                           | `GET /fundamentals/{symbol}`                | Key-metrics projection of the aggregate   |
| `get_financial_ratios`     | `symbol`, `exchange?`                                           | `GET /fundamentals/{symbol}`                | Ratios projection of the aggregate        |
| `get_company_details`      | `symbol`, `exchange?`                                           | `GET /fundamentals/{symbol}`                | Profile projection of the aggregate       |
| `search_symbols`           | `q`                                                             | `GET /symbols/search`                       | Symbol lookup results                     |

Inputs are validated or clamped in the handler before any backend call, so a bad
argument never becomes a backend `422` (which the client classifies as
`ErrNoData` and would otherwise be misreported as "no data"):

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
