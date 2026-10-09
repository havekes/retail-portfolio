## Plan

**Approach:** Extend the existing typed `MarketService`/`ApiClient` seam in `frontend/src/lib/api/marketService.ts` rather than introducing a new module: add a `WatchlistSort` string-literal union mirroring the backend `WatchlistSortMode` enum (`src/market/enum.py`), a `WatchlistSecuritySchema` interface extending `SecuritySchema` with `added_at`/`position`, tighten `WatchlistRead` accordingly, and add two thin methods (`updateWatchlistSort` → PATCH, `reorderWatchlistSecurities` → PUT) using the existing protected `patch<T, R>` / `put<T, R>` helpers and the trailing optional `token` argument convention. Tests extend the colocated `marketService.test.ts` with stubbed `global.fetch` responses, exactly like the existing `renameWatchlist` / `addSecurityToWatchlist` cases. (Rejected alternative: a dedicated watchlist client module — rejected because all watchlist calls already live in `MarketService` in this codebase.)

**Files:**
- `frontend/src/lib/api/marketService.ts` — modify: types + 2 new methods
- `frontend/src/lib/api/marketService.test.ts` — modify: extend fixtures and add suite coverage for both methods

**Steps:**
1. In `marketService.ts`, add the exported union next to the watchlist types (~line 62):
   `export type WatchlistSort = 'custom' | 'name_asc' | 'price_change_desc' | 'price_change_asc' | 'date_added' | 'date_added_asc';`
   The six value strings must match `WatchlistSortMode` in `src/market/enum.py` exactly (note: `name_asc`, not `name`; `date_added` = newest first, `date_added_asc` = oldest first — encode this in a short doc comment only).
2. Add `export interface WatchlistSecuritySchema extends SecuritySchema { added_at: string; position: number; }` and change `WatchlistRead.securities: WatchlistSecuritySchema[]`; add `sort: WatchlistSort` to `WatchlistRead` (matches backend `WatchlistRead`, `src/market/schema.py` line 112).
3. Widen `export interface WatchlistUpdate { name?: string; sort?: WatchlistSort }` so the PATCH endpoint's optional fields match backend `WatchlistUpdate` (`src/market/schema.py` line 120: name and sort both optional; renameWatchlist keeps sending `{ name }` and stays valid).
4. Add `updateWatchlistSort(watchlistId: string, sort: WatchlistSort, token?: string | null): Promise<WatchlistRead>` calling `this.patch<WatchlistRead, WatchlistUpdate>(\`/market/watchlists/${watchlistId}\`, { sort }, {}, token)` — no `name` in the body (backend PATCHes either field independently; verify `patch` returns the parsed watchlist, `apiClient.ts` line 88).
5. Add `reorderWatchlistSecurities(watchlistId: string, securityIds: string[], token?: string | null): Promise<WatchlistRead>` calling `this.put<WatchlistRead, { security_ids: string[] }>(\`/market/watchlists/${watchlistId}/securities/order\`, { security_ids: securityIds }, {}, token)` — path and body key (`security_ids`) must match `PATCH/PUT` backend routes `src/market/router.py` lines 354 and 454; use the serializer-order `securityIds` array as-given (ordering is the caller's responsibility).
6. Update the test file's shared fixtures: give the bottom `watchlistFixture()` a `sort: 'custom'` default and make the bottom `security` fixture reusable as a `WatchlistSecuritySchema` (add `added_at: '2026-01-01T00:00:00Z'` and `position: 0`, overridable like existing fields). Fixtures only — don't rename helpers already used by earlier tests.
7. Add tests (stub `global.fetch` like every existing case; no real fetch):
   - `updateWatchlistSort`: PATCH to `/api/v1/market/watchlists/wl-1`, `body: JSON.stringify({ sort: 'date_added' })`, Authorization header with token, resolves the returned watchlist (assert `.sort`).
   - `reorderWatchlistSecurities`: PUT to `/api/v1/market/watchlists/wl-1/securities/order`, `body: JSON.stringify({ security_ids: ['sec-2', 'sec-1'] })` asserting array order is preserved, resolves returned watchlist.
   - Error propagation for both: stub `ok: false, status: 422` with `{ detail: '...' }` and assert rejects with the backend detail message `toBeInstanceOf(ApiError)` (pattern already used at test line ~245).
8. Gate checks: `./scripts/agent-test frontend/src/lib/api/marketService.test.ts` (targeted) then `./scripts/agent-test --frontend` (Gate 0 lint/svelte-check + full frontend regression, i.e. `npm run lint` / `npm run check` / `npm run test:run` equivalents — all via Docker).

**Verification:**
- `./scripts/agent-test frontend/src/lib/api/marketService.test.ts` — all new/updated cases green with zero real network calls.
- `./scripts/agent-test --frontend` — Gate 0 (lint + type check) passes and the full frontend suite passes; types must svelte-check cleanly against existing call sites (`getWatchlists`, `renameWatchlist`, etc. still compile with `WatchlistRead` gained required `sort`).
- Manual contract spot-check: TS union values diff against `src/market/enum.py::WatchlistSortMode` one-to-one.

**Risks / watch-outs:**
- The branch (T01–T03 merged) has already evolved these files, so anything read on `main` may be stale. Reconcile before editing tests — the fixture changes in step 6 only apply if T01–T03 haven't already added `sort`/`added_at`/`position` to the fixtures.
- `WatchlistRead.securities` goes through a required-field change (added_at/position/sort now required) — any other consumer (e.g. a mock or fixture in `.svelte.ts`/components) that fabricates a `WatchlistRead` will fail `check` after this ticket's changes even though the fix belongs to T05/T06; fix any such fixture in this ticket's diff (fixture-only, not logic) to keep the build green.
- Error propagation must be `422` for reorder (backend `WatchlistOrderIdentityError`) and `409` for duplicate-name paths; assert the generic detail-message mechanism (from `apiClient.ts` line 26) against the actual status codes the backend emits.

## Review feedback

<empty. Orchestrator appends PR-review findings here.>
