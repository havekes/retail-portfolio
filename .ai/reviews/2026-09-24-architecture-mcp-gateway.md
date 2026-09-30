---
date: 2026-09-24
verdict: sound-with-concerns
focus: services/mcp-gateway (scalability: more tools, different APIs)
---

# Architecture Review — mcp-gateway focus (2026-09-24)

## Summary

The mcp-gateway (`services/mcp-gateway/`, Go 1.x sidecar) is a clean thin-transport
layer: unauthenticated MCP streamable-HTTP listener → typed `BackendClient` → backend
service-to-service data plane (`src/market/data_router.py`) with a strict four-class
error taxonomy and a well-documented tool contract. The single most important
observation: **the scaling path for "more tools / different APIs" already exists and
runs through the backend** — new providers compose behind `DataPlaneMarketGateway`
(`src/market/gateway.py:203`), new capabilities appear as data-plane routes, and the
Go sidecar mirrors them. What is missing is a *drift guard*: the Go sidecar
hand-mirrors Python response types and route/query contracts with no CI mechanism to
detect divergence, which is the friction that will compound fastest as tool count
grows.

## Findings

### 1. Data-plane contract is hand-duplicated in Go with no drift guard [severity: risk]
**Observation:** `services/mcp-gateway/backendclient.go` re-declares every
data-plane response type field-for-field (`PriceHistory`, `CompanyFundamentals`,
`OptionsChain`, three statement structs — ~300 lines) mirroring
`src/market/schema.py` and `src/market/api_types.py`, plus the route paths/query
parameter names as string literals in both `dataPlanePath` and per-method URLs. The
README tables duplicate all of it a third time. Nothing in CI compares the two sides:
response-shape drift (a renamed/added Pydantic field) surfaces only at runtime as
`ErrProvider` "malformed response" or as silently-null Go fields — and
`decodeStatementList`'s `DisallowUnknownFields` even turns *additive* backend changes
into hard failures.
**Impact:** Every new tool requires synchronized edits across Python types, Go
structs, and the README, with compile passing on both sides even when they disagree.
The cost per added tool grows linearly and the failure mode is runtime-only.
**Recommendation:** Lock the contract in CI. Originally ticketed as **ARCH-T01**
(#600), now closed as a duplicate of the equivalent **ARCH-T10** (#596) from the
same-day review `2026-09-24-mcp-gateway.md` (its version includes a
regenerate-and-diff artifact test and is the dependency target of ARCH-T11): a
backend-side pytest that asserts the documented data-plane routes + query params
against the FastAPI OpenAPI schema, committed as a versioned `openapi.json` snapshot
that the Go side (and optionally `oapi-codegen`-generated types later) can be
checked against. Blocking future tool/API expansion work.

### 2. Unbounded concurrency between MCP agents and the backend data plane [severity: concern]
**Observation:** `BackendClient.get` (`backendclient.go:368`) has a 15s per-request
timeout but no cap on concurrent in-flight calls; `runTool` executes immediately per
tool call. Every response body is buffered up to `maxResponseBytes` (8 MiB) and
JSON-encoded into a single `TextContent`. The streamable-HTTP transport accepts many
simultaneous sessions, and `/mcp` is unauthenticated, so any container on the network
can open unbounded parallel calls into the backend (which does have
`EndpointResponseCache`, but the gateway itself has no backpressure).
**Impact:** A runaway or multi-agent workload can pin goroutines, buffer many 8 MiB
payloads, and degrade the shared backend — the gateway's `GET /health` never signals
this because it is liveness-only.
**Recommendation:** Ticketed as **ARCH-T02** (#601): a configurable concurrency
semaphore around backend calls (env knob, e.g. `MAX_CONCURRENCY`), plus a
`GET /health` detail or log signal when saturated. Small, self-contained PR.

### 3. Tool-registration plumbing passes `env` as a variadic string through three layers [severity: debt]
**Observation:** Environment awareness reaches tool handlers via
`newMCPServer(client, env ...string)` → `registerTools(server, client, env ...string)`
→ `statementHandler(client, name, statement, env ...string)`, each repeating the same
deduction dance (default → variadic arg → `client.env` fallback) —
`tools.go:47-53`, `tools.go:149-155`, `mcpserver.go:40-46`.
**Impact:** Low today (10 tools), but every future tool-handler factory copies this
pattern; the "environment" concern is smeared across the call chain instead of being
a single injected value.
**Recommendation:** Originally ticketed as **ARCH-T03** (#602), now closed as
subsumed by **ARCH-T13** (#599, from `2026-09-24-mcp-gateway.md`), which
consolidates the four variadic env signatures into one config struct as part of a
broader transport-core generalization: replace the variadic env with a
small `ToolRuntime` struct (`env`, `client`) constructed once in `main.go` and
threaded explicitly. Mechanical, low-risk refactor that removes per-tool boilerplate.

### 4. openwiki runtime map omits the mcp-gateway sidecar [severity: debt]
**Observation:** `openwiki/architecture/overview.md` documents the indicator-service
Go sidecar in the runtime diagram and component table (lines ~65–114) but never
mentions the mcp-gateway, despite it being a deployed Compose service
(`docker-compose.yml:125`). The mcp-gateway README is excellent, but the repo-level
architecture doc that future tickets read first is incomplete.
**Impact:** New contributors and tickets discover the sidecar by accident; the
provider-agnostic trust-boundary rules (no provider names, unauthenticated internal
listener) live in one README instead of the shared architecture narrative.
**Recommendation:** Originally ticketed as **ARCH-T04** (#603); closed at the
maintainer's request — OpenWiki regenerates automatically on a daily schedule, so
the gap self-heals without a ticket.

### 5. `/mcp` unauthenticated by design — fine now, has a clear trigger condition [observation only]
**Observation:** The unauthenticated MCP listener is documented
(`README.md:21-25`) and intentional: the trust boundary is the backend
`X-Service-Token` data plane, and `docker-compose.prod.yml` publishes no host port
("Internal network only by design"). In the *dev* Compose the port is published
(`:8086`), which is acceptable for local use.
**Recommendation:** No ticket. Trigger to revisit: when the gateway must serve
agents outside the internal Compose network or distinguish multiple tenants, add a
config-gated bearer-token middleware in front of `/mcp`. Recorded here so the
decision point is explicit.

### 6. Adding "different APIs" scales correctly — via the backend, not the sidecar [observation only]
**Observation:** The architecture already answers the multi-provider question:
`DataPlaneMarketGateway` composes per-provider gateways behind one
provider-agnostic interface (`src/market/gateway.py`), and the data plane is the
single contract surface. The Go sidecar holds no provider credentials and one
client. Adding a *second backend domain* (e.g. portfolio or watchlist tools) would
require a second client/token pair and de-hardcoding `dataPlanePath`
(`backendclient.go:19`) — a modest, well-contained refactor when the time comes.
**Recommendation:** No ticket now. Keep the rule: new tools = new data-plane route +
new Go client method + registration; new APIs = new provider behind the backend
gateway composition. Revisit the client-path parameterization only when a second
domain is actually exposed.

## What went well

- **Strict thin-sidecar discipline**: no provider credentials, no direct provider
  calls, one data-plane client (`README.md`, `backendclient.go`) — the
  provider-name rule is enforced in code comments, tests, and docs consistently.
- **Error taxonomy**: four sentinel classes (`ErrNoData`/`ErrValidation`/
  `ErrConfiguration`/`ErrProvider`) with `backendError` deliberately keeping
  diagnostics out of `Error()` — a leak-proof agent boundary that is well tested.
- **Shared `runTool` pipeline + typed input structs**: tool addition is a uniform
  pattern (input struct, `prepare`, backend call), with client-side validation
  mirroring backend constraints so most 422s never happen.
- **`ErrNoData`-as-success semantics**: 404-with-cache-TTL is correctly modeled as
  a non-error outcome, an easy thing to get wrong.
- **Prod posture**: prod compose publishes no host port for the gateway; health
  checks are liveness-only and honest about it.

## Prior finding disposition

No prior review reports existed when this review was written. No open ARCH-T
tickets at that time. A same-day review (`2026-09-24-mcp-gateway.md`, tickets
ARCH-T10–T13 / #596–599) overlaps this one: its ARCH-T10 (#596) duplicates the
contract guard above (my ARCH-T01 #600 closed in its favor), and its ARCH-T13
(#599) subsumes the env-plumbing refactor above (my ARCH-T03 #602 closed). Its
ARCH-T11 (#597, shrink Go mirrors) and ARCH-T12 (#598, concurrent fundamentals)
are complementary findings not covered here, as is my unique ARCH-T02 (#601,
concurrency cap). Past ARCH ticket ARCH-T03 (#549, "Distinguish HTTP 422
validation errors in MCP gateway") was merged (commit `e7a318c6`) and its
behavior is present and tested in
`classifyBackendError`/`validationMessage` — addressed.
