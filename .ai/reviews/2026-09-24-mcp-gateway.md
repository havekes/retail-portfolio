---
date: 2026-09-24
verdict: sound-with-concerns
focus: mcp-gateway scalability (adding tools, different upstream APIs) — services/mcp-gateway + src/market data plane
---

# Architecture Review 2026-09-24 — mcp-gateway

## Summary

The mcp-gateway is a well-built boundary: provider-agnostic vocabulary is enforced end-to-end (including `TestTools_ProviderNameCompliance` / `TestBackendClient_ProviderNameCompliance`), the four-class error taxonomy in `backendclient.go` maps cleanly onto MCP results, input validation is clamped in the handler before any backend call, and the `addTool`/`prepare`/`runTool` pipeline in `tools.go` is a genuinely repeatable template for new tools. The concerns are all about **growth cost**, not current correctness: (1) the Go service hand-mirrors ~330 lines of backend response schemas with a strict `DisallowUnknownFields` decode that turns every backend field addition into a runtime break; (2) the Go↔Python contract (paths, params, limits, date formats) exists only as prose in README/docstrings/mirrored consts with no mechanical parity check; (3) the client funnels everything through one `dataPlanePath`, one `BACKEND_BASE_URL`, one token, and GET-only plumbing — the first non-market-data domain or POST-based tool will force a fork. Verdict: **sound-with-concerns** — none of this blocks the next two or three market-data tools, but items 1–2 bite the moment `src/market/api_types.py` evolves, and item 3 bites at the second data domain.

## Findings

### 1. Go response structs hand-mirror backend schemas; strict decoding makes backend field additions a runtime break [severity: risk]

**Observation:** `backendclient.go:481-817` re-declares `PriceBar`, `CompanyProfile`, `KeyMetrics`, `FinancialRatios`, `IncomeStatement`, `BalanceSheet`, `CashFlowStatement`, `OptionsChain` &c. field-for-field from `src/market/api_types.py` / `src/market/schema.py`. For the three statement tools the decode is strict — `decodeStatementItems` sets `DisallowUnknownFields` (`backendclient.go:810-816`) — so *any* new field added to a backend statement type makes every statement tool return a generic `ErrProvider` ("decoding statement list: unknown field") until the Go structs are updated. Even for the lenient tools, the mirror is mostly dead weight: `successResult` (`tools.go:270-278`) immediately re-marshals the typed struct back to JSON text, so the structs' only load-bearing uses are the three projection tools (`get_key_metrics`/`get_financial_ratios`/`get_company_details`, `tools.go:91-125`) and the statement decode check. That's ~330 lines + the `Decimal` adapter that must be kept in lock-step with Pydantic v2's Decimal-as-JSON-string behaviour by hand.
**Impact:** Every `api_types.py` evolution (new line item, new metric, renamed field) becomes a coordinated two-language change, and the strict-decode path actively fails the statement tools when the two sides drift — a backend-only PR can silently degrade agent tooling. This is the single biggest tax on "adding more tools" today.
**Recommendation:** Shrink the typed surface to what Go actually needs, and cover the rest with a contract artifact. Pass `json.RawMessage` through for pass-through tools (prices, search, options, fundamentals aggregate); keep typed structs only for the projection tools and the statement header-field check (`date`/`symbol` presence), with the unknown-field strictness either dropped or converted into the contract test from finding 2. Ticketed as ARCH-T11 (#596), depends on ARCH-T10 (#595).

### 2. The Go↔Python data-plane contract is prose, not an artifact [severity: risk]

**Observation:** Route paths, query-param names, validation bounds and date formats are a "stable contract" asserted by three independent prose sources: `services/mcp-gateway/README.md` (endpoint table), the docstring of `src/market/data_router.py:15-26`, and mirrored Go consts (`tools.go:33-39` — `maxStatementLimit`, `maxSymbolLength`, query bounds; `backendclient.go:19-23` — `dataPlanePath`, header name). Nothing mechanically checks parity. The Go side has excellent unit tests against fixtures (`backendclient_test.go:261` `TestBackendClientDecodesRealBackendShapes`), and `tests/market/test_data_router.py` covers the Python side, but both fixture sets are hand-written — they test each side against its own assumptions, not against each other.
**Impact:** Contract drift is silent until an agent-visible tool breaks (e.g. a `data_router.py` param rename passes the whole Python suite while the Go client sends dead params). As tool count grows, each new tool widens this unverified surface.
**Recommendation:** Check in the data-plane slice of FastAPI's generated OpenAPI document as an artifact (e.g. `tests/market/contracts/data_plane_openapi.json` or a checked-in `openapi.json` filtered to `/market/data`), and add a Go test (`go test`) that asserts `backendclient.go` paths/params/response field names against that snapshot. Backend CI re-serializes the snapshot so any route change forces a visible artifact diff. Ticketed as ARCH-T10 (#595).

### 3. The client is a single-domain funnel: one prefix, one base URL, one token, GET-only [severity: concern]

**Observation:** `BackendClient` (`backendclient.go:200-239`) is built from exactly one `BACKEND_BASE_URL` (`config.go`), one `MARKET_DATA_SERVICE_TOKEN`, and hardcodes `dataPlanePath = "/api/v1/market/data"` (`backendclient.go:19`) into every URL (`backendclient.go:370`). Transport plumbing is GET-only (`c.get`, `backendclient.go:368`). Cross-cutting config is threaded through variadic `env ...string` parameters in four places (`NewBackendClient`, `registerTools`, `newMCPServer`, `statementHandler`) plus a raw `env string` in `runTool`. The provider-agnostic *backend* side is already prepared for growth — `MarketGateway`'s optional-capability pattern and `CompositeMarketGateway` (`src/market/composite.py`) add providers cheaply — but the gateway side has no pattern for a second data domain (accounts, watchlists, portfolios) or a second upstream service.
**Impact:** The first tool outside `/market/data` — or the first POST-based tool (screening, watchlist writes) — forces either forking a near-duplicate client or overloading the market-data namespace. The four-way `env ...string` threading compounds every time new cross-cutting config (timeouts, auth mode, feature flags) is added.
**Recommendation:** Before the second data domain lands: extract the request/decode/error/logging pipeline from `c.get` into a shared transport core, rename it to a method-agnostic `do`, parameterize the path prefix (and token) per route group, and consolidate the four `env ...string` signatures into one config struct. Also record the "add a new tool domain" recipe in the README. Scope deliberately kept to plumbing only — no new features. Ticketed as ARCH-T13 (#598).

### 4. Fundamentals overview performs three sequential blocking provider reads [severity: debt]

**Observation:** `market_data_fundamentals` (`src/market/data_router.py:308-318`) awaits `get_company_profile`, `get_key_metrics` and `get_financial_ratios` one after another, each through `asyncio.to_thread` against the sync FMP gateway. On cache miss that's three serial upstream round-trips. The projection tools then make it easy for an agent to trigger the full aggregate three times in a row (`get_fundamentals` + `get_key_metrics` + `get_financial_ratios`).
**Impact:** Slowest tool on the data plane for cold symbols; each extra fundamentals-derived tool multiplies cold-cache latency. Not a correctness problem — `EndpointResponseCache` absorbs repeats — but it is the cheapest real scalability win available.
**Recommendation:** Fetch the three reads concurrently with `asyncio.gather` inside `fetch()`. Small backend-only change, no contract impact. Ticketed as ARCH-T12 (#597).

### 5. Observations only (no ticket)

- **Unauthenticated MCP listener is host-published in dev Compose.** The trust model ("shared-secret boundary is the data plane, not the MCP listener", `main.go:137-138`, README) is deliberate and internally consistent, but `docker-compose.yml:125-133` maps `${MCP_GATEWAY_PORT:-8086}` to the host and defaults `MARKET_DATA_SERVICE_TOKEN` to `dev-market-data-token`. Anyone on the dev host's network can reach `/mcp` and ride the token into the data plane. Fine for single-developer dev; must not survive into any shared/staging deployment. Flag before any non-local deploy.
- **Oversized responses degrade to a generic error.** `io.LimitReader(resp.Body, maxResponseBytes)` (`backendclient.go:427`) truncates at 8 MiB, then `json.Unmarshal` fails on the truncated body → generic `ErrProvider`. Acceptable, but a very large options chain will read as "temporarily unavailable" rather than a size signal. Only worth touching if big chains become common.
- **No pagination** on `search_symbols` or `get_price_history`; range-bounded tools are fine, but an agent asking for 10 years of daily prices gets one large JSON blob per call. Observation for a future "chunked range" guidance note in tool descriptions.
- **`serverVersion = "0.0.1"` is static** (`mcpserver.go:14`) and never bumped with the binary; harmless while there's exactly one deployable.

## What went well

- **Provider-name hygiene is tested, not just documented** — `TestTools_ProviderNameCompliance` / `TestBackendClient_ProviderNameCompliance` scan tool names, descriptions and error strings. Worth keeping as a convention for every new tool.
- **Error taxonomy is a genuine contract**: four sentinels with `Unwrap` support, agent-safe `Error()`, diagnostics (`Status()`/`Detail()`) split off for Go-side logs only, and the `ErrNoData`-is-success rule correctly handles the negative-cached-404 semantics the backend's `EndpointResponseCache` produces (`data_router.py:174-185`).
- **Input validation is mirrored in the right place**: `prepare` methods reject/clamp before the backend call, matching `data_router.py`'s `Query` constraints, so most bad agent input never costs a backend round-trip; a residual 422 is still surfaced as an actionable parsed validation message (`validationMessage`, `backendclient.go:131-170`).
- **Per-provider routing stays in the backend**: the Go service never learns FMP/Polygon exist; `CompositeMarketGateway` + optional-capability `MarketGateway` methods (`src/market/gateway.py:83-200`) make adding a provider a local change.
- **Test discipline on the Go side**: ~2,700 test lines vs ~2,400 source lines, covering decode shapes, error classification, secret-leak, and logging behaviour.

## Prior finding disposition

- Prior review (`2026-08-25-architecture.md`) was auth-scoped; none of its findings touched `services/mcp-gateway` or `src/market/data_router.py`. All ARCH-T01–T09 tickets it created are now closed (verified via `gh issue list`), so there are no open ARCH findings to carry over.
- The `T08`/`T09`/`T10`/`T11`/`T13` references in code comments (`data_router.py`, `backendclient.go`, `main.go`) are completed feature tickets, not open findings.
- Open feature ticket F-OBS-T10 (#586, "Wire OTel into mcp-gateway and data-plane calls") is observability scope, not architectural drift; no conflict with the tickets below, but implementers of ARCH-T10–T13 should avoid colliding with its branch.
