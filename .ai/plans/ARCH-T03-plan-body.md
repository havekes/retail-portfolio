## Meta
- id: ARCH-T03
- depends_on: []
- branch: feat/arch-t03-mcp-gateway-validation-errors
- source: ".agent/reviews/2026-09-24-architecture.md"

## Objective

Distinguish HTTP 422 (Unprocessable Entity) from HTTP 404 (Not Found) in the Go MCP gateway client. This ensures that parameter validation failures return actionable tool errors to AI agents rather than falsely reporting that no market data exists.

## Scope

**In scope:**
- Introduce `ErrValidation` in `services/mcp-gateway/backendclient.go` to classify HTTP 422 separately from `ErrNoData` (HTTP 404).
- Update `classifyBackendError` in `backendclient.go` to map 422 to `ErrValidation` instead of `ErrNoData`.
- Update `mapBackendError` in `services/mcp-gateway/tools.go` to return an error result (`result.SetError`) for `ErrValidation`, retaining the descriptive validation message from the backend.
- Update tests in `backendclient_test.go` and `tools_test.go`.

**Out of scope:**
- Changing backend validation rules in FastAPI.
- Changing MCP tool parameter schemas.

## Plan

**Approach:** Split 422 out of the `ErrNoData` classification by adding a fourth sentinel `ErrValidation` to `backendclient.go`'s error taxonomy, and give it an agent-safe descriptive message parsed from the backend's 422 response body (FastAPI writes validation messages into a `{"detail": ...}` body, and that body is already buffered in `classifyBackendError`). `mapBackendError` then maps `ErrValidation` through `errorResult` (error status) instead of `noDataResult`. This keeps the existing `backendError` wrapper + `errors.Is` contract intact — no plumbing changes beyond the two switches.

**Rejected alternative:** sending the raw backend validation JSON straight to the agent — rejected because tool-facing text must stay free of internal detail; only a parsed validation message may pass through.

**Files:**
- `services/mcp-gateway/backendclient.go` — modify: add `ErrValidation` sentinel; split 404/422 in `classifyBackendError`; extract a validation message from the 422 body; update taxonomy + `get()` doc comments (they currently say "one of three classes" and that every failure normalizes to `ErrNoData / ErrConfiguration / ErrProvider`).
- `services/mcp-gateway/tools.go` — modify: `mapBackendError` adds an `ErrValidation ⇒ errorResult(...)` branch ahead of the `ErrNoData` case; also fix the stale package comment that says a leaked 422 "would be misreported as 'no data'" and the `mapBackendError` contract comment.
- `services/mcp-gateway/backendclient_test.go` — modify: taxonomy case table (~line 189-190) expects `ErrValidation` for 422 with errors.Is; keep 404 → `ErrNoData`.
- `services/mcp-gateway/tools_test.go` — modify: `TestToolsMapBackendErrors` case (~line 400) "422 is no data" becomes "422 is validation error": `wantErr: true`, text = the backend's validation message (or `ErrValidation.Error()` when the body is unparsable).

**Steps:**
1. In `backendclient.go`, add to the sentinel `var` block: `ErrValidation = errors.New("market data request was invalid")` with a doc comment explaining it maps 422: the request's parameters failed backend validation (agent-addressable: retry with corrected parameters), unlike `ErrNoData` where retrying different data parameters is correct.
2. In `backendclient.go`, change `classifyBackendError` so `http.StatusNotFound` returns `ErrNoData` and `http.StatusUnprocessableEntity` returns `ErrValidation`, each with the existing `detail` truncation.
3. In `backendclient.go`, add a small helper that, given a 422 body, extracts an agent-safe validation message: try `json.Unmarshal` of the FastAPI body `{"detail": ...}` where `detail` is either a string or an array of `{loc, msg, type}` objects (render loc path + msg compactly, e.g. `"expiry must be a valid date"`); on any parse failure fall back to the `ErrValidation.Error()` generic text. Cap the message length (reuse `errorDetailLimit`). Store the message on the `backendError` so `mapBackendError` can forward it; if a new field feels heavy, the executor may instead re-parse the body in tools.go — pick one, don't do both — but the classification stay in `classifyBackendError`.
4. In `backendclient.go`, update the taxonomy doc comment and `get()`'s doc comment to describe four classes (404 → no data, 422 → validation, 401/403 → configuration, other → provider).
5. In `tools.go`, extend `mapBackendError` with `case errors.Is(err, ErrValidation): return errorResult(...)` carrying the backend validation message (falling back to `ErrValidation.Error()` internally if none is present). Keep `ErrNoData ⇒ noDataResult()` unchanged, and order the cases so only 422 maps to validation.
6. In `tools.go`, update the package-level comment ("no input can trigger a backend 422 ... classified as ErrNoData") and `mapBackendError`'s contract comment to reflect the new class.
7. In `backendclient_test.go`, update the taxonomy case table: 422 + any body must satisfy `errors.Is(err, ErrValidation)` and not `errors.Is(err, ErrNoData)`; 404 keeps `ErrNoData`. Add a case that a 422 with a FastAPI-style validation body surfaces the parsed message (e.g. the case checking `Detail()`/message string from the new helper).
8. In `tools_test.go`, change the 422 case in `TestToolsMapBackendErrors` to expect an error result whose text is the backend validation message from the stub body (pick a deterministic one, e.g. `{"detail":[{"loc":["query","expiry"],"msg":"invalid date","type":"value_error"}]}` or a string detail), while the 404 case keeps `wantErr: false` and `noDataMessage`.
9. Run `gofmt`/`go vet` and the full module tests (commands below; the codebase targets Go modules in the existing repo — check `services/mcp-gateway/go.mod` for the toolchain version).

**Verification:**
- From `services/mcp-gateway`: `go test ./...` — all existing tests still pass; the taxonomy case table now shows `{422, ErrValidation}` (AC 1); `TestToolsMapBackendErrors` shows the 422 case with `IsError = true` and a non-`noDataMessage` text (AC 2), and the 404 case with `IsError = false` and text `noDataMessage` ("No market data is available for this request.") (AC 3).
- Also run `go vet ./...` and `gofmt -l .` — both must be clean.

**Risks / watch-outs:**
- FastAPI's pydantic 422 detail arrays: strings are `loc`/`msg` but `loc` mixes strings and ints (e.g. `"query"` followed by `"expiry"`, or array indices) — unmarshal loosely (any) and stringify defensively.
- `backendError.Error()` must stay generic for the non-validation classes; make sure `ErrConfiguration`/`ErrProvider` behavior is untouched, and test the internal error result text for validation errors (or fall back to `ErrValidation.Error()`) so agent-facing output contains no status codes, tokens, or provider names.
- Test in `tools_test.go` covers every tool (validToolCalls × errCase): the 422 stub body must be chosen so the same expected message is produced for every tool path.
- Critically, tool `prepare()` validation still runs first and pre-empts most 422s; the 422 only surfaces when backend-side rules are tighter than the tool checks — keep the pre-validation logic untouched (out of scope).
- This gateway lives on the `feat/market-gateway-mcp` branch (PR #541), not `main`; the implementation branch must be created off `feat/market-gateway-mcp`.

## Review feedback
