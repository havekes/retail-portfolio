## Plan

**Approach:**
Address the four still-relevant review follow-ups from #424 (Items 3, 4, 5, 6) across watchlists and drawings, noting that Items 1 (cross-currency grouping) and 2 (debounced drawing writes) are already complete on `feat/security-details` via PRs #436/#438 and #450/#453. In the watchlist search picker, guard against async search response reordering using an incremental request token. In `WatchlistService`, short-circuit on pre-existing target membership before network resolution, reuse security IDs across watchlists to preserve stored currency without issuing `createOrUpdateSecurity({ currency: 'USD' })`, and centralize `this.error = null` at the start of all service mutations while stripping manual workarounds from the UI components. For drawings, normalize legacy date-string and BusinessDay anchors to UTC epoch seconds at the preference-loading seam (`ChartDrawingsService.svelte.ts`) and in point-equality comparisons (`drawings.ts`) to eliminate false-difference triggers and prevent extra preference PATCH writes on first load.

**Files:**
- `frontend/src/lib/components/watchlist/watchlist-security-picker.svelte` — modify: Add an incremental request counter (`latestRequestId`) to the debounced `search` function to drop stale or out-of-order query responses, and remove manual `watchlistService.error = null` from `handleSelect`.
- `frontend/src/lib/components/watchlist/watchlist-security-picker.test.ts` — create: Add tests for `watchlist-security-picker.svelte` verifying out-of-order search resolutions retain only the newest query result and error states are correctly surfaced.
- `frontend/src/lib/components/watchlist/watchlistService.svelte.ts` — modify: In `addSecurity`, inspect `target.securities` first to exit early if already present; search all `this.watchlists` to reuse existing `id` before falling back to `createOrUpdateSecurity`; clear `this.error = null` at the beginning of all 9 mutation methods (`loadWatchlists`, `createWatchlist`, `renameWatchlist`, `deleteWatchlist`, `addSecurity`, `removeSecurity`, `addSecurityToWatchlist`, `removeSecurityFromWatchlist`, `toggleSecurity`).
- `frontend/src/lib/components/watchlist/watchlistService.test.ts` — modify: Update dedupe tests to assert neither `createOrUpdateSecurity` nor `addSecurityToWatchlist` is called when security already belongs to the target list; assert existing security ID is reused without `createOrUpdateSecurity`; and assert all mutations reset `this.error` on subsequent success.
- `frontend/src/lib/components/watchlist/create-watchlist-modal.svelte` — modify: Remove manual assignments `watchlistService.error = null`.
- `frontend/src/routes/watchlists/+page.svelte` — modify: Remove manual assignments `watchlistService.error = null` in `confirmRename`, `confirmDelete`, and `handleRemoveSecurity`. Only show the page-level error alert when `!createOpen` to prevent duplicate error banners when the modal handles the error.
- `frontend/src/routes/watchlists/page.svelte.test.ts` — modify: Ensure tests for create error and rename/delete/remove error and recovery pass cleanly with centralized service error clearing.
- `frontend/src/lib/utils/finance/drawings.ts` — modify: Export `normalizeSecurityDrawings(drawings: SecurityDrawings | null | undefined): SecurityDrawings | null` converting `p1`/`p2` anchor times to epoch seconds via `normalizeDrawingTime`, and update `areDrawingPointsEqual` to compare points using `normalizeDrawingTime(a.time) === normalizeDrawingTime(b.time)`.
- `frontend/src/lib/utils/finance/drawings.test.ts` — modify: Add unit tests for `normalizeSecurityDrawings` and `areDrawingPointsEqual` asserting equality between epoch seconds, ISO date strings, and `BusinessDay` objects.
- `frontend/src/lib/services/ChartDrawingsService.svelte.ts` — modify: Normalize all drawings in `userPreferences.drawings` on initialization (constructor) and `setPreferences`, and normalize in `securityDrawings` getter so restored drawings match primitive epoch anchors immediately.
- `frontend/src/lib/services/ChartDrawingsService.test.ts` — modify: Add test asserting that loading legacy date-string or BusinessDay drawings initializes without triggering any `patchPreferences` write-back.

**Steps:**
1. Scope verification & baseline confirmation:
   - Confirm Item 1 (holdings cross-currency group sums) is already implemented in `holdings-table.svelte` via `groupHoldings(holdings, 'stock')` and covered in `holdings-group.test.ts`.
   - Confirm Item 2 (debounced drawing-tool preference writes) is already implemented in `ChartDrawingsService.svelte.ts` (`handleDrawingDragEnd`) and covered in `page.svelte.test.ts` and `ChartDrawingsService.test.ts`.
2. Implement Item 3 (Watchlist search picker race):
   - In `frontend/src/lib/components/watchlist/watchlist-security-picker.svelte`, introduce a local `latestRequestId = 0` counter.
   - In `search`, assign `const requestId = ++latestRequestId;`. When query trimmed length < 2, increment `latestRequestId++`, reset `searchResults = []`, `searchError = null`, `isSearching = false`, and return.
   - After `await watchlistService.searchSecurities(trimmed)`, check `if (requestId !== latestRequestId) return;` before assigning `searchResults` or `searchError`. In `finally`, only set `isSearching = false` if `requestId === latestRequestId`.
   - In `handleSelect`, remove `watchlistService.error = null;`.
   - Create `frontend/src/lib/components/watchlist/watchlist-security-picker.test.ts` with test cases for out-of-order promise resolution (query A launched first but resolving second, query B launched second but resolving first -> picker displays query B results).
3. Implement Item 4 (Currency-preserving watchlist dedupe):
   - In `frontend/src/lib/components/watchlist/watchlistService.svelte.ts`, in `addSecurity(watchlistId, result, token)`:
     - Find target watchlist `const target = this.watchlists.find((w) => w.id === watchlistId);`.
     - Check if target already contains a security matching `s.symbol.toUpperCase() === result.code.toUpperCase() && s.exchange.toUpperCase() === result.exchange.toUpperCase()`. If so, return immediately without calling `createOrUpdateSecurity` or `addSecurityToWatchlist`.
     - Check if ANY watchlist in `this.watchlists` already contains a matching security. If found, reuse its `id` as `securityId` directly without calling `createOrUpdateSecurity`.
     - Only if not found in any loaded watchlist, call `this.client.createOrUpdateSecurity({ code: result.code, exchange: result.exchange, name: result.name, currency: 'USD' })`.
     - Call `this.client.addSecurityToWatchlist(watchlistId, securityId, token)` and update state via `this.replaceWatchlist`.
   - Update `frontend/src/lib/components/watchlist/watchlistService.test.ts`:
     - Update the test `'is a no-op when the resolved security already belongs to the list'` to assert that neither `createOrUpdateSecurity` nor `addSecurityToWatchlist` is called.
     - Add test: selecting a security already present in another watchlist reuses its `id` and adds membership without invoking `createOrUpdateSecurity` with hardcoded `'USD'`.
     - Ensure lookup failure test queries for an unseen security so resolution error handling is exercised.
4. Implement Item 6 (Centralize WatchlistService error clearing):
   - In `frontend/src/lib/components/watchlist/watchlistService.svelte.ts`, set `this.error = null;` at the top of:
     - `loadWatchlists`
     - `createWatchlist`
     - `renameWatchlist`
     - `deleteWatchlist`
     - `addSecurity`
     - `removeSecurity`
     - `addSecurityToWatchlist`
     - `removeSecurityFromWatchlist`
     - `toggleSecurity`
   - In `frontend/src/lib/components/watchlist/create-watchlist-modal.svelte`:
     - Remove manual `watchlistService.error = null;` assignments from `handleSubmit` (lines 39 and 44).
   - In `frontend/src/routes/watchlists/+page.svelte`:
     - Remove manual `watchlistService.error = null;` assignments from `confirmRename` (line 98), `confirmDelete` (line 125), and `handleRemoveSecurity` (line 135).
     - Guard the page-level alert with `{#if watchlistService.error && !createOpen}` to prevent duplicate alerts while the create modal is open.
   - In `frontend/src/lib/components/watchlist/watchlistService.test.ts`:
     - Add test asserting that when `service.error` is pre-set (e.g. from a prior failure), calling any successful mutation clears `service.error` to `null`.
   - In `frontend/src/routes/watchlists/page.svelte.test.ts`:
     - Validate that success-after-failure scenarios properly clear page-level alerts.
5. Implement Item 5 (Normalize legacy drawing anchor times once at the seam):
   - In `frontend/src/lib/utils/finance/drawings.ts`:
     - Import `normalizeDrawingTime` from `./drawing-time`.
     - Export function `normalizeSecurityDrawings(drawings: SecurityDrawings | null | undefined): SecurityDrawings | null` which maps `measures`, `horizontalLines`, and `lines` anchor points (`p1.time`, `p2.time`) using `normalizeDrawingTime(time)`.
     - In `areDrawingPointsEqual(a, b)`: update comparison to `a.price === b.price && normalizeDrawingTime(a.time) === normalizeDrawingTime(b.time)`.
   - In `frontend/src/lib/services/ChartDrawingsService.svelte.ts`:
     - In the constructor and `setPreferences(prefs)`: normalize drawings across all securities in `prefs.drawings` using `normalizeSecurityDrawings` before setting `this.userPreferences`.
     - In the `securityDrawings` getter: return normalized drawings (`normalizeSecurityDrawings(drawings) ?? {}`).
   - In `frontend/src/lib/utils/finance/drawings.test.ts`:
     - Add unit tests for `normalizeSecurityDrawings` (mapping date string `"2025-01-01"` and `BusinessDay` `{ year: 2025, month: 1, day: 1 }` to epoch seconds `1735689600`).
     - Add unit tests for `areDrawingPointsEqual` verifying that an anchor with an ISO string and an anchor with epoch seconds compare equal.
   - In `frontend/src/lib/services/ChartDrawingsService.test.ts`:
     - Add test verifying that when initialized with legacy date-string or BusinessDay drawings, `patchPreferences` is NOT called during initialization or initial drawing read.
6. Verification & Quality Check:
   - Run unit tests:
     - `watchlist-security-picker.test.ts`
     - `watchlistService.test.ts`
     - `watchlists/page.svelte.test.ts`
     - `drawings.test.ts`
     - `ChartDrawingsService.test.ts`
     - `holdings-group.test.ts`
   - Run full frontend check `./scripts/agent-test` to ensure linting, types, and all tests pass.

**Verification:**
- Item 1: `pnpm --filter frontend test src/lib/utils/finance/holdings-group.test.ts` passes; confirms multi-currency same-security grouping behavior.
- Item 2: `pnpm --filter frontend test src/lib/services/ChartDrawingsService.test.ts` and `pnpm --filter frontend test src/routes/security` pass; confirms drag-end persistence deferral.
- Item 3: `pnpm --filter frontend test src/lib/components/watchlist/watchlist-security-picker.test.ts` passes; confirms out-of-order reversed search resolutions preserve only latest results.
- Item 4: `pnpm --filter frontend test src/lib/components/watchlist/watchlistService.test.ts` passes; confirms membership dedupe is a no-op without `createOrUpdateSecurity` or membership POST, and cross-watchlist additions reuse existing security IDs without sending `currency: 'USD'`.
- Item 5: `pnpm --filter frontend test src/lib/utils/finance/drawings.test.ts` and `pnpm --filter frontend test src/lib/services/ChartDrawingsService.test.ts` pass; confirms `normalizeSecurityDrawings`, `areDrawingPointsEqual`, and zero `patchPreferences` write-backs on legacy drawing load.
- Item 6: `pnpm --filter frontend test src/lib/components/watchlist/watchlistService.test.ts` and `pnpm --filter frontend test src/routes/watchlists/page.svelte.test.ts` pass; confirms service-level error clearing on success and error UI stability.
- Full verification: `./scripts/agent-test` passes with 0 lint errors, 0 type errors, and 100% passing tests.

**Risks / watch-outs:**
- In `WatchlistService.addSecurity`: Case sensitivity when comparing symbols/exchanges (use `.toUpperCase()` to ensure robust matching across uppercase and lowercase input).
- Svelte 5 reactivity: When clearing `this.error` at the start of mutations in `WatchlistService`, verify that calling `this.error = null` does not inadvertently mask error states of simultaneous operations (all mutations are async and triggered sequentially by UI actions).
- Duplicate DOM alert query in `page.svelte.test.ts`: When `create-watchlist-modal` is open and fails, suppressing the page-level alert via `!createOpen` prevents Testing Library's `findByText` from failing due to duplicate alert messages in the DOM.
