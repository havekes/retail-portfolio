## Plan

**Approach:**
Address PR review feedback round 2 for the holdings table by streamlining presentation, UI affordances, and adding projection metrics across the column configuration, table component, page header actions, and server loader. We make security links fill the cell width (`w-full`), soften account badge styling (`text-[10px] font-normal text-muted-foreground`), simplify Average Cost to native currency single-line display, highlight header resize handles with visible separator borders, consolidate Return % and dollar profit/loss into a unified Return column, and hoist column visibility controls into the PageHeader actions snippet. Elliott Wave primary and cycle target projections are surfaced as first-class table columns with upside % pills and target prices, computed via existing `getLatestWaveCount`, `getWaveTargetPrice`, and `calculateUpsidePercentage` utilities seeded from user preferences in `+page.server.ts`.

**Files:**
- `frontend/src/lib/components/holdings/holdings-table-columns.ts` — modify: rename column labels ("Avg Cost" -> "Average", "Profit/Loss" -> "Return"), remove `profit_loss_percent`, add `ew_primary_target` and `ew_cycle_target` with width constraints, and export `toggleColumnVisibility`.
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: update security link to `w-full`, update account badge styling, simplify `average_cost` to native-only single-line, add visible header separator borders/resize handles, remove the above-table toolbar, accept `elliottWaves` prop, combine Return % and dollar P/L into the `profit_loss` cell, add `ew_primary_target` and `ew_cycle_target` cells with upside % pill and target price, and support sorting for Return and both EW target columns (nulls last).
- `frontend/src/routes/holdings/+page.svelte` — modify: move column visibility dropdown into `PageHeader` actions snippet, manage local reactive `tableConfig` state with `toggleColumnVisibility`, and forward `elliott_waves` from server data to `HoldingsTable`.
- `frontend/src/routes/holdings/+page.server.ts` — modify: load and return `elliott_waves` from `getUserPreferencesService(fetch).getPreferences(token)`.
- `frontend/src/lib/components/holdings/holdings-table-columns.test.ts` — modify: update tests for renamed labels, removed `profit_loss_percent`, added EW columns, clamping, and `toggleColumnVisibility`.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: test `w-full` security link, account badge styling, single-line Average cost, combined Return cell, EW target column rendering, visible header separator borders, and sorting for Return and EW columns.
- `frontend/src/routes/holdings/page.svelte.test.ts` — modify: test PageHeader column visibility dropdown trigger and toggling, and `elliott_waves` prop passing.
- `frontend/src/routes/holdings/page.server.test.ts` — create: unit tests for `+page.server.ts` verifying data loading, preferences fallback, and error handling.

**Steps:**
1. **Update column configuration in `frontend/src/lib/components/holdings/holdings-table-columns.ts`:**
   - Rename column labels in `HOLDINGS_TABLE_COLUMNS`: `"average_cost"` to `"Average"` and `"profit_loss"` to `"Return"`.
   - Remove `profit_loss_percent` from `HOLDINGS_TABLE_COLUMN_IDS`, `HOLDINGS_TABLE_COLUMNS`, `HOLDINGS_TABLE_DEFAULT_WIDTHS`, `HOLDINGS_TABLE_COLUMN_MIN_WIDTHS`, and `HOLDINGS_TABLE_COLUMN_MAX_WIDTHS`.
   - Add `ew_primary_target` (label `"EW Primary"`, `alignRight: true`, default width 150px, min 120px, max 240px) to `HOLDINGS_TABLE_COLUMN_IDS`, `HOLDINGS_TABLE_COLUMNS`, and width definitions.
   - Add `ew_cycle_target` (label `"EW Cycle"`, `alignRight: true`, default width 150px, min 120px, max 240px) to `HOLDINGS_TABLE_COLUMN_IDS`, `HOLDINGS_TABLE_COLUMNS`, and width definitions.
   - Add and export `toggleColumnVisibility(config: HoldingsTableConfig, columnId: HoldingsTableColumnId): HoldingsTableConfig` ensuring sticky `HOLDINGS_TABLE_STICKY_COLUMN_ID` cannot be hidden and visible order matches `HOLDINGS_TABLE_COLUMNS`.
2. **Update column unit tests in `frontend/src/lib/components/holdings/holdings-table-columns.test.ts`:**
   - Update tests to reflect new column IDs (`ew_primary_target`, `ew_cycle_target`) and removal of `profit_loss_percent`.
   - Test `clampColumnWidth` for `ew_primary_target` and `ew_cycle_target` (min 120, max 240, default 150).
   - Test `toggleColumnVisibility` verifying toggling columns off/on, preserving canonical order, and preventing hiding of sticky column `security_symbol`.
   - Test `normalizeHoldingsTableConfig` filtering out legacy `profit_loss_percent` while maintaining canonical visibility of new EW columns.
3. **Update server loader and create `page.server.test.ts`:**
   - In `frontend/src/routes/holdings/+page.server.ts`:
     - Load `elliott_waves: prefs?.elliott_waves ?? null` alongside `holdings_table_config` and `group_mode`.
     - Return `elliott_waves` in the server data object.
   - Create `frontend/src/routes/holdings/page.server.test.ts`:
     - Test successful load returning `holdings`, `holdings_table_config`, `group_mode`, and `elliott_waves`.
     - Test non-fatal preferences error fallback returning default configs and `elliott_waves: null`.
     - Test 401 ApiError triggers cookie deletion and redirect to `/auth/login?clear_session=true`.
     - Test non-401 ApiErrors and unexpected 500 errors propagate as expected.
4. **Update holdings route layout and column visibility in `frontend/src/routes/holdings/+page.svelte`:**
   - Import `DropdownMenu` components, `Settings2` icon, `HOLDINGS_TABLE_COLUMNS`, `HOLDINGS_TABLE_STICKY_COLUMN_ID`, and `toggleColumnVisibility`.
   - Initialize reactive `tableConfig` state with `normalizeHoldingsTableConfig(data.holdings_table_config)`.
   - Add column visibility dropdown menu into `PageHeader` `actions` snippet next to "Group by stock" checkbox.
   - Implement `handleToggleColumn(columnId)` using `toggleColumnVisibility` and persist via `saveHoldingsTableConfig(prefsService, nextConfig)`.
   - Implement `handleConfigChange(nextConfig)` on column resize and persist via `saveHoldingsTableConfig`.
   - Forward `elliottWaves={data.elliott_waves}` to `<HoldingsTable />`.
5. **Update `HoldingsTable` presentation and formatting in `frontend/src/lib/components/holdings/holdings-table.svelte`:**
   - Accept `elliottWaves?: Record<string, SecurityElliottWaves> | null` prop.
   - Remove redundant above-table column visibility toolbar (`<div class="flex items-center justify-end border-b px-2 py-1">...</div>`).
   - On `<a data-testid="security-link">`, change `w-fit` to `w-full` for full-width clickability.
   - On `<Badge variant="secondary">` in `account-cell`, add `class="text-[10px] font-normal text-muted-foreground"`.
   - Update `average_cost` cell to a single line showing `formatCurrency(row.average_cost, row.security_currency)` or `"-"`, removing converted CAD line.
   - Update `sortHeader`: add `border-r border-border/40` on `Table.Head` and visible separator border/handle styling `border-r border-border/60 hover:border-primary/70` on the resize handle `span` so resizability is signaled before hover.
   - Update `HoldingRowView` to include `ew_primary_target`, `ew_primary_upside`, `ew_cycle_target`, and `ew_cycle_upside`.
   - In `baseRows` (both flat and `groupHoldings` grouped paths), compute wave targets and upside % via `getLatestWaveCount(elliottWaves?.[securityId], 'primary')` / `'cycle'`, `getWaveTargetPrice(wave, 'wave5')`, and `calculateUpsidePercentage(targetPrice, latest_price)`.
   - Combine Return column in `profit_loss` cell: show `profit-loss-percent` pill badge on top using `getPillClass` and `formatPercent`, and dollar `profit_loss` (with secondary native USD if foreign currency) underneath.
   - Add EW target column cells for `ew_primary_target` and `ew_cycle_target`: show upside % pill badge on top using `getPillClass` and `formatPercent`, and target price in `security_currency` below; if no wave 5 target exists, display `"-"`.
   - Update `valueFor`: return `row.ew_primary_upside ?? row.ew_primary_target` for `ew_primary_target`, and `row.ew_cycle_upside ?? row.ew_cycle_target` for `ew_cycle_target`. Ensure `displayRows` sorting places null/undrawn targets last in both asc and desc directions.
6. **Update component and integration tests:**
   - Update `frontend/src/lib/components/holdings/holdings-table.test.ts`:
     - Update button labels: `"Avg Cost"` -> `"Average"`, `"Profit/Loss"` / `"P/L %"` -> `"Return"`.
     - Test security link has `w-full` class.
     - Test account badges have `text-[10px] font-normal text-muted-foreground`.
     - Test Average column displays only native currency on a single line and no converted CAD line.
     - Test Return column displays percentage pill badge on top and dollar value underneath.
     - Test EW Primary and EW Cycle column rendering (upside % pill on top, target price below, and `"-"` for undrawn targets).
     - Test sorting by Return, EW Primary, and EW Cycle, verifying null/undrawn targets sort last in both directions.
     - Verify visible resize borders on header cells.
   - Update `frontend/src/routes/holdings/page.svelte.test.ts`:
     - Test PageHeader column visibility dropdown trigger and toggling columns hides/restores them.
     - Test `data.elliott_waves` forwarding to `HoldingsTable`.
7. **Verification and quality checks:**
   - Run Vitest unit test suites for touched files: `holdings-table-columns.test.ts`, `page.server.test.ts`, `holdings-table.test.ts`, and `page.svelte.test.ts`.
   - Run `pnpm -C frontend check` to verify TypeScript and Svelte compilation.
   - Run `pnpm -C frontend lint` to verify formatting and linting rules.
   - Run `pnpm -C frontend build` to verify production build passes.

**Verification:**
- `pnpm -C frontend test:unit src/lib/components/holdings/holdings-table-columns.test.ts`: verify column definitions, widths, bounds, and normalizer (Acceptance criteria 6, 7, 8, 12).
- `pnpm -C frontend test:unit src/routes/holdings/page.server.test.ts`: verify `+page.server.ts` loads and passes `elliott_waves` and handles fallbacks/errors (Acceptance criterion 10).
- `pnpm -C frontend test:unit src/lib/components/holdings/holdings-table.test.ts`: verify `w-full` security link (AC 1), account badge styling (AC 2), single-line native Average cost (AC 3), visible header separator handles (AC 4), Return column % pill + dollar layout (AC 6, 7), EW Primary and EW Cycle projection pill and price display with "-" fallback (AC 8, 9), and sorting on Return and EW target columns (AC 11).
- `pnpm -C frontend test:unit src/routes/holdings/page.svelte.test.ts`: verify column visibility dropdown in PageHeader actions and removal of redundant toolbar (AC 5).
- `pnpm -C frontend check`: passes with zero TypeScript / Svelte errors (Acceptance criterion 13).
- `pnpm -C frontend lint`: passes with zero ESLint / Prettier formatting errors (Acceptance criterion 13).
- `pnpm -C frontend build`: production build succeeds without errors (Acceptance criterion 13).

**Risks / watch-outs:**
- **Null / Undrawn wave targets in sorting:** Elliott Wave targets may be absent (`null`) or present without a valid `latest_price` (resulting in non-finite or `null` upside percent). Ensure `valueFor` and `displayRows` sorting consistently places null/undrawn values last regardless of whether sort direction is `'asc'` or `'desc'`.
- **Legacy stored column preferences:** Users with stored `visible` or `widths` containing `profit_loss_percent` must have that unknown column gracefully dropped without breaking table layout or restoring corrupted state.
- **Sticky column invariant:** The sticky first column (`security_symbol`) must remain disabled in the hoisted `PageHeader` column visibility dropdown so users cannot hide it and break sticky cell alignment.
- **Grouped mode projection alignment:** In "Group by stock" mode, aggregated rows must calculate EW targets against the stock's `security_id` and `latest_price`, mirroring flat row behavior.
