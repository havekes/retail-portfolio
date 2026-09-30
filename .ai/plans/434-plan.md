## Plan

**Approach:**
Refactor the holdings table and finance grouping utilities to replace collapsible accordion rows with a flat "Group by stock" view where each stock renders strictly as a single table row with combined account badges (`Badge variant="secondary"`), CAD aggregations (summed quantity, total value, profit/loss, and weighted converted average cost), and native column sorting. Update security link hover styling to rounded backgrounds (`hover:bg-muted/80 rounded-md` with `group-hover:underline` removed), convert the P/L % column to a watchlist-style pill badge with emerald/rose/muted tints, and invert USD/CAD dual-currency display ordering so CAD appears on top with native USD beneath, displaying only native USD for price.

**Files:**
- `frontend/src/lib/utils/finance/holdings-group.ts` — modify: Update `HoldingsGroupMode` to `'none' | 'stock' | 'company'`; update `groupHoldings` so stock grouping keys strictly on `security_id` (one row per stock) and aggregates quantity, CAD total value, CAD profit/loss, weighted CAD converted average cost, weighted native average cost, unconverted values, and distinct account names.
- `frontend/src/lib/components/holdings/holdings-group-prefs.ts` — modify: Update `normalizeHoldingsGroupMode` to accept both `'stock'` and `'company'` (normalizing to `'stock'` or preserving valid modes), defaulting to `'none'`.
- `frontend/src/lib/components/holdings/holdingsService.svelte.ts` — modify: Support `'stock'` and `'company'` in `setGroupBy`, maintaining reactivity on `groupedHoldings`.
- `frontend/src/routes/holdings/+page.svelte` — modify: Update toggle label to "Group by stock" (`id="group-by-stock"`, `data-testid="group-by-stock"`), toggle and persist `'stock'` / `'none'`, and pass `groupBy="stock"` to `HoldingsTable`.
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: Remove accordion collapsible headers (`group-header` / `group-row`) and render strictly one row per stock in grouped mode; display account badges via `<Badge variant="secondary">` (showing combined badges in grouped mode); replace symbol `group-hover:underline` with anchor `hover:bg-muted/80 rounded-md`; style P/L % column as a watchlist pill badge (`inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums`) with emerald/rose/muted tints while keeping dollar P/L text-only; invert USD/CAD display (CAD on top in primary font, native USD on bottom in secondary font) for total value, avg cost, and profit/loss; display only native USD price for `latest_price` without CAD line; sort aggregated stock rows in grouped mode and individual holding rows in flat mode across all columns.
- `frontend/src/lib/utils/finance/holdings-group.test.ts` — modify: Update tests for stock-based grouping keyed on `security_id`, single group per stock across accounts, CAD aggregation, weighted cost calculations, combined account names, and support for `'stock'` mode.
- `frontend/src/lib/components/holdings/holdings-group-prefs.test.ts` — modify: Test `normalizeHoldingsGroupMode` with `'stock'`, `'company'`, and invalid inputs.
- `frontend/src/lib/components/holdings/holdingsService.test.ts` — modify: Verify `HoldingsService` supports `'stock'` group mode.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: Update tests to verify rounded hover styling (no `group-hover:underline`), single and combined `<Badge variant="secondary">` account badges, watchlist pill styling for positive/negative/zero/null P/L %, text-only dollar P/L, inverted USD/CAD ordering, price single native currency display, flat grouped mode with strictly one row per stock and no accordion headers, and column sorting in both flat and grouped modes.
- `frontend/src/routes/holdings/page.svelte.test.ts` — modify: Update tests to verify "Group by stock" label and testid, grouped rendering without accordion headers, toggle behavior without refetching, and persistence of `'stock'`.

**Steps:**
1. **Update grouping models & aggregation logic (`holdings-group.ts`):**
   - Update `HoldingsGroupMode` to `'none' | 'stock' | 'company'`.
   - Update `HoldingsGroup` type to include `id`, `security_id`, `security_currency`, `unconverted_total_value`, `converted_average_cost`, `unconverted_profit_loss`, `latest_price`, `price_date`, `account_names: string[]`.
   - In `groupHoldings`, when `mode === 'stock' || mode === 'company'`:
     - Key groups by `row.security_id` (strictly one group per stock).
     - For each group, sum `quantity`, sum CAD `total_value`, sum native `unconverted_total_value`, sum CAD `profit_loss`, and sum native `unconverted_profit_loss`.
     - Compute weighted CAD average cost: `sum(quantity * converted_average_cost) / sum(quantity)` for non-null rows.
     - Compute weighted native average cost: `sum(quantity * average_cost) / sum(quantity)` for non-null rows.
     - Collect distinct non-empty `account_names: string[]`.
     - Set `currency: 'CAD'`, `security_currency: firstRow.security_currency`, and `latest_price: firstRow.latest_price`.
   - When `mode === 'none'`, return 1:1 groups preserving original order with `account_names: row.account_name ? [row.account_name] : []`.
2. **Update preferences and service layers (`holdings-group-prefs.ts`, `holdingsService.svelte.ts`):**
   - In `holdings-group-prefs.ts`, update `normalizeHoldingsGroupMode(raw: unknown)` to return `'stock'` if `raw === 'stock' || raw === 'company'`, else `'none'` (or preserve valid modes).
   - In `holdingsService.svelte.ts`, update `setGroupBy` signature and implementation to handle `HoldingsGroupMode`.
3. **Update holdings route (`frontend/src/routes/holdings/+page.svelte`):**
   - Change toggle checkbox id and `data-testid` to `group-by-stock`.
   - Change label text to "Group by stock".
   - Set `checked={service.groupBy === 'stock' || service.groupBy === 'company'}`.
   - Update `handleGroupToggle`: if checked, set and save `'stock'`; if unchecked, set and save `'none'`.
   - Pass `groupBy={service.groupBy === 'stock' || service.groupBy === 'company' ? 'stock' : null}` to `HoldingsTable`.
4. **Refactor `HoldingsTable` layout and aggregation (`holdings-table.svelte`):**
   - Remove accordion header rows (`group-header` button, `group-row` table row, `collapsedGroups`, `toggleGroup`, `groupTotals`).
   - Define row view mapping for flat rows vs grouped stock rows:
     - Grouped: call `groupHoldings(holdings, 'stock')` to get aggregated stock rows.
     - Flat: map each `UserHolding` to a row view with `account_names: row.account_name ? [row.account_name] : []`.
   - Derive `displayRows` by sorting aggregated stock rows (when grouped) or flat rows (when flat) by `sortColumn` and `sortDirection`, keeping null/undefined cells last in both directions.
   - In table body, render strictly `displayRows` using `{#each displayRows as row (row.id)} {@render holdingRow(row)} {/each}`.
5. **Update table cell styling and formatting (`holdings-table.svelte`):**
   - **Security link hover styling:** On the `<a data-testid="security-link">` element, add `rounded-md px-1.5 py-1 -mx-1.5 -my-1 transition-colors hover:bg-muted/80`; remove `group-hover:underline` from the symbol `<span>`.
   - **Account badges:** Import `Badge` from `$lib/components/ui/badge/index.js`. In the `account_name` cell, if `row.account_names.length === 0`, render `-`. Otherwise, render `<div class="flex flex-wrap items-center gap-1">` containing `<Badge variant="secondary">{name}</Badge>` for each name.
   - **USD/CAD currency display ordering:** For `total_value`, `average_cost`, and `profit_loss` when `row.security_currency !== row.currency`:
     - `total_value`: top primary line renders CAD `row.total_value`; bottom secondary line renders native USD `row.unconverted_total_value`.
     - `average_cost`: top primary line renders CAD `row.converted_average_cost`; bottom secondary line renders native USD `row.average_cost`.
     - `profit_loss`: top primary line renders CAD `row.profit_loss` (colored with sign prefix); bottom secondary line renders native USD `row.unconverted_profit_loss` (colored with sign prefix).
   - **Price display:** For `latest_price`, render only the native price `formatCurrency(row.latest_price, row.security_currency)`. Remove the converted CAD secondary line.
   - **Watchlist-style P/L % pill:** Style `profit_loss_percent` using watchlist pill badge classes `inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums` with `getPillClass`: emerald styling for > 0, rose styling for < 0, and muted styling (`text-muted-foreground bg-muted/40 border-border/40`) for zero or null.
   - **Dollar Profit/Loss:** Retain colored text styling (`text-sm tabular-nums text-emerald-600` / `text-rose-600`) without pill badge containers.
6. **Update unit and component tests:**
   - In `holdings-group.test.ts`: test single group per stock across accounts, CAD aggregation, weighted cost calculations, combined account names, and support for `'stock'` mode.
   - In `holdings-group-prefs.test.ts`: test `normalizeHoldingsGroupMode` with `'stock'`, `'company'`, and invalid inputs.
   - In `holdingsService.test.ts`: test `'stock'` group mode.
   - In `holdings-table.test.ts`:
     - Test security link hover styling (`hover:bg-muted/80 rounded-md` and no `group-hover:underline`).
     - Test account badges in flat mode (`<Badge variant="secondary">` and `-` for blank) and combined badges in grouped mode.
     - Test P/L % watchlist pill badge styling for positive, negative, and zero/null values.
     - Test dollar P/L text styling without pill wrapper.
     - Test dual-currency display (CAD top, USD bottom for value/cost/PL; only native USD for price).
     - Test "Group by stock" mode: strictly one row per stock, no accordion headers, aggregated CAD totals.
     - Test column sorting on aggregated stock rows in grouped mode and single rows in flat mode.
   - In `page.svelte.test.ts`:
     - Test "Group by stock" label and testid.
     - Test toggle merges rows into single rows per stock with combined badges without refetching.
     - Test toggle off restores flat rows.
     - Test persistence of `'stock'` preference.
7. **Run verification suite:**
   - Execute vitest tests, type check (`svelte-check`), linter (`prettier` / `eslint`), and build.

**Verification:**
- `pnpm -C frontend test:unit src/lib/utils/finance/holdings-group.test.ts`: verify stock grouping, CAD aggregations, weighted average costs, and combined account names (Acceptance criteria 2, 4).
- `pnpm -C frontend test:unit src/lib/components/holdings/holdings-group-prefs.test.ts src/lib/components/holdings/holdingsService.test.ts`: verify preferences and service support `stock` / `company` modes (Acceptance criterion 2).
- `pnpm -C frontend test:unit src/lib/components/holdings/holdings-table.test.ts`: verify security hover styling without underline (AC 1), flat group by stock without accordion headers (AC 3), CAD aggregations (AC 4), account badges and combined badges (AC 5), watchlist-style P/L % pill badge (AC 6), text-only dollar P/L (AC 7), USD/CAD ordering and price display (AC 8), and column sorting on aggregated stock rows and flat rows (AC 9).
- `pnpm -C frontend test:unit src/routes/holdings/page.svelte.test.ts`: verify "Group by stock" toggle label, state persistence, and flat stock row rendering (Acceptance criteria 2, 3, 5, 10).
- `pnpm -C frontend check`: passes with zero TypeScript / Svelte errors (Acceptance criteria 10, 11).
- `pnpm -C frontend lint`: passes with zero ESLint and Prettier errors (Acceptance criteria 10, 11).
- `pnpm -C frontend build`: production build succeeds without errors (Acceptance criterion 11).

**Risks / watch-outs:**
- Backward compatibility for stored user preference: users who already have `holdings_group: 'company'` stored in the database must have their preference honored as grouped without falling back to flat mode.
- Inverted currency order: ensure `unconverted_*` values represent native security currency (USD) and standard `total_value` / `converted_average_cost` / `profit_loss` represent converted CAD values from the backend.
- Account badge wrap: when a stock is held in several accounts, combined badges in the account column should wrap gracefully (`flex flex-wrap items-center gap-1`) without breaking table layout.
