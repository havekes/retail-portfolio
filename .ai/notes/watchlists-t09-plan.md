# WATCHLISTS-T09 Implementation Plan

## Approach
Enrich `SecuritySchema` and `SqlAlchemyWatchlistRepository` with price and daily performance metrics queried via a single window-function query over `market_prices`, handling missing or single prices gracefully. Extend `UserPreferences` on both backend and frontend to persist `watchlist_order` and `watchlist_sort`, loading them in layout SSR and applying custom ordering to both sidebar navigation and the watchlists page. In `/watchlists`, display formatted prices with emerald/red pills, provide per-watchlist sort dropdown menus, enable HTML5 drag-and-drop watchlist reordering with a PageHeader toggle, and stabilize inline title editing using consistent container heights and alignment.

## Files
- `src/market/schema.py` — modify: add optional `current_price: Decimal | None = None`, `daily_price_change: Decimal | None = None`, and `daily_price_change_percent: Decimal | None = None` to `SecuritySchema`.
- `src/market/repository_sqlalchemy.py` — modify: implement batched price enrichment helper using a window query over `market_prices` (`func.row_number().over(partition_by=PriceModel.security_id, order_by=PriceModel.date.desc()) <= 2`) to enrich securities in `get_by_user`, `get_securities`, and mutation return paths (`rename`, `add_security_to_watchlist`, `remove_security_from_watchlist`).
- `src/account/api_types.py` — modify: add optional `watchlist_order: list[str] | None = None` and `watchlist_sort: dict[str, str] | None = None` to `UserPreferences`.
- `frontend/src/lib/api/marketService.ts` — modify: add optional `current_price?: number | null`, `daily_price_change?: number | null`, and `daily_price_change_percent?: number | null` to `SecuritySchema`.
- `frontend/src/lib/api/userPreferencesService.ts` — modify: add `watchlist_order?: string[] | null` and `watchlist_sort?: Record<string, string> | null` to `UserPreferences`.
- `frontend/src/routes/+layout.server.ts` — modify: extract `watchlist_order` and `watchlist_sort` from user preferences and pass them in layout data.
- `frontend/src/lib/components/watchlist/watchlist-utils.ts` — create: shared helpers for watchlist ordering (`sortWatchlistsByOrder`), security sorting (`sortSecurities`), and price/pill formatting (`formatPrice`, `formatPriceChangePercent`).
- `frontend/src/lib/components/watchlist/watchlist-utils.test.ts` — create: unit tests for sorting and price/pill formatting helpers.
- `frontend/src/lib/components/layout/app-sidebar-watchlist.svelte` — modify: apply `sortWatchlistsByOrder` to watchlists based on `watchlist_order` from context or layout data, appending unlisted watchlists gracefully.
- `frontend/src/lib/components/layout/app-sidebar.test-harness.svelte` — modify: support `initialWatchlistOrder` prop and provide it via context.
- `frontend/src/lib/components/layout/app-sidebar.test.ts` — modify: add unit tests verifying sidebar renders watchlists in the order specified by `watchlist_order`.
- `frontend/src/routes/watchlists/+page.svelte` — modify:
  - Add reorder mode toggle button in `PageHeader` actions snippet.
  - Fix inline title editing layout stability with consistent height (`h-10 min-h-10 flex items-center justify-between`) and matching line heights.
  - Add sort `DropdownMenu` in watchlist header actions allowing sorting by Name or Price Change (Gainers / Losers), immediately reordering securities and persisting `watchlist_sort` via `userPreferencesService.patchPreferences`.
  - Add HTML5 drag-and-drop reordering when reorder mode is active (draggable cards, `GripVertical` handle, drop reordering), updating display immediately and persisting `watchlist_order` via `userPreferencesService.patchPreferences`.
  - Display right-aligned formatted current price and daily price change percentage pill (emerald for positive, red for negative, muted for zero/missing) in each security row.
- `frontend/src/routes/watchlists/page.svelte.test.ts` — modify: add comprehensive tests for price & pill display with styling, sort submenu & persistence, reorder mode toggle & drag-and-drop reordering, sidebar ordering, and title editing stability.
- `tests/repositories/test_repository_sqlalchemy.py` — modify: add tests for `SqlAlchemyWatchlistRepository` price enrichment covering 0 prices (None values), 1 price (current_price with None change), 2+ prices (latest and previous close calculation), zero previous close defensive handling, and multiple securities in batched query.
- `tests/routers/test_accounts.py` — modify: add tests verifying `watchlist_order` and `watchlist_sort` roundtrip and partial patch persistence.

## Steps
1. **Update schemas and type contracts (Backend & Frontend):**
   - In `src/market/schema.py`, add `current_price: Decimal | None = None`, `daily_price_change: Decimal | None = None`, and `daily_price_change_percent: Decimal | None = None` to `SecuritySchema`.
   - In `src/account/api_types.py`, add `watchlist_order: list[str] | None = None` and `watchlist_sort: dict[str, str] | None = None` to `UserPreferences`.
   - In `frontend/src/lib/api/marketService.ts`, add `current_price?: number | null`, `daily_price_change?: number | null`, and `daily_price_change_percent?: number | null` to `SecuritySchema`.
   - In `frontend/src/lib/api/userPreferencesService.ts`, add `watchlist_order?: string[] | null` and `watchlist_sort?: Record<string, string> | null` to `UserPreferences`.
2. **Implement batched price enrichment in SqlAlchemyWatchlistRepository:**
   - In `src/market/repository_sqlalchemy.py`, create helper `_fetch_price_metrics(security_ids: Iterable[SecurityId]) -> dict[SecurityId, PriceMetrics]` querying `market_prices` using `func.row_number().over(partition_by=PriceModel.security_id, order_by=PriceModel.date.desc()) <= 2`.
   - Compute `current_price = latest.close`; if 2+ prices, compute `daily_price_change = latest.close - prev.close` and `daily_price_change_percent = ((latest.close - prev.close) / prev.close) * Decimal(100)` when `prev.close != 0`; handle 0 and 1 price cases cleanly.
   - Use `_enrich_watchlist`, `_enrich_watchlists`, and `_enrich_securities` to enrich models returned by `get_by_user`, `get_securities`, `rename`, `add_security_to_watchlist`, and `remove_security_from_watchlist`.
3. **Add backend test coverage:**
   - In `tests/repositories/test_repository_sqlalchemy.py`, write test functions verifying price enrichment for watchlist securities with 0 prices, 1 price, 2 prices, 3+ prices, zero previous close edge case, and multi-security batching.
   - In `tests/routers/test_accounts.py`, write test verifying `watchlist_order` and `watchlist_sort` roundtrip through PUT/PATCH and isolation across users.
4. **Create shared frontend watchlist utilities:**
   - Create `frontend/src/lib/components/watchlist/watchlist-utils.ts` with:
     - `sortWatchlistsByOrder(watchlists: WatchlistRead[], order: string[]): WatchlistRead[]` (unlisted watchlists appended gracefully).
     - `sortSecurities(securities: SecuritySchema[], sortKey: string): SecuritySchema[]` supporting `'name_asc'`, `'name_desc'`, `'price_change_desc'` (gainers), and `'price_change_asc'` (losers).
     - `formatPrice(price: number | null | undefined): string` (formatted with 2 decimals e.g. "50.25", or "-" when absent).
     - `formatPriceChangePercent(changePercent: number | null | undefined): string` (with sign prefix e.g. "+1.65%", "-0.82%", or "0.00%").
   - Create `frontend/src/lib/components/watchlist/watchlist-utils.test.ts` testing all sorting branches and formatting edge cases.
5. **Update layout server load and sidebar ordering:**
   - In `frontend/src/routes/+layout.server.ts`, extract `watchlist_order` and `watchlist_sort` from `prefService.getPreferences(token)` and return them in layout data.
   - In `frontend/src/lib/components/layout/app-sidebar-watchlist.svelte`, derive sorted watchlists using `sortWatchlistsByOrder(watchlistService?.watchlists || [], watchlistOrder)` where `watchlistOrder` comes from context or `$page.data.watchlist_order`.
   - In `frontend/src/lib/components/layout/app-sidebar.test-harness.svelte` and `app-sidebar.test.ts`, add prop/context for `initialWatchlistOrder` and test that sidebar renders watchlists matching `watchlist_order`.
6. **Implement Watchlists page features (`/watchlists/+page.svelte`):**
   - **Reorder mode & drag-and-drop:**
     - Add a reorder toggle button to `PageHeader` actions (`Reorder` / `Done`).
     - When active, render each watchlist with `draggable={true}` and a `GripVertical` handle icon.
     - On drop, reorder `watchlistOrder` and update `watchlistService.watchlists`, persisting `watchlist_order` via `userPreferencesService.patchPreferences`.
   - **Header layout stability & sort DropdownMenu:**
     - Fix watchlist section header container to `min-h-10 h-10 flex items-center justify-between gap-2` with matched line heights between view and edit modes to eliminate vertical jumps.
     - In header actions, add a sort `DropdownMenu` with trigger `ArrowUpDown` icon: options for Name (alphabetical) and Price Change (Gainers / Losers).
     - On sort selection, update local `watchlistSort[watchlist.id]` and persist `watchlist_sort` via `userPreferencesService.patchPreferences`, reactively reordering the security rows.
   - **Price and daily percentage change display:**
     - For each security row, display the formatted price and daily percentage change pill next to ticker and name.
     - Apply emerald styling (`text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border-emerald-500/20`) for positive changes, red styling (`text-rose-600 dark:text-rose-400 bg-rose-500/10 border-rose-500/20`) for negative changes, and muted styling for zero/absent values.
7. **Add frontend component tests (`page.svelte.test.ts`):**
   - Test current price and daily price change pill display with positive (emerald) and negative (red) styling.
   - Test sort `DropdownMenu` interaction: selecting Name or Price Change immediately sorts rows and calls `userPreferencesService.patchPreferences({ watchlist_sort: ... })`.
   - Test reorder mode toggle button and HTML5 drag-and-drop reordering, asserting display updates immediately and persists `watchlist_order`.
   - Test inline title editing toggle preserves container height/classes without jumping or collapsing action buttons unexpectedly.
8. **Run verification suite:**
   - Execute backend tests: `pytest tests/repositories/test_repository_sqlalchemy.py tests/routers/test_market.py tests/routers/test_accounts.py`.
   - Execute frontend typecheck: `npm --prefix frontend run check`.
   - Execute frontend linter: `npm --prefix frontend run lint`.
   - Execute frontend unit tests: `npm --prefix frontend run test:run`.

## Verification
- `pytest tests/repositories/test_repository_sqlalchemy.py -k test_watchlist_price_enrichment`: verifies 0, 1, and 2+ prices, zero prev close, and multi-security batching (Acceptance criteria 1, 2, 10).
- `pytest tests/routers/test_accounts.py -k test_preferences_watchlist_order_and_sort`: verifies `watchlist_order` and `watchlist_sort` preferences roundtrip and patch (Acceptance criteria 5, 7, 10).
- `npx --prefix frontend vitest run frontend/src/lib/components/watchlist/watchlist-utils.test.ts`: verifies watchlist ordering, security sorting, and price formatting helpers (Acceptance criteria 3, 4, 7, 8, 11).
- `npx --prefix frontend vitest run frontend/src/routes/watchlists/page.svelte.test.ts`: verifies price and pill display, sort dropdown behavior & preference persistence, reorder mode toggle & drag-and-drop reordering persistence, and title editing layout stability (Acceptance criteria 3, 4, 5, 6, 7, 9, 11).
- `npx --prefix frontend vitest run frontend/src/lib/components/layout/app-sidebar.test.ts`: verifies sidebar renders watchlists ordered according to `watchlist_order` (Acceptance criteria 8, 11).
- `npm --prefix frontend run check`: passes with zero TypeScript / Svelte check errors (Acceptance criterion 12).
- `npm --prefix frontend run lint`: passes with zero ESLint / Prettier errors (Acceptance criterion 12).
- `npm --prefix frontend run test:run`: full frontend test suite passes cleanly (Acceptance criterion 12).
- `./scripts/agent-test`: full repository test suite passes (Acceptance criterion 12).

## Risks / watch-outs:
- **Zero or missing previous close**: In `SqlAlchemyWatchlistRepository`, check `prev.close == 0` before calculating percentage change to avoid `ZeroDivisionError`. When only 1 price exists, return `current_price = latest.close` and `None` for price change fields.
- **SQL window function in batched query**: Using `row_number() over (partition by security_id order by date desc)` requires SQLite >= 3.25 (standard in Python 3.10+) and PostgreSQL; ensuring the subquery filters `rn <= 2` in one trip avoids N+1 queries.
- **Drag-and-Drop accessibility & mobile**: HTML5 drag events (`draggable`) should be disabled when reorder mode is off (`draggable={isReorderMode}`) so text selection and clicks on mobile/desktop work naturally.
- **Dynamic route shell discipline**: Avoid unquoted brackets in shell commands involving `/security/[security_id]`. Pass test file paths explicitly without bracket wildcards.
