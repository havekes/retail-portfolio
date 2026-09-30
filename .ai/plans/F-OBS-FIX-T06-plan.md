## Plan

**Approach:** Six independent, pre-verified nits handled as one checklist on a single `fix/f-obs-fix-t06-review-nits` branch — each item is a tiny, self-contained edit plus verification, so no cross-item ordering constraints exist. Item 5 resolves `generateTraceparent` by dropping the dead optional parameter (matches the codebase's minimal-surface convention; the "keep + docstring" alternative is rejected as it preserves dead surface). Item 6 adds the hermetic empty-result test as a small gateway subclass in the existing `tests/market/test_market_fetch_events.py` file, mirroring the established `_RaisingGateway` pattern.

**Files:**
- `docker/observability/otelcol-sampling.yaml` — modify: reword the line-13 header comment ("Policy, in evaluation order (tail sampling stops at the first matching policy):") to union semantics, e.g. "# Policy set (tail sampling retains a trace if ANY policy matches; order never shadows):" and keep the numbered list. Change both `${env:OTEL_SAMPLER_SUCCESS_PERCENT}` references (line 83 `sampling_percentage`, line 94 `event.sample_rate` statement) to `${env:OTEL_SAMPLER_SUCCESS_PERCENT:-7}`. No policy/transform semantics change.
- `docker/observability/README.md` — modify: replace line 171 ("Tail sampling stops at the first matching policy, so the probabilistic bulk can never shadow a failure.") with union wording, e.g. "The policy set is a union — a trace is kept if *any* policy matches — so the probabilistic bulk can never shadow a failure, regardless of order." Table at line 165-169 stays valid (the "Order" column remains meaningful as documentation order; leave it).
- `services/indicator-service/middleware.go` — modify: `newRequestID()` (line ~38): on `rand.Read` failure return a time/pid-derived fallback id (e.g. `fmt.Sprintf("%x-%x", time.Now().UnixNano(), os.Getpid())` — imports `os`, `time`, `fmt`; drop the empty-string return). Keep `RequestIDMiddleware` semantics otherwise.
- `services/indicator-service/handlers.go` — modify: delete the unused `r = r.WithContext(ctx)` (line 67). The `ctx, span := tracer().Start(...)` and deferred `span.End()` stay.
- `src/integration/task.py` — modify: `handle_interrupted_task` (line ~459): replace `_ = exc` with `logger.debug("Interrupted task %s reported exc: %s", task.id, exc)` as the first statement (before the task-name check) so the exception is always recorded.
- `src/ws/manager.py` — modify: add `_UNKNOWN_USER_ID = "unknown"` next to `_UNKNOWN_MESSAGE_TYPE` (line 22) and use it as the `user_id` fallback in the `ws.delivery` failure emit (lines 187-191). The `message_type` argument keeps `_UNKNOWN_MESSAGE_TYPE`.
- `tests/fixtures/redis.py` — modify: extend the module docstring (lines 1-9) with a sentence stating that `FakePubSub` registers subscribers on the fake Redis and fans published messages out to each subscriber queue, so a real `ConnectionManager` listener can be driven with no Redis server.
- `frontend/src/lib/api/traceContext.ts` — modify: drop the optional `traceId` parameter from `generateTraceparent` (lines 74-85); body becomes `randomHex` trace id always. `deriveChildTraceparent` (line 95) already calls it with no argument — unchanged.
- `frontend/src/lib/api/traceContext.test.ts` — modify: remove/rewrite the test cases that pass a `traceId` argument to `generateTraceparent` (lines 35-47); the no-arg cases (fresh-trace, uniqueness, all-zero/malformed rejection, `randomHex` stubbed determinism) stay.
- `src/market/gateway.py` — modify: in `record_fetch`'s `else:` branch (line ~178), wrap the success `emit_market_data_fetched(...)` call in `try/except Exception` with `logger.debug("Market fetch telemetry emission failed: %s", emit_error)` matching the failure branch's guard (lines 161-175). Docstring gains one line noting success telemetry is also best-effort.
- `tests/market/test_market_fetch_events.py` — modify: add an `_EmptyGateway(StubEodhdGateway)` subclass whose `get_prices`/`get_intraday_prices` return `[]` (same signatures as `_RaisingGateway`, lines 127-152), plus one test `test_service_empty_price_window_emits_success_row_count_zero` (anyio, `span_exporter`): call `service._update_security_prices(security, from_date, to_date)` via `_service(_EmptyGateway(...))`, assert it returns `True`, then read `_single_fetch_attributes(span_exporter)` and assert `outcome == "success"`, `row_count == 0`, and `"freshness_lag_ms" not in attributes`.

**Steps:**
1. Items 1 (yaml + README rewording): rewrite the yaml header comment and README §6 sentence to union semantics; verify no "first matching"/"stops at the first matching" wording remains in those two files.
2. Item 1 (env defaults): add `:-7` inline defaults to lines 83 and 94 of `otelcol-sampling.yaml`.
3. Item 2: implement the `newRequestID()` fallback in `middleware.go`; delete `r = r.WithContext(ctx)` in `handlers.go` (line 67).
4. Item 3: replace `_ = exc` in `src/integration/task.py` with a `logger.debug` including `task.id` and `exc`.
5. Item 4a: add `_UNKNOWN_USER_ID` in `src/ws/manager.py` and use it for the delivery-failure `user_id` fallback only.
6. Item 4b: extend the `tests/fixtures/redis.py` module docstring with the FakePubSub fan-out description.
7. Item 5: drop the `traceId` parameter from `generateTraceparent` in `traceContext.ts`; update `traceContext.test.ts` accordingly.
8. Item 6: guard the success emit in `src/market/gateway.py::record_fetch` with try/except + debug log.
9. Item 6 test: add `_EmptyGateway` and the `row_count == 0` / no-`freshness_lag_ms` success test in `tests/market/test_market_fetch_events.py`.
10. Run the verification suite below; fix any fallout.

**Verification:**
- Item 1: `./scripts/agent-test tests/observability/test_sampling_config.py` — passes. Note: `test_sampling_stamp_exposes_the_applied_decision` (line 180-183) asserts the *exact* string `set(span.attributes["event.sample_rate"], ${env:OTEL_SAMPLER_SUCCESS_PERCENT})` without a default; adding `:-7` breaks it. Correct that one assertion to the `:-7` form (minimal, behavior-preserving test adjustment — flag in PR description). The `_resolved_success_percent` regex (line 78) and the band test already accept a `:-N` default, so the rest passes unchanged. `grep -n "first matching" docker/observability/*` → no hits in the yaml/README. The yaml is also config-parse-validated by `_collector_config()` inside the same test file (README §7 config-only validation).
- Item 2: in `services/indicator-service`: `go test ./...` (covers `middleware_test.go`) plus `go build ./...` / `gofmt -l .`; update `middleware_test.go` if it pins the empty-string fallback behavior.
- Item 3: `./scripts/agent-test tests/tasks/test_integration.py` — the existing interrupted-task tests (lines 1033-1116) exercise `handle_interrupted_task` directly and must pass.
- Item 4: `./scripts/agent-test tests/ws tests/fixtures` (or the ws test files covering the delivery path + redis fixture) plus grep that `_UNKNOWN_USER_ID` is used at the `user_id` fallback site only.
- Item 5: `./scripts/agent-test frontend/src/lib/api/traceContext.test.ts` then `./scripts/agent-test frontend` (Gate 0 lint/type-check + suite).
- Item 6: `./scripts/agent-test tests/market/test_market_fetch_events.py` — new test asserts `row_count == 0` and absence of `freshness_lag_ms` on the empty success path.
- Final gate: `./scripts/agent-test` (auto-detects backend + frontend from the diff) and the Go checks from step 2.

**Risks / watch-outs:**
- AC-1 in the ticket says "`tests/observability/test_sampling_config.py` passes **unchanged**", but the transform-statement assertion at lines 180-183 pins the exact env reference *without* a default — the yaml change the same criterion demands forces a one-line assertion update (regex-free, exact-string edit). This is an internal inconsistency in the ticket; handle it as a deliberate, documented deviation rather than dropping the env default.
- The test file itself contains a "stops at the first matching policy" comment (line 137) — outside AC-1's file list; optionally reword while touching the file, otherwise leave.
- `newRequestID` fallback: keep it deterministic-ish and low-cardinality-safe (time+pid hex); do not log the failure or add dependencies (`os`, `time`, `fmt` are stdlib).
- `generateTraceparent` removal: check for any other callers with `grep -rn "generateTraceparent"` in `frontend/src` — only `apiClient.ts` and `deriveChildTraceparent` call it, both without arguments.
- `emit_event` itself is non-guarding (raising), which is why item 6's guard is genuinely needed; mirror the failure path exactly, including not emitting a second event on emit failure.
- Keep `HandlerInterrupted` debug log behind `logger.debug` (not info/warning) per scope — no log-noise change.
