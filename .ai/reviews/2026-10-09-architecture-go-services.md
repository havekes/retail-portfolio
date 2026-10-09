---
title: Architecture review 2026-10-09 — Go microservices
date: 2026-10-09
status: resolved        # orchestrator sets `resolved` when all its ARCH tickets close
verdict: needs-remediation
---

# Architecture Review 2026-10-09 — Go microservices

## Summary

Both Go services (`services/indicator-service/`, ~1.0k LOC; `services/mcp-gateway/`, ~2.4k LOC) are internally sound: thin, well-tested (7.2k test LOC), with a clean error taxonomy and a generalized `Transport`/`RouteGroup` core in the gateway. The structural issue is that each is a flat `package main` with no enforced boundaries — `mcp-gateway/tools.go` is 1,144 lines mixing registry plumbing, eight tool descriptions, input types, validators and symbol ranking, and its test file is 2,650 lines. The **most important observation is security, not layout**: `docker-compose.prod.yml:54-55` publishes the unauthenticated indicator-service `/compute` endpoint on the prod host (`8085`), even though its only caller (the backend) reaches it over the Compose network; combined with unbounded per-request work, that is a remotely triggerable CPU/memory sink. It's a one-line fix, hence `needs-remediation`.

## Proposed target layout

Standard Go `cmd/` + `internal/` layout, same shape in both services so conventions transfer:

```
services/mcp-gateway/
  cmd/mcp-gateway/main.go        # wiring + server lifecycle only
  internal/config/               # Config, Load(getenv)
  internal/logging/              # logger setup, HTTP access-log middleware, header redaction
  internal/backend/              # transport.go (Transport, RouteGroup, Do), errors.go (taxonomy,
                                 #   classify, validation msg), market.go (market data client),
                                 #   contract_test.go
  internal/tools/                # registry.go (toolSpec, addTool, runTool, result mapping),
                                 #   validate.go, prices.go (history, quote, indicators),
                                 #   fundamentals.go (fundamentals, statements), options.go,
                                 #   symbols.go (resolve_symbol + ranking) — description consts
                                 #   live next to their tool
  internal/server/               # MCP server identity, router, /health

services/indicator-service/
  cmd/indicator-service/main.go
  internal/config/               # Config struct (PORT, ENVIRONMENT, LOG_LEVEL) — today read ad hoc in main
  internal/indicators/           # calculator.go, timeframe.go, point types (pure domain, no net/http)
  internal/httpapi/              # handlers, router, request-ID/logging middleware, request/response DTOs
  internal/logging/
```

Rejected: a shared Go module (`go.work` + `services/pkg/`) for the duplicated logger/response-writer/shutdown code. Each service has its own `go.mod` and its Docker build context is `./services/<svc>`, so sharing would require widening build contexts and versioning an internal module — more cost than ~200 duplicated lines. Align the shape instead (findings 6–8).

## Decisions (2026-10-09, user)

- Layout: full `cmd/` + `internal/` move for both services (#6, #7, #8 all go ahead).
- No external consumer of prod port 8085. Dev host ports follow backend 8001, frontend 8002, services 8003+ (mailcrab 8003, indicator-service 8004, mcp-gateway 8005); prod and debug ports unchanged (folded into #1).
- #3 and #4 ship as one ticket.
- Tickets (base `feat/market-gateway-mcp`): #1 → ARCH-T31 (#729), #2 → ARCH-T32 (#730), #3+#4 → ARCH-T33 (#731), #5 → ARCH-T34 (#732), #8 → ARCH-T35 (#733), #6 → ARCH-T36 (#734), #7 → ARCH-T37 (#735) + ARCH-T38 (#736, split for PR size). #9: no ticket.

## Findings

### 1. indicator-service is published on the prod host, unauthenticated [severity: risk] [actionable] [blocking: yes]
**Observation:** `docker-compose.prod.yml:54-55` maps `8085:8080` for `indicator-service`. `/compute` (`services/indicator-service/handlers.go:34`) has no authentication and accepts 10 MiB bodies. The only caller is the backend (`src/market/service.py:432`) via `INDICATOR_SERVICE_URL=http://indicator-service:8080` (`.env.example:37`) — Compose-internal, so the host port serves no one. `mcp-gateway` already follows the right pattern ("Internal network only by design", `docker-compose.prod.yml:69`). In dev, both Go services publish on all interfaces (`docker-compose.yml:115`, `:129`), so anyone on the developer's LAN can reach `/compute` and `/mcp` (the latter riding the default `dev-market-data-token` into the data plane).
**Impact:** Anyone who can reach the prod host on 8085 can drive arbitrary CPU/memory load (see #2) on the box that also runs the backend and Postgres.
**Recommendation:** Remove the `ports:` block from `indicator-service` in `docker-compose.prod.yml` (add the same "internal network only" comment). In `docker-compose.yml`, bind both Go services to loopback and renumber them into the dev host-port scheme (backend 8001, frontend 8002, services 8003+; mailcrab keeps 8003): `"127.0.0.1:${INDICATOR_SERVICE_PORT:-8004}:8080"` and `"127.0.0.1:${MCP_GATEWAY_PORT:-8005}:8080"`. Update `.env.example` (`INDICATOR_SERVICE_PORT=8004`, add `MCP_GATEWAY_PORT=8005`) and any doc referencing 8085/8086. Prod ports (backend 8000, frontend 80) and debug ports (8090/8091) are unchanged. Update both READMEs' Compose sections. `scripts/setup-agent-worktree.sh:35-36,71-72` only allocates the host ports, so loopback binding keeps worktrees working. Verifiable: `docker compose -f docker-compose.prod.yml config` shows no published port for indicator-service; backend indicator tests still pass.
**Order:** none — do first.

### 2. indicator-service `/compute` has no work bounds [severity: risk] [actionable] [blocking: no]
**Observation:** `ComputeHandler` (`handlers.go:80-92`) loops over an unbounded `req.Indicators` slice; `req.Candles` is bounded only by the 10 MiB body (~100k candles); `period`/`fast`/`slow`/`signal`/`stdDev` are uncapped (`models.go:82-155`). SMA/EMA/BB/RSI guard `period > len(candles)` (`calculator.go:75,104,133,245`), but `ComputeMACD` (`calculator.go:189-200`) only checks `> 0` before calling `trend.NewMacdWithPeriod` with arbitrary ints, and `ScalePeriod` multiplies by up to 35 with no overflow guard (`timeframe.go:40`). The mcp-gateway already caps periods at 2–400 on its side (`tools.go`, `validatePeriodParam`), but the service itself trusts its input.
**Impact:** One request can carry thousands of indicator specs over 100k candles; even after #1 this remains reachable from anything on the Compose network.
**Recommendation:** Validate in `ComputeHandler` before computing: max indicators per request (e.g. 16), max candles (e.g. 10,000), period/fast/slow/signal in `[1, 1000]`, `stdDev` in `(0, 10]`; return 400 with a field-named message. Add table tests in `handlers_test.go` for each bound. Confirm the backend's real payload sizes fit (`src/market/service.py`).
**Order:** independent of #1.

### 3. mcp-gateway `/mcp` transport runs on SDK defaults with no session reaping [severity: concern] [actionable] [blocking: no]
**Observation:** `newRouter` (`main.go:146-153`) passes `nil` options to `mcp.NewStreamableHTTPHandler` (go-sdk v1.8.0). With `SessionTimeout` zero, idle sessions are never closed (`streamable.go:171`), on a listener that is unauthenticated by design. The SDK's DNS-rebinding guard only fires when the local address is loopback (`streamable.go:317-325`); inside a container behind Docker NAT it never is, so the guard is inert. No `CrossOriginProtection`. In `RouteGroup.Do` (`transport.go:322-336`) a call that queues on the concurrency semaphore waits only on `ctx`; the 15 s `http.Client.Timeout` does not cover the wait, and with `PropagateRequestCancellation` off the tool ctx may not cancel when the client disconnects.
**Impact:** Session state grows without bound over a long-lived deployment; a stuck backend can pile up queued tool calls indefinitely; a browser on the dev host can drive tools via cross-origin requests.
**Recommendation:** Pass `&mcp.StreamableHTTPOptions{SessionTimeout: cfg.SessionIdleTimeout}` (new env `SESSION_IDLE_TIMEOUT`, default 30m); wrap `/mcp` in `http.NewCrossOriginProtection()`; bound the semaphore wait by deriving a `context.WithTimeout(ctx, defaultHTTPTimeout)` at the top of `Do` (covering wait + request). Tests: config parsing, queued call times out with `ErrProvider`, cross-origin POST is rejected.
**Order:** after #650 and #586 if they are still open when scheduled (both touch `transport.go`/call sites); otherwise none.

### 4. Symbols are validated by length only and land in a URL path [severity: concern] [actionable] [blocking: no]
**Observation:** `requireSymbol` (`tools.go:972-981`) checks only non-empty and ≤32 chars. The symbol is `url.PathEscape`d into the path (`backendclient.go:72` et al.), which encodes `/` as `%2F` — but ASGI servers decode `%2F` in `scope["path"]`, and the backend path params are bare `symbol: str` (`src/market/data_router.py:116,138,229,394`). Upper-casing in `normalizeSymbol` happens to block the obvious sub-route confusions (`/EXPIRATIONS` ≠ `/expirations`), but that is accidental, not a control. The symbol also flows on to upstream provider URLs from the backend.
**Impact:** Low today (the service token only reaches data-plane routes), but any future lower-case route or provider-URL construction becomes injectable from agent input.
**Recommendation:** Allowlist the charset in `requireSymbol`: `^\^?[A-Za-z0-9][A-Za-z0-9.\-=]{0,30}$` (covers forms in the repo — `RY.TO`, `VOD.L` (`src/market/fmp.py:56`), `SHOP-A` (tests) — plus `^GSPC`/`EURUSD=X` index/FX forms; re-check against provider symbol formats before merging). Add rejection tests for `/`, `%`, `..`, whitespace, and control chars. Optionally mirror the pattern as a `Path(pattern=…)` on the backend routes (separate backend ticket if wanted).
**Order:** ticketed together with #3 as one "mcp-gateway hardening" PR (user decision); same ordering as #3.

### 5. No Go vulnerability scanning in CI [severity: debt] [actionable] [blocking: no]
**Observation:** `.github/workflows/ci.yml:110-123,157-170` and `justfile:20-34` run `staticcheck` and `go test` only. The gateway depends on `go-sdk` v1.8.0 and `golang.org/x/*`; the indicator service on `cinar/indicator/v2`. Nothing flags known CVEs in dependencies or the stdlib.
**Impact:** Vulnerable deps ship silently.
**Recommendation:** Add `go run golang.org/x/vuln/cmd/govulncheck@<pinned> ./...` per service to both CI Go jobs and to `just lint-go`. Verifiable: CI step present and green.
**Order:** none.

### 6. `mcp-gateway/tools.go` is a 1,144-line monolith [severity: debt] [actionable] [blocking: no]
**Observation:** `tools.go` holds the registry (`toolSpec`, `addTool`, `runTool`, result mapping), eight ~25-line description constants, eight input/request type pairs with `prepare` methods, ~15 validators, fundamentals section filtering, and `rankSymbolMatches`. `tools_test.go` is 2,650 lines. Every new tool (the README's own recipe, `README.md:209-231`) edits the middle of this file.
**Impact:** The highest-churn file in the service is the hardest to navigate and review; parallel tool tickets conflict on it.
**Recommendation:** Pure file split inside `package main`, no behaviour change: `tools.go` (registry + result mapping), `tools_validate.go`, `tools_prices.go` (price history, quote, technical indicator), `tools_fundamentals.go` (fundamentals, statements), `tools_options.go`, `tools_symbols.go` (resolve_symbol + ranking); each description const moves next to its tool; split `tools_test.go` the same way. Verifiable: `go test ./...` and `contract_test.go` unchanged and green; no non-move diff beyond imports.
**Order:** after #650 and #586 (both edit tool call sites) to avoid rebasing a move.

### 7. mcp-gateway: move to `cmd/` + `internal/` packages [severity: debt] [actionable] [blocking: no]
**Observation:** Everything is `package main`, so nothing stops tool handlers from reaching into transport internals — and they do: `tools.go:311,362,379,900,909` construct `&backendError{...}` directly; `indicatorQuery` (`backendclient.go:203`) and the `statement*` consts are unexported types shared across concerns. Smaller drift that the split should clean up: `main.go` repeats the same five `slog` attributes six times; base-URL validation is duplicated (`config.go:101` `validateBaseURL` vs `transport.go:215-230`); `Transport.BaseURL/Config` and `RouteGroup.Prefix/Token/Transport` exist only for tests; `Transport` stores the whole `Config` including the service token; `runTool` takes `cfg Config` solely for `isDev` checks that the slog level already gates.
**Impact:** Boundaries that are documented in comments ("must not be forwarded to agent-facing output") aren't enforced by the compiler; the next data domain (README recipe) will copy the coupling.
**Recommendation:** Adopt the target layout above. Export a minimal `backend` API (`backend.NoData()`, `backend.Provider(err)` constructors or exported sentinels + `IndicatorQuery`), move `main.go` to `cmd/mcp-gateway/` with a `logger.With(...)` base logger, drop the duplicate validation and test-only accessors, and stop threading `Config` into `runTool`. Update the Dockerfile build target (`go build -o mcp-gateway ./cmd/mcp-gateway`), the README recipe and file references. `contract_test.go` finds the snapshot by walking up to the repo root (`contract_test.go:48-70`), so it survives the move. Verifiable: `go vet`/`staticcheck`/`go test ./...` green, image builds, `GET /health` and an MCP `tools/list` unchanged.
**Order:** depends on #6 (and transitively #650/#586); land #3/#4 first or rebase them.

### 8. indicator-service: move to `cmd/` + `internal/` packages and align conventions [severity: debt] [actionable] [blocking: no]
**Observation:** Config is read ad hoc from `os.Getenv` in `main.go:15-20` (no struct, no validation; `ParseLogLevel` silently falls back where the gateway errors). `NewRouter(loggers ...*slog.Logger)` (`handlers.go:100`) uses the variadic-injection pattern ARCH-T13 removed from the gateway. Wire DTOs (`ComputeRequest`) and domain point types (`MAPoint`…) share `models.go`. Conventions have diverged between the two services: indicator-service has request IDs and status-based access-log levels (`middleware.go:104-180`); mcp-gateway has neither and logs every request at Info.
**Impact:** Two services, two sets of conventions; each new Go service will pick one at random.
**Recommendation:** Adopt the target layout above (smaller service — good pilot for the convention): `internal/config` with a `Load(getenv)` like the gateway's, `internal/indicators` free of `net/http`, `internal/httpapi` with explicit logger injection. Add a short `services/README.md` "Go service conventions" section (layout, config struct, logging, request ID, graceful shutdown) and link it from root `AGENTS.md` Project Guides. Update Dockerfile build target and README test-file list (`README.md:197`). Request-ID propagation in the gateway is deliberately left to #586 (OTel trace context supersedes it).
**Order:** after #2 (both edit `handlers.go`); independent of #6/#7 — recommended as the first layout ticket.

### 9. OpenWiki still omits mcp-gateway [severity: debt] [observation] [blocking: no]
**Observation:** ARCH-T04 (#603) was closed on the expectation that the scheduled OpenWiki refresh would add the gateway. `grep -rli 'mcp-gateway\|mcp gateway' openwiki/` returns nothing; `openwiki/architecture/overview.md` still lists only the indicator-service sidecar.
**Recommendation:** No ticket (generated pages aren't hand-edited per `AGENTS.md`). Worth checking whether `.github/workflows/openwiki-update.yml` is running and why it doesn't pick up `services/mcp-gateway/`.

## What went well

- **Error taxonomy** (`transport.go:33-90`): agent-safe `Error()`, diagnostics split into `Status()`/`Detail()`, `ErrNoData`-as-success — still the right contract.
- **Contract test** (`contract_test.go`) against the checked-in OpenAPI snapshot closed the drift gap flagged on 2026-09-24, and its repo-root discovery makes it layout-independent.
- **`Transport`/`RouteGroup`** is a good seam for a second data domain; the concurrency semaphore is in the right place.
- **Secret hygiene**: header redaction (`mcp-gateway/middleware.go:13-34`), token never logged or put in errors, constant-time compare on the backend (`src/auth/api.py:322`).
- **Images**: multi-stage, static binary, non-root user in both Dockerfiles.
- **Test density**: ~2:1 test-to-source lines in both services.

## Prior finding disposition

- **2026-09-24 (two same-day mcp-gateway reviews):** contract guard ARCH-T10 (#596) — addressed (`contract_test.go`). Shrink mirrors ARCH-T11 (#597) — addressed (`json.RawMessage` pass-through). Concurrent fundamentals ARCH-T12 (#598) — closed. Client generalization ARCH-T13 (#599) — addressed (`Transport`/`RouteGroup`); residual `Config` threading into `runTool` folded into #7. Concurrency cap ARCH-T02 (#601) — addressed; unbounded semaphore wait raised in #3. OpenWiki ARCH-T04 (#603) — closed but **not healed** (#9).
- **09-24 observations:** unauthenticated `/mcp` — still acceptable, not re-raised. Dev host publishing + default token — escalated in #1/#3 with new evidence (SDK rebinding guard is inert behind Docker NAT). Static `serverVersion = "0.0.1"` (`mcpserver.go:12`) — unchanged, inert.
- **ARCH-T14–T17 (#669–#672):** all closed (fundamentals contract canonicalization, partial fundamentals, statement pass-through, Go lint gate). Their cited source `.ai/reviews/2026-10-06-architecture-market-gateway-mcp.md` is not in the repo — it was never committed.
- **Open, related (not ARCH):** #650 F-OBS-FIX-T05 and #586 F-OBS-T10 both touch mcp-gateway call sites; #3, #6 and #7 are ordered after them.
- No open `ARCH-T` issues at time of review.
