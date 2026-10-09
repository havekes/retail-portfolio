# Implementation Plan - Ticket #441

HOLDINGS-T09: Address PR 422 round 4 review feedback for holdings display and settings

## Plan

**Approach:**
Polish holdings table styling by disabling header row hover, scoping hover highlighting to individual `Table.Head` elements, softening vertical separator borders (`border-border/40`), aligning Quantity typography with neighboring numeric columns (`text-xs tabular-nums`), and fixing sticky Security cell hover specificity with `group-even:group-hover:bg-muted/80` and ticker link hover styling (`hover:bg-accent hover:text-accent-foreground`). In the page header, consolidate the standalone "Group by stock" checkbox and column visibility button into a single icon-only `Settings2` dropdown menu ("Display settings") containing both grouping and column toggles without triggering data refetches. Update all unit tests in `holdings-table.test.ts` and `page.svelte.test.ts` to assert the refreshed styling and menu interactions.

**Files:**
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: disable header `Table.Row` hover (`hover:bg-transparent`), add individual `Table.Head` hover (`transition-colors hover:bg-muted/50`), soften vertical borders to `border-border/40` across headers, cells, and resize separators, update Quantity cell typography to `text-xs tabular-nums`, resolve sticky cell hover specificity on even rows with `group-even:group-hover:bg-muted/80`, and update security ticker link hover styling to `hover:bg-accent hover:text-accent-foreground`.
- `frontend/src/routes/holdings/+page.svelte` — modify: remove standalone "Group by stock" checkbox and text button, replace with a unified icon-only `Settings2` button (`aria-label="Display settings"`, `title="Display settings"`, `data-testid="display-settings-trigger"`), and include both "Group by stock" checkbox item and visible columns checkbox items in `DropdownMenu.Content`.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: update and add unit tests to assert header row hover suppression, individual column header hover classes, softened vertical border classes (`border-border/40`), Quantity cell `text-xs tabular-nums`, sticky cell `group-even:group-hover:bg-muted/80` consistency, and ticker link `hover:bg-accent hover:text-accent-foreground`.
- `frontend/src/routes/holdings/page.svelte.test.ts` — modify: update tests to verify the unified icon-only settings trigger button layout, dropdown menu open action, "Group by stock" toggle behavior and persistence from within the menu, and column visibility toggles.

**Steps:**
1. Update `frontend/src/lib/components/holdings/holdings-table.svelte`:
   - On `<Table.Row>` inside `<Table.Header>`, add `class="hover:bg-transparent"`.
   - On `<Table.Head>` in `sortHeader`, add `transition-colors hover:bg-muted/50` and change `border-r border-border` to `border-r border-border/40`.
   - On the resize separator `<span>` in `sortHeader`, change `border-r border-border` to `border-r border-border/40`.
   - On sticky Security `<Table.Cell>`, change `border-r border-border` to `border-r border-border/40`, and add `group-even:group-hover:bg-muted/80` to the class list.
   - On the security ticker link `<a>` inside sticky cell, update `hover:bg-muted/80` to `hover:bg-accent hover:text-accent-foreground`.
   - On the Quantity `<Table.Cell>`, change `text-sm` to `text-xs` (keeping `tabular-nums`) and update `border-r border-border` to `border-r border-border/40`.
   - On all remaining `<Table.Cell>` elements in `holdingRow` (`account_name`, `average_cost`, `latest_price`, `total_value`, `profit_loss`, `ew_primary_target`, `ew_cycle_target`), change `border-r border-border` to `border-r border-border/40`.
2. Update `frontend/src/routes/holdings/+page.svelte`:
   - Remove unused import of `Checkbox` from `$lib/components/ui/checkbox/index.js`.
   - Remove the standalone `<div class="flex items-center gap-2">` containing the "Group by stock" checkbox and label from the header `actions` snippet.
   - Replace the column visibility `<DropdownMenu.Root>` trigger button with an icon-only button: `<button type="button" data-testid="display-settings-trigger" aria-label="Display settings" title="Display settings" class="inline-flex size-8 items-center justify-center rounded-md border border-input bg-background text-muted-foreground shadow-xs transition-colors hover:bg-accent hover:text-accent-foreground"><Settings2 size={16} /></button>`.
   - In `<DropdownMenu.Content>`, add a `View options` label and a `<DropdownMenu.CheckboxItem data-testid="group-by-stock" checked={service.groupBy === 'stock' || service.groupBy === 'company'} onCheckedChange={handleGroupToggle}>Group by stock</DropdownMenu.CheckboxItem>`, followed by a separator and the existing visible columns section.
3. Update `frontend/src/lib/components/holdings/holdings-table.test.ts`:
   - Update security link hover test to assert `hover:bg-accent` and `hover:text-accent-foreground` instead of `hover:bg-muted/80`.
   - Update header and cell border assertions to check for `border-border/40` (and verify horizontal row borders remain `border-b border-border`).
   - Add assertions for header `Table.Row` having `hover:bg-transparent` and each `Table.Head` having `transition-colors hover:bg-muted/50`.
   - Add an assertion for Quantity cell having `text-xs tabular-nums`.
   - Update sticky Security cell assertions to verify `group-even:group-hover:bg-muted/80`.
4. Update `frontend/src/routes/holdings/page.svelte.test.ts`:
   - Update tests that interact with "Group by stock" and column visibility to open the dropdown menu via `screen.getByTestId('display-settings-trigger')` (or `screen.getByRole('button', { name: 'Display settings' })`) before clicking `group-by-stock` or `column-toggle-*`.
   - Add test asserting top bar actions render the icon-only button with `aria-label="Display settings"` and do not render the standalone checkbox outside the dropdown.
   - Verify toggling "Group by stock" from within the dropdown updates row grouping and persists preferences to `patchPreferences` without triggering `getUserHoldings`.

**Verification:**
- `cd frontend && bun test src/lib/components/holdings/holdings-table.test.ts`: passes all unit tests for header hover, softened borders, Quantity typography, sticky cell hover consistency, and ticker link hover state.
- `cd frontend && bun test src/routes/holdings/page.svelte.test.ts`: passes all unit tests for unified settings dropdown trigger, menu layout, grouping toggle, and column visibility.
- `cd frontend && bun run check`: SvelteKit type checking passes with zero diagnostics.
- `cd frontend && bun run lint`: Biome / ESLint linter passes with zero warnings or errors.
- `cd frontend && bun test`: full frontend test suite passes cleanly.

**Risks / watch-outs:**
- In jsdom tests, elements inside `DropdownMenu.Content` from `bits-ui` are not present in the DOM until the menu trigger is clicked; test cases must await trigger interaction before querying dropdown items (`group-by-stock` or column toggles).
- Ensure `hover:bg-accent` on the ticker link has sufficient contrast against both light and dark theme row backgrounds (`bg-muted/80`).
