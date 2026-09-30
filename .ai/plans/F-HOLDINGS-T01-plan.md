# Implementation Plan - F-HOLDINGS-T01: Add % of total portfolio column and % of account badge

## Approach
Implement allocation percentage metrics (`calculatePercentOfTotal`, `calculatePercentOfAccount`, `formatHoldingPercent`) in `holdings-metrics.ts`, configure a new `'percent_of_total'` column immediately adjacent to `'total_value'` in `holdings-table-columns.ts`, and update `holdings-table.svelte` to derive total portfolio value and account total values to render the `% of Total` column and account badges with clean 1-decimal formatting (e.g. `14.2%`). This purely frontend approach preserves table configuration normalization, supports column resizing and sorting, seamlessly handles both ungrouped and "Group by stock" modes, and maintains backwards compatibility with existing table preferences.

## Files
- `frontend/src/lib/utils/finance/holdings-metrics.ts` — modify: Add `calculatePercentOfTotal(holdingValue: number, totalPortfolioValue: number): number`, `calculatePercentOfAccount(holdingValue: number, accountTotalValue: number): number`, and `formatHoldingPercent(value: number | null | undefined): string` (formatting to 1 decimal place, e.g. `14.2%`, or `'-'` on null/undefined/non-finite).
- `frontend/src/lib/utils/finance/holdings-metrics.test.ts` — modify: Add unit tests for `calculatePercentOfTotal`, `calculatePercentOfAccount`, and `formatHoldingPercent` covering regular inputs, zero totals, negative/non-finite numbers, and clean 1-decimal place percentage formatting.
- `frontend/src/lib/components/holdings/holdings-table-columns.ts` — modify: Add `'percent_of_total'` to `HOLDINGS_TABLE_COLUMN_IDS` right after `'total_value'`, define column definition `{ id: 'percent_of_total', label: '% of Total', alignRight: true }` in `HOLDINGS_TABLE_COLUMNS`, and configure default (120), min (90), and max (200) widths in `HOLDINGS_TABLE_DEFAULT_WIDTHS`, `HOLDINGS_TABLE_COLUMN_MIN_WIDTHS`, and `HOLDINGS_TABLE_COLUMN_MAX_WIDTHS`.
- `frontend/src/lib/components/holdings/holdings-table-columns.test.ts` — modify: Add unit tests for `percent_of_total` width clamping, column configuration, visibility toggling, and config normalization.
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: Derive `totalPortfolioValue` (sum of `h.total_value` across `holdings`) and `accountTotals` map (sum of `h.total_value` per account); populate `percent_of_total` and `accounts` (with `name`, `account_id`, and `percent_of_account`) on `HoldingRowView` for flat and grouped rows; support sorting by `percent_of_total` in `valueFor`; render the `% of Total` cell adjacent to `total_value` with `formatHoldingPercent`; render account badges displaying the holding's percentage of account value cleanly formatted.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: Update column count assertion from 9 to 10 and cell index assertions; add unit tests for `% of Total` column presence and value calculation adjacent to Total Value, sorting by `% of Total`, Account column badge percentage display for individual holdings and grouped stock holdings, and 1-decimal percentage formatting.

## Steps
1. In `frontend/src/lib/utils/finance/holdings-metrics.ts`, implement:
   - `calculatePercentOfTotal(holdingValue: number, totalPortfolioValue: number): number`: returns `(holdingValue / totalPortfolioValue) * 100` if `totalPortfolioValue > 0` and inputs are finite, else `0`.
   - `calculatePercentOfAccount(holdingValue: number, accountTotalValue: number): number`: returns `(holdingValue / accountTotalValue) * 100` if `accountTotalValue > 0` and inputs are finite, else `0`.
   - `formatHoldingPercent(value: number | null | undefined): string`: returns `${value.toFixed(1)}%` if `value` is finite, else `'-'`.
2. In `frontend/src/lib/utils/finance/holdings-metrics.test.ts`, add test suites for `calculatePercentOfTotal`, `calculatePercentOfAccount`, and `formatHoldingPercent` testing standard calculations, division-by-zero protection, non-finite values, and 1-decimal formatting (e.g. `14.2%`).
3. In `frontend/src/lib/components/holdings/holdings-table-columns.ts`:
   - Add `'percent_of_total'` to `HOLDINGS_TABLE_COLUMN_IDS` immediately after `'total_value'`.
   - Add `{ id: 'percent_of_total', label: '% of Total', alignRight: true }` to `HOLDINGS_TABLE_COLUMNS` immediately after `'total_value'`.
   - Add `percent_of_total: 120` to `HOLDINGS_TABLE_DEFAULT_WIDTHS`.
   - Add `percent_of_total: 90` to `HOLDINGS_TABLE_COLUMN_MIN_WIDTHS`.
   - Add `percent_of_total: 200` to `HOLDINGS_TABLE_COLUMN_MAX_WIDTHS`.
4. In `frontend/src/lib/components/holdings/holdings-table-columns.test.ts`:
   - Add clamp tests for `percent_of_total` (at min 90, max 200, within bounds, and NaN fallback to 120).
   - Verify `HOLDINGS_TABLE_COLUMNS` includes `percent_of_total` with label `'% of Total'` and `alignRight: true` immediately after `'total_value'`.
   - Verify `toggleColumnVisibility` and `normalizeHoldingsTableConfig` correctly preserve and normalize `percent_of_total`.
5. In `frontend/src/lib/components/holdings/holdings-table.svelte`:
   - Import `calculatePercentOfTotal`, `calculatePercentOfAccount`, and `formatHoldingPercent` from `$lib/utils/finance/holdings-metrics`.
   - Add derived `totalPortfolioValue = $derived(holdings.reduce((sum, h) => sum + (h.total_value ?? 0), 0))`.
   - Add derived `accountTotals = $derived.by(...)` mapping account identifier (`h.account_name || h.account_id`) to the sum of `h.total_value`.
   - Define `HoldingAccountBadge` type `{ name: string; account_id?: string; percent_of_account: number }`.
   - Update `HoldingRowView` to include `percent_of_total: number` and `accounts: HoldingAccountBadge[]`.
   - In `baseRows`:
     - For ungrouped mode: compute `percent_of_total` using `calculatePercentOfTotal(row.total_value, totalPortfolioValue)`; build `accounts` with `percent_of_account = calculatePercentOfAccount(row.total_value, accountTotals.get(row.account_name || row.account_id) ?? 0)`.
     - For grouped mode (`groupBy === 'stock' || groupBy === 'company'`): compute `percent_of_total` using `calculatePercentOfTotal(g.total_value, totalPortfolioValue)`; aggregate `g.rows` by account to sum each account's portion of the holding, and compute each account's `percent_of_account = calculatePercentOfAccount(accountHoldingValue, accountTotals.get(accountKey) ?? 0)`.
   - In `valueFor`: return `row.percent_of_total` when `column === 'percent_of_total'` to enable numeric sorting.
   - In `holdingRow`:
     - Render `account-cell`: for each account badge, display the account name and formatted percentage inside the badge (`<span>{account.name}</span> <span class="ml-1 text-muted-foreground/70">{formatHoldingPercent(account.percent_of_account)}</span>`).
     - Render `percent_of_total` cell immediately after `total_value` with `data-testid="percent-of-total-cell"` displaying `<span data-testid="percent-of-total" class="text-xs font-medium tabular-nums">{formatHoldingPercent(row.percent_of_total)}</span>`.
6. In `frontend/src/lib/components/holdings/holdings-table.test.ts`:
   - Update default column count assertion from 9 to 10 (line 730) and adjust trailing cell indices for `aCells` (lines 426-428) to account for the new column at index 6.
   - Add unit test: `renders "% of Total" column immediately adjacent to Total Value with correct portfolio percentage formatted to 1 decimal place (e.g. 14.2%)`.
   - Add unit test: `sorts holdings table by "% of Total" column ascending and descending`.
   - Add unit test: `renders account badge with holding percentage of account value for single holding and multiple holdings within the same account`.
   - Add unit test: `renders account badges with respective account holding percentages in "Group by stock" mode`.
7. Verify all acceptance criteria, linting, type checks, and unit tests pass across the entire frontend.

## Verification
- `npm --prefix frontend run test:run src/lib/utils/finance/holdings-metrics.test.ts`: Verify `calculatePercentOfTotal`, `calculatePercentOfAccount`, and `formatHoldingPercent` unit tests pass.
- `npm --prefix frontend run test:run src/lib/components/holdings/holdings-table-columns.test.ts`: Verify column configuration, widths, clamping, and visibility toggle tests pass.
- `npm --prefix frontend run test:run src/lib/components/holdings/holdings-table.test.ts`: Verify `% of Total` column presence, position adjacent to Total Value, sorting, account badge percentage display, and 10-column header tests pass.
- `npm --prefix frontend run test:run src/routes/holdings/page.svelte.test.ts`: Verify route page holdings tests pass with the new column available.
- `npm --prefix frontend run check`: Verify SvelteKit type checking passes with zero errors.
- `npm --prefix frontend run lint`: Verify ESLint and Prettier checks pass.
- `npm --prefix frontend run test:run`: Verify all frontend tests pass without regression.
- `npm --prefix frontend run build`: Verify the production frontend build completes successfully.

## Risks / watch-outs
- **Account Identification Keying**: In test fixtures and mock rows, `account_id` defaults to a shared string (e.g. `'acc-test-1'`) while `account_name` differentiates accounts. Account totals must key on `account_name || account_id` so mock tests and real accounts both aggregate independently.
- **Zero/Empty Portfolio and Account Totals**: Division by zero must be guarded in both `calculatePercentOfTotal` and `calculatePercentOfAccount`, returning `0` (formatted as `0.0%`) rather than `NaN` or `Infinity`.
- **Existing Cell/Column Index Tests in `holdings-table.test.ts`**: Inserting a column at index 6 shifts subsequent columns (`profit_loss` to 7, `ew_primary_target` to 8, `ew_cycle_target` to 9). Hardcoded cell indices at line 426 and header count at line 730 must be updated to avoid test breakages.
- **Account Badge Querying**: Account badges should contain `<span>{account.name}</span>` so tests searching for exact text `within(cell).getByText('TFSA')` continue to succeed while displaying the percentage alongside.
- **Table Preference Normalization**: Saved user preferences with missing `percent_of_total` width or visibility will be safely merged via `normalizeHoldingsTableConfig` using defaults.
