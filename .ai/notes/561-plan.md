## Plan

**Approach:**
Extend `MarketService` with `getValuationsBatch` calling the batch valuation endpoint introduced in `F-VALUATION-T01` (`POST /market/securities/valuation/batch`), and fetch valuations for all displayed securities reactively in `frontend/src/routes/watchlists/+page.svelte`. Update `WATCHLIST_ROW_DATA_TRACKS` in `watchlist-utils.ts` to include a fixed-width valuation track on `md` screens and up, export canonical column headers (`WATCHLIST_HEADERS`), and render formatted price ranges (e.g. `20.00 – 50.00`) or em-dash (`—`) using a pure `formatValuationRange` utility.
Rejected alternative: Fetching valuations per individual security or storing them directly inside `WatchlistService.loadWatchlists` would introduce duplicate requests or couple layout-level sidebar/search usage to valuation data; a reactive batch lookup at the page view keeps data loading isolated and batch-efficient.

**Files:**
- `frontend/src/lib/api/marketService.ts` — modify: add `SecurityValuationRead` interface and `getValuationsBatch(securityIds: string[], token?: string | null): Promise<SecurityValuationRead[]>` method calling `/market/securities/valuation/batch`.
- `frontend/src/lib/api/marketService.test.ts` — modify: add unit tests for `getValuationsBatch` verifying batch endpoint request payload and empty array fast-path.
- `frontend/src/lib/components/watchlist/watchlist-utils.ts` — modify: update `WATCHLIST_ROW_DATA_TRACKS` to include the valuation column track on `md` breakpoints (`md:grid-cols-[minmax(0,1fr)_6.5rem_7.5rem_5rem_6rem]`), export `WATCHLIST_HEADERS` constant, and add `formatValuationRange(valuation)` helper.
- `frontend/src/lib/components/watchlist/watchlist-utils.test.ts` — modify: add unit tests for `formatValuationRange`, `WATCHLIST_HEADERS`, and updated `WATCHLIST_ROW_DATA_TRACKS`.
- `frontend/src/routes/watchlists/+page.svelte` — modify: add table header row with column titles, fetch valuation ranges via `getValuationsBatch` for unique security IDs in watchlists, and render valuation data cells with `title="Valuation"` in `<a>` row items.
- `frontend/src/routes/watchlists/page.svelte.test.ts` — modify: add `getValuationsBatch` to `mocks.client`, and add unit tests verifying valuation header rendering, formatted range display, fallback `"—"` display, responsive breakpoint classes, and batch endpoint invocation.

**Steps:**
1. Update `frontend/src/lib/api/marketService.ts`:
   - Define `SecurityValuationRead` interface matching backend schema:
     ```ts
     export interface SecurityValuationRead {
         id: number;
         user_id: string;
         security_id: string;
         lower_bound: number | string;
         upper_bound: number | string;
         created_at: string;
         updated_at: string;
     }
     ```
   - Add method `getValuationsBatch(securityIds: string[], token?: string | null): Promise<SecurityValuationRead[]>` to `MarketService`: returns `[]` immediately if `securityIds.length === 0`, otherwise makes a `POST /market/securities/valuation/batch` call with `{ security_ids: securityIds }`.
2. Add unit tests in `frontend/src/lib/api/marketService.test.ts`:
   - Test `getValuationsBatch`: returns empty array without network request when `securityIds` is empty.
   - Test `getValuationsBatch`: sends `POST /market/securities/valuation/batch` with `{ security_ids: ['s1', 's2'] }` and resolves parsed `SecurityValuationRead` list.
3. Update `frontend/src/lib/components/watchlist/watchlist-utils.ts`:
   - Update `WATCHLIST_ROW_DATA_TRACKS`:
     ```ts
     export const WATCHLIST_ROW_DATA_TRACKS =
         'grid grid-cols-[minmax(0,1fr)_5rem_6rem] gap-2 md:grid-cols-[minmax(0,1fr)_6.5rem_7.5rem_5rem_6rem]';
     ```
     Update documentation comment noting the 5 tracks on `md`: symbol/name (fluid), date added (`md` and up), valuation range (`md` and up), price, and % change pill.
   - Export `WatchlistColumnHeader` type and `WATCHLIST_HEADERS` constant:
     ```ts
     export interface WatchlistColumnHeader {
         id: string;
         label: string;
         headerClass?: string;
     }

     export const WATCHLIST_HEADERS: readonly WatchlistColumnHeader[] = [
         { id: 'security', label: 'Security' },
         { id: 'date_added', label: 'Added', headerClass: 'hidden md:block' },
         { id: 'valuation', label: 'Valuation', headerClass: 'hidden md:block justify-self-end' },
         { id: 'price', label: 'Price', headerClass: 'justify-self-end' },
         { id: 'change', label: 'Change', headerClass: 'justify-self-end' }
     ] as const;
     ```
   - Implement `formatValuationRange(valuation?: { lower_bound?: number | string | null; upper_bound?: number | string | null } | null): string`:
     - Returns `'—'` (em dash `\u2014`) if `valuation` is null, undefined, or either bound is null/undefined/empty string.
     - Formats bounds via `formatPrice`: if either bound formats to `'-'`, returns `'—'`.
     - Returns formatted string `${lower} – ${upper}` with en dash (`\u2013`) and spaces.
4. Add unit tests in `frontend/src/lib/components/watchlist/watchlist-utils.test.ts`:
   - Test `formatValuationRange`:
     - Formats numbers e.g. `{ lower_bound: 20, upper_bound: 50 }` -> `'20.00 – 50.00'`.
     - Formats strings e.g. `{ lower_bound: '20.00', upper_bound: '50.50' }` -> `'20.00 – 50.50'`.
     - Handles null, undefined, partial bounds, non-numeric strings, and returns `'—'`.
   - Test `WATCHLIST_HEADERS`:
     - Asserts presence and order of headers: security, date_added, valuation, price, change.
   - Test `WATCHLIST_ROW_DATA_TRACKS`:
     - Asserts presence of `md:grid-cols-[minmax(0,1fr)_6.5rem_7.5rem_5rem_6rem]`.
5. Update `frontend/src/routes/watchlists/+page.svelte`:
   - Import `getMarketService`, `type SecurityValuationRead` from `$lib/api/marketService` and `formatValuationRange` from `$lib/components/watchlist/watchlist-utils`.
   - Instantiate market client `const marketService = getMarketService()`.
   - Add state `let valuations = $state<Record<string, SecurityValuationRead>>({})`.
   - Derive unique security IDs:
     `const securityIds = $derived([...new Set(watchlists.flatMap((w) => w.securities.map((s) => s.id)))]);`
   - In a reactive `$effect`:
     - If `securityIds` is empty, reset `valuations = {}`.
     - Otherwise, call `marketService.getValuationsBatch(ids)`. On success, populate `valuations` map keyed by `security_id`. Guard with cancellation token to avoid stale async state.
   - Add table header above `<ul>` for watchlists that have securities (`watchlist.securities.length > 0`):
     ```svelte
     <div class="flex items-center gap-2 px-2 text-xs font-medium text-muted-foreground" aria-hidden="true">
         {#if isSecurityReorderActive(watchlist)}
             <span class="h-4 w-4 shrink-0"></span>
         {/if}
         <div class={cn(WATCHLIST_ROW_DATA_TRACKS, 'flex-1 px-2')}>
             <span>Security</span>
             <span class="hidden md:block">Added</span>
             <span class="hidden md:block justify-self-end">Valuation</span>
             <span class="justify-self-end">Price</span>
             <span class="justify-self-end">Change</span>
         </div>
         <span class="h-8 w-8 shrink-0"></span>
     </div>
     ```
   - In each security row `<a>` link, insert the valuation data cell between Date Added and Price:
     ```svelte
     <span
         class="hidden truncate text-xs text-muted-foreground md:block justify-self-end tabular-nums"
         title="Valuation"
     >
         {formatValuationRange(valuations[security.id])}
     </span>
     ```
6. Update `frontend/src/routes/watchlists/page.svelte.test.ts`:
   - In `mocks.client`, add `getValuationsBatch: vi.fn().mockResolvedValue([])`. In `beforeEach`, ensure `mocks.client.getValuationsBatch.mockResolvedValue([])` resets cleanly.
   - Add test: verifies Valuation column header is rendered in watchlist table headers with `hidden md:block`.
   - Add test: verifies security row renders formatted valuation range (e.g. `'20.00 – 50.00'`) when valuation data is returned from `getValuationsBatch`.
   - Add test: verifies security row renders `'—'` when no valuation is set for that security.
   - Add test: verifies valuation cell has classes `hidden md:block` and `justify-self-end`.
   - Add test: verifies `mocks.client.getValuationsBatch` is invoked with security IDs from loaded watchlists.

**Verification:**
- Criterion 1 (Watchlist rows include a Valuation column displaying price range or "—"):
  - Run `npx vitest run frontend/src/routes/watchlists/page.svelte.test.ts` — verify assertions pass for formatted price range (`20.00 – 50.00`) and fallback (`—`).
- Criterion 2 (Grid columns in WATCHLIST_ROW_DATA_TRACKS and table headers updated to accommodate the new column):
  - Run `npx vitest run frontend/src/lib/components/watchlist/watchlist-utils.test.ts` — verify `WATCHLIST_ROW_DATA_TRACKS` contains `7.5rem` track and `WATCHLIST_HEADERS` includes valuation.
  - Run `npx vitest run frontend/src/routes/watchlists/page.svelte.test.ts` — verify header row renders "Valuation" column.
- Criterion 3 (Responsive layout preserves alignment across breakpoints):
  - Verify valuation column header and row cell share `hidden md:block justify-self-end`, matching `md:grid-cols-[minmax(0,1fr)_6.5rem_7.5rem_5rem_6rem]`.
  - Verify row links match `WATCHLIST_ROW_DATA_TRACKS` classes across all items.
- Criterion 4 (Unit tests in watchlists/page.svelte.test.ts and watchlist-utils.test.ts pass):
  - Run `npx vitest run frontend/src/routes/watchlists/page.svelte.test.ts frontend/src/lib/components/watchlist/watchlist-utils.test.ts` (all pass).
- Criterion 5 (Build passes and relevant tests pass):
  - Run `npm run check` and `npm run test` in `frontend/`.

**Risks / watch-outs:**
- Test mock completeness: Existing tests in `page.svelte.test.ts` mock `getMarketService()`. Adding `getValuationsBatch: vi.fn().mockResolvedValue([])` to `mocks.client` avoids `TypeError: marketService.getValuationsBatch is not a function` during page render.
- Title collisions in DOM queries: Existing tests query `screen.getAllByTitle('Added')`. The header element must not carry `title="Added"`, and the valuation cell should use `title="Valuation"` to preserve deterministic element selection.
- Distinct dash types: Range uses en-dash `–` (`\u2013`) with spaces e.g. `20.00 – 50.00`; missing valuation uses em-dash `—` (`\u2014`).
