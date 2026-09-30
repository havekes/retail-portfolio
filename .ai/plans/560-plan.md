# Implementation Plan - Issue #560: Add valuation range column to holdings table

## Approach
Add `valuation_range` as a canonical column to `HOLDINGS_TABLE_COLUMNS` with dedicated min/max/default widths and visibility preferences. In `HoldingsService.load()`, fetch valuations in batch for all unique holding securities using a new `MarketService.getValuationsBatch()` endpoint wrapper. In `HoldingsTable`, map valuation bounds to rows, display formatted price ranges (e.g. `20.00 – 50.00`) or em dash `—` when unset using a reusable `formatValuationRange` utility, and support column resizing, preference toggling, and numeric sorting by range midpoint with nulls sorted last.

## Files
- `frontend/src/lib/api/marketService.ts` — modify: Define `SecurityValuation` interface and add `getValuationsBatch(securityIds: string[], token?: string | null): Promise<SecurityValuation[]>` making `POST /market/securities/valuation/batch`.
- `frontend/src/lib/api/marketService.test.ts` — modify: Add unit tests for `getValuationsBatch` testing empty input bypass, payload dispatch, and response parsing.
- `frontend/src/lib/utils/finance/valuation.ts` — create: Implement `formatValuationRange(lowerBound?: number | null, upperBound?: number | null): string` returning `lower – upper` formatted with 2 decimal places and en dash, or `—` (em dash) when undefined/null/non-finite.
- `frontend/src/lib/utils/finance/valuation.test.ts` — create: Add unit tests for `formatValuationRange` covering standard ranges, currency-less decimal formatting with commas, and null/undefined/NaN empty handling.
- `frontend/src/lib/components/holdings/holdings-table-columns.ts` — modify: Add `'valuation_range'` to `HOLDINGS_TABLE_COLUMN_IDS`, configure `{ id: 'valuation_range', label: 'Valuation Range', alignRight: true }` in `HOLDINGS_TABLE_COLUMNS`, and define widths (default: 160, min: 120, max: 260).
- `frontend/src/lib/components/holdings/holdings-table-columns.test.ts` — modify: Add unit tests for `valuation_range` column configuration, default width, clamping bounds, and visibility toggling.
- `frontend/src/lib/components/holdings/holdingsService.svelte.ts` — modify: Instantiate `MarketService`, add `valuations = $state<Record<string, SecurityValuation>>({})`, and in `load()`, extract distinct `security_id`s to fetch batch valuations non-fatally.
- `frontend/src/lib/components/holdings/holdingsService.test.ts` — modify: Add unit tests for batch valuation fetching, mapping by `security_id`, and graceful fallback to empty valuations on fetch failure.
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: Add optional `valuations?: Record<string, SecurityValuation> | null` prop, populate `valuation_lower` and `valuation_upper` on `HoldingRowView` for ungrouped and grouped rows, implement numeric sorting by midpoint in `valueFor`, and render the `valuation_range` data cell with `formatValuationRange` or `—`.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: Update total column count expectations and add unit tests for Valuation Range formatting (`20.00 – 50.00` and `—`), numeric sorting (asc, desc, nulls last), and column resizing.
- `frontend/src/routes/holdings/+page.svelte` — modify: Pass `valuations={service.valuations}` to `<HoldingsTable>`.
- `frontend/src/routes/holdings/page.svelte.test.ts` — modify: Mock `getMarketService` and verify that the `Valuation Range` column toggle works in view options and persists to user preferences.

## Steps
1. In `frontend/src/lib/api/marketService.ts`, define `SecurityValuation` interface and implement `getValuationsBatch(securityIds: string[], token?: string | null)` calling `POST /market/securities/valuation/batch`. Add corresponding unit tests in `frontend/src/lib/api/marketService.test.ts`.
2. Create `frontend/src/lib/utils/finance/valuation.ts` implementing `formatValuationRange(lowerBound?: number | null, upperBound?: number | null): string` using `en-CA` number formatting with 2 decimal places and en dash separator (` \u2013 `), returning em dash (`\u2014`) when either bound is missing or non-finite. Add tests in `frontend/src/lib/utils/finance/valuation.test.ts`.
3. In `frontend/src/lib/components/holdings/holdings-table-columns.ts`, add `'valuation_range'` to `HOLDINGS_TABLE_COLUMN_IDS`, configure the column in `HOLDINGS_TABLE_COLUMNS` with label `'Valuation Range'` and `alignRight: true`, and add width configuration (default: 160, min: 120, max: 260) in `HOLDINGS_TABLE_DEFAULT_WIDTHS`, `HOLDINGS_TABLE_COLUMN_MIN_WIDTHS`, and `HOLDINGS_TABLE_COLUMN_MAX_WIDTHS`. Update tests in `frontend/src/lib/components/holdings/holdings-table-columns.test.ts`.
4. In `frontend/src/lib/components/holdings/holdingsService.svelte.ts`, inject `MarketService` via `getMarketService(customFetch)`, add reactive `valuations = $state<Record<string, SecurityValuation>>({})`, and in `load()`, extract unique non-empty `security_id`s from loaded holdings to call `getValuationsBatch()`. Wrap in try/catch so valuation lookup failures do not fail the holdings load. Add unit tests in `frontend/src/lib/components/holdings/holdingsService.test.ts`.
5. In `frontend/src/lib/components/holdings/holdings-table.svelte`, accept `valuations` prop, map `valuation_lower` and `valuation_upper` into `HoldingRowView` for both grouped (`groupBy: 'stock'`) and flat views, update `valueFor` to compute the range midpoint for numeric sorting, and render the `valuation_range` table cell with `formatValuationRange` or em dash `—` when null.
6. In `frontend/src/routes/holdings/+page.svelte`, wire `valuations={service.valuations}` into `<HoldingsTable>`. Update `frontend/src/routes/holdings/page.svelte.test.ts` to mock `getMarketService` and verify that the Valuation Range column toggle appears in the settings dropdown menu and triggers preference persistence.
7. In `frontend/src/lib/components/holdings/holdings-table.test.ts`, update the total column header count assertion from 9 to 10. Add unit tests verifying:
   - Rendering formatted valuation ranges for securities with valuations and `—` for securities without.
   - Sorting by Valuation Range ascending and descending, verifying numeric ordering and that unvalued securities sort last in both directions.
   - Column resizing via `column-resize-valuation_range` handle within [120, 260] bounds.
   - Display and sorting in "Group by stock" mode with valuations.

## Verification
- `pnpm --filter frontend test:unit src/lib/api/marketService.test.ts`: Verify `getValuationsBatch` tests pass.
- `pnpm --filter frontend test:unit src/lib/utils/finance/valuation.test.ts`: Verify `formatValuationRange` tests pass for standard ranges, large numbers, and null/NaN fallbacks (`—`).
- `pnpm --filter frontend test:unit src/lib/components/holdings/holdings-table-columns.test.ts`: Verify column configuration, width clamping, and visibility toggling tests pass.
- `pnpm --filter frontend test:unit src/lib/components/holdings/holdingsService.test.ts`: Verify batch valuation loading and graceful failure tests pass.
- `pnpm --filter frontend test:unit src/lib/components/holdings/holdings-table.test.ts`: Verify Valuation Range column rendering, sorting, and resizing tests pass.
- `pnpm --filter frontend test:unit src/routes/holdings/page.svelte.test.ts`: Verify settings dropdown column toggle and preference persistence tests pass.
- `pnpm --filter frontend check`: Verify TypeScript compilation and type safety pass without errors.
- `pnpm --filter frontend lint`: Verify code style and formatting standards pass.
- `pnpm --filter frontend test:unit`: Verify the entire frontend test suite passes without regressions.
- `pnpm --filter frontend build`: Verify the frontend build succeeds.

## Risks / watch-outs
- Numeric vs String Sorting: Valuation ranges must sort by numeric value (midpoint `(lower + upper) / 2`) rather than alphabetical string comparison (so e.g. "100.00 – 200.00" does not sort before "20.00 – 30.00").
- Non-fatal Valuations Lookup: The batch valuation API call must never crash or prevent the holdings table from displaying holding rows if the market API experiences an error or timeout.
- Decimal Parsing: Backend Decimal values may serialize as strings (e.g. `"25.50"`); convert them to numbers via `Number()` when storing in the valuation map.
- SSR Isolation Seam: Adhere to the codebase's SSR rule ("no global instances") by passing `customFetch` to `getMarketService(customFetch)` in `HoldingsService`.
- Existing Column Count Assertions: The test in `holdings-table.test.ts` line 728 asserts 9 column headers for invalid configurations; this must be updated to 10 to reflect the new column.
