## Plan

**Approach:** Implement round 3 review feedback for the holdings table and page layout by redesigning header currency totals into a 2-line layout with return % badges computed from bucket cost basis, updating table row and sticky cell styling to support contrastive zebra striping and unified hover states with reinforced borders, removing secondary unconverted P/L text to slim the Return column, and dynamically setting the Account column header based on grouping mode. This matches existing presentation patterns from the Watchlists and Security Detail pages while preserving Svelte 5 reactivity and client-side grouping performance.

**Files:**
- `frontend/src/routes/holdings/+page.svelte` — modify: Update `currencyTotals` derived state to calculate aggregate cost basis and `returnPercent` per currency bucket; import `cn` and add `getPillClass` and `formatPercent` helpers; redesign currency totals UI into a 2-line flex layout with `{currency} TOTAL` and formatted total on the left, and Return % pill badge and profit/loss dollar value on the right.
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: Add `group border-b border-border transition-colors even:bg-muted/50 hover:bg-muted/80` to `<Table.Row>`; update sticky `security_symbol` `<Table.Cell>` with `group-even:bg-muted/50 group-hover:bg-muted/80 border-r border-border`; add `border-r border-border` to table header and body cells; remove `profit-loss-secondary` from Return column; dynamically display `"Accounts"` when `groupBy` is active and `"Account"` when disabled in `sortHeader`.
- `frontend/src/routes/holdings/page.svelte.test.ts` — modify: Update currency total tests to assert 2-line layout, `{currency} TOTAL` casing, formatted dollar values, and Return % pill badge presence with proper styling; add tests for negative and zero return percentages.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: Update existing tests asserting `profit-loss-secondary` to assert it is absent; add tests verifying dynamic `"Accounts"` vs `"Account"` column header label based on `groupBy`; add tests verifying table row, sticky cell, and border CSS classes for zebra striping and hover states.

**Steps:**
1. **Update top bar currency totals computation and helpers in `frontend/src/routes/holdings/+page.svelte`:**
   - Import `cn` from `$lib/utils`.
   - Add `formatPercent` helper: `(value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%``.
   - Add `getPillClass` helper matching `holdings-table.svelte` styling: emerald for `> 0`, rose for `< 0`, muted for zero/null.
   - In `currencyTotals` derived calculation, accumulate `costBasis` for each currency bucket by summing `row.quantity * (row.converted_average_cost ?? row.average_cost ?? 0)`.
   - Compute `returnPercent = bucket.hasProfitLoss && bucket.costBasis > 0 ? (bucket.profitLoss / bucket.costBasis) * 100 : null`.
2. **Redesign header currency totals markup in `frontend/src/routes/holdings/+page.svelte`:**
   - In `PageHeader` `actions` snippet, update the container for each `currencyTotals` entry to a 2-line flex layout (`flex items-center gap-3`).
   - Left side: top line displays `<span class="text-[10px] tracking-tight text-muted-foreground uppercase">{total.currency} TOTAL</span>`, bottom line displays formatted total value `<span class="text-base font-semibold text-foreground tabular-nums">{formatCurrency(total.totalValue, total.currency)}</span>`.
   - Right side: when `total.hasProfitLoss` is true, top line displays Return % pill badge `<span data-testid={`currency-return-percent-${total.currency}`} class={cn('inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold tabular-nums', getPillClass(total.returnPercent))}>{formatPercent(total.returnPercent)}</span>` (when `returnPercent !== null`), and bottom line displays formatted profit/loss `<span data-testid={`currency-profit-loss-${total.currency}`} class="text-xs text-muted-foreground tabular-nums">{total.profitLoss >= 0 ? '+' : ''}{formatCurrency(total.profitLoss, total.currency)}</span>`.
3. **Enhance table row, sticky cell, and border styling in `frontend/src/lib/components/holdings/holdings-table.svelte`:**
   - On `<Table.Row data-testid="holding-row">`: replace `border-b-muted/10 transition-all even:bg-muted/30 hover:bg-muted/10` with `group border-b border-border transition-colors even:bg-muted/50 hover:bg-muted/80`.
   - On sticky Security `<Table.Cell>`: add `group-even:bg-muted/50 group-hover:bg-muted/80 border-r border-border` alongside `sticky left-0 z-10 bg-background px-4 py-2`.
   - On other `Table.Cell` elements across the row: reinforce column separator borders by adding `border-r border-border`.
   - In `sortHeader` snippet: reinforce header column borders with `border-r border-border` on `<Table.Head>` and resize handle.
4. **Remove secondary currency text from Return column in `frontend/src/lib/components/holdings/holdings-table.svelte`:**
   - In `isVisible('profit_loss')` block, remove the secondary unconverted profit/loss block (`data-testid="profit-loss-secondary"`).
   - Retain Return % pill badge on top and primary currency dollar return below.
5. **Make Account column header dynamic in `frontend/src/lib/components/holdings/holdings-table.svelte`:**
   - In `sortHeader(column, width)` snippet, determine column header text: `const label = column.id === 'account_name' && groupBy ? 'Accounts' : column.label`.
   - Display `{label}` in the header sort button and in the resize handle `aria-label={`Resize ${label} column`}`.
6. **Update component and route unit tests:**
   - In `frontend/src/routes/holdings/page.svelte.test.ts`:
     - Update `buckets header totals per currency instead of summing across them` to verify `{currency} TOTAL` text, formatted total, Return % pill badge with positive/negative pill classes, and dollar profit/loss.
     - Add test verifying currency bucket with zero cost basis or missing profit/loss handles `returnPercent` gracefully.
   - In `frontend/src/lib/components/holdings/holdings-table.test.ts`:
     - In row display test (around line 450), replace assertion checking for `profit-loss-secondary` with `expect(within(row).queryByTestId('profit-loss-secondary')).not.toBeInTheDocument()`.
     - Add tests verifying Account column header renders `"Account"` when `groupBy={null}` and `"Accounts"` when `groupBy="stock"`.
     - Add tests verifying row styling classes (`even:bg-muted/50`, `hover:bg-muted/80`, `border-b border-border`) and sticky cell classes (`group-even:bg-muted/50`, `group-hover:bg-muted/80`, `border-r border-border`).
7. **Verification and Quality Checks:**
   - Run unit tests: `bun test src/routes/holdings/page.svelte.test.ts` and `bun test src/lib/components/holdings/holdings-table.test.ts`.
   - Run typecheck: `bun run check`.
   - Run linter: `bun run lint`.
   - Run full test suite: `bun run test`.

**Verification:**
- `bun test src/routes/holdings/page.svelte.test.ts`: verify 2-line layout for header totals, accurate return percentage calculation, pill badge styling, and dollar profit/loss (Acceptance criteria 1, 2, 9).
- `bun test src/lib/components/holdings/holdings-table.test.ts`: verify sticky Security cell matching even zebra striping and hover background, even zebra striping contrast classes, row hover classes, reinforced border classes, removal of secondary profit/loss text, and dynamic Account/Accounts column header (Acceptance criteria 3, 4, 5, 6, 7, 8, 9).
- `bun run lint`: verify frontend code passes ESLint and Prettier checks with 0 errors (Acceptance criterion 10).
- `bun run check`: verify Svelte and TypeScript diagnostics pass with 0 errors (Acceptance criterion 10).
- `bun run test`: verify all frontend unit and integration test suites pass (Acceptance criterion 10).

**Risks / watch-outs:**
- **Zero or negative cost basis in top bar totals:** If all holdings in a currency bucket have zero or null cost basis (e.g. gifted securities or incomplete data), `bucket.costBasis` will be 0. Division by zero must be prevented by setting `returnPercent = null` and omitting the pill badge or rendering a fallback.
- **Sticky cell layering on hover:** The sticky `security_symbol` cell uses `sticky left-0 z-10`. When an even row is hovered, `group-hover:bg-muted/80` must take visual precedence over `group-even:bg-muted/50` and `bg-background`. In Tailwind, `group-hover:` styles correctly override non-hover styles.
- **Dynamic Account header sort button name:** When testing button queries with Testing Library `getByRole('button', { name: 'Account' })`, tests with `groupBy="stock"` must query for `getByRole('button', { name: 'Accounts' })` instead.
