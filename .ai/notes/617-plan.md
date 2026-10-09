## Plan

**Approach:**
Polish account cards and inline holdings visual affordances by introducing watchlist-aligned rounded hover backgrounds (`rounded-md px-2 py-1 transition-colors hover:bg-background/60`) on links and action buttons, reorganizing the actions header so total profit/loss (`value - cost`) is rendered next to current value, positioning the sync button immediately left of the 3-dots actions menu, and moving the rename trigger into the 3-dots menu with a neutral `Pencil` icon while removing the inline pencil button. Persist expanded/collapsed account card states via `expanded_account_ids` in `UserPreferences`, wired through `+layout.server.ts` into page data/context and patched on toggle.

**Files:**
- `frontend/src/lib/api/userPreferencesService.ts` — modify: Add `expanded_account_ids?: string[] | null;` to the `UserPreferences` interface.
- `frontend/src/routes/+layout.server.ts` — modify: Load `expanded_account_ids` from user preferences with array shape validation and pass it down in layout data.
- `frontend/src/routes/layout.test.ts` — modify: Add test cases verifying `expanded_account_ids` defaults to empty array and reads from preferences.
- `frontend/src/lib/components/forms/editable-title.svelte` — modify: Support external editing control via bindable `isEditing` prop, conditional inline pencil button via `showEditButton` prop (defaults to true), and custom link styling via `linkClass` prop.
- `frontend/src/lib/components/accounts/account-inline-holdings.svelte` — modify: Add rounded hover background styling (`rounded-md px-2 py-1 transition-colors hover:bg-background/60`) to security symbol/name links in table rows.
- `frontend/src/lib/components/accounts/accounts-list.svelte` — modify: Provide shared reactive `expandedAccountIds` set via Svelte context initialized from page data / context to coordinate expansion state across account cards.
- `frontend/src/lib/components/accounts/accounts-list-item.svelte.ts` — modify: Support initial expansion state in `AccountsListItemState` constructor and optional expansion toggle callback.
- `frontend/src/lib/components/accounts/accounts-list-item.svelte` — modify: Reposition sync button immediately left of 3-dots menu; display total profit/loss alongside current value with currency formatting, sign prefix (+/-), and emerald/rose coloring; add rounded hover styling to account name link, sync button, and 3-dots button; update 3-dots dropdown menu with neutral `Pencil` rename item and destructive `Trash2` delete item; remove static pencil button next to title and trigger edit mode from 3-dots menu; persist expanded state to preferences on toggle.
- `frontend/src/lib/components/accounts/accounts-list-item.test.ts` — modify: Update existing rename test to use 3-dots menu, assert removal of static pencil icon, and add new unit tests for hover classes, button positioning, profit/loss formatting/coloring, 3-dots menu icons/variants, and preference persistence/restoration on toggle.
- `frontend/src/lib/components/accounts/account-inline-holdings.test.ts` — modify: Add unit test verifying security symbol/name links have rounded hover background classes.
- `openwiki/concepts/user-preferences.md` — modify: Document `expanded_account_ids` preference field.

**Steps:**
1. Update `frontend/src/lib/api/userPreferencesService.ts` to add `expanded_account_ids?: string[] | null;` to the `UserPreferences` interface.
2. In `frontend/src/routes/+layout.server.ts`, extract `expanded_account_ids` from `prefs` (guarding with `Array.isArray(prefs.expanded_account_ids)` and defaulting to `[]`) and return it in the layout data. In `frontend/src/routes/layout.test.ts`, add unit tests asserting default and loaded states.
3. Update `frontend/src/lib/components/forms/editable-title.svelte` to expose `isEditing = $bindable(false)`, `showEditButton = true`, and `linkClass = ''`. Ensure setting `isEditing = true` initializes `tempValue = value` and setting it to `false` cancels editing. When `showEditButton` is false, omit the pencil button beside the title. Apply `linkClass` to the `<a>` element.
4. Update `frontend/src/lib/components/accounts/account-inline-holdings.svelte` to add `class="group -mx-2 -my-1 flex w-fit flex-col rounded-md px-2 py-1 transition-colors hover:bg-background/60"` to the security symbol and name link `<a>` element.
5. In `frontend/src/lib/components/accounts/accounts-list-item.svelte.ts`, update `AccountsListItemState` to accept `initialExpanded = false` in the constructor, immediately setting `isExpanded` and dispatching `fetchAccountHoldings` if initially true.
6. In `frontend/src/lib/components/accounts/accounts-list.svelte`, initialize a reactive `SvelteSet<string>` of expanded IDs from `$page?.data?.expanded_account_ids` (and/or context `initialExpandedAccountIds`), and share it with child items via Svelte context `expandedAccountIds`.
7. In `frontend/src/lib/components/accounts/accounts-list-item.svelte`:
   - Initialize expansion state from the context `expandedAccountIds` or fallback to `$page?.data?.expanded_account_ids` / `initialExpanded` prop.
   - On caret toggle, update `expandedAccountIds` (add or delete `account.id`), toggle item state, and invoke `userPreferencesService.patchPreferences({ expanded_account_ids: Array.from(expandedAccountIds) })`.
   - Pass `showEditButton={false}`, `bind:isEditing={isEditingTitle}`, and `linkClass="rounded-md px-2 py-1 transition-colors hover:bg-background/60 hover:no-underline"` to `EditableTitle`.
   - Apply `rounded-md hover:bg-background/60 transition-colors` to the caret button, the sync button, and the 3-dots button.
   - Restructure the actions container: place the totals area on the left, followed immediately by the sync button, followed by the 3-dots dropdown menu button.
   - In the totals area, compute `val = moneyToNumber(totals.value)`, `cost = moneyToNumber(totals.cost)`, and `profitLoss = val - cost`. Display `money(totals.value)` alongside `(profitLoss >= 0 ? '+' : '') + formatCurrency(profitLoss, account.currency)` with `text-emerald-600 dark:text-emerald-400` when `>= 0` and `text-rose-600 dark:text-rose-400` when `< 0`.
   - In the 3-dots dropdown menu, add `Rename` with `<Pencil class="h-4 w-4" />` (default styling) that sets `isEditingTitle = true`, and ensure `Delete account` has `<Trash2 class="h-4 w-4" />` with `variant="destructive"`.
8. In `frontend/src/lib/components/accounts/accounts-list-item.test.ts`:
   - Update the existing rename test to open the 3-dots dropdown menu and click "Rename", asserting that no static pencil button is rendered next to the title.
   - Add test verifying the 3-dots menu contains "Rename" with Pencil icon (default styling) and "Delete account" with Trash2 icon (destructive variant).
   - Add test verifying the sync button immediately precedes the 3-dots button in the DOM order.
   - Add test verifying rounded hover classes (`rounded-md`, `hover:bg-background/60`) on the account title link, sync button, and 3-dots button.
   - Add test verifying total profit/loss formatting and color classes for positive (`+$50.00`, emerald) and negative (`-$25.00`, rose) values.
   - Add test verifying caret toggle calls `userPreferencesService.patchPreferences` with updated `expanded_account_ids`.
   - Add test verifying initial expansion and holdings fetching when account ID is present in `initialExpandedAccountIds` / preferences.
9. In `frontend/src/lib/components/accounts/account-inline-holdings.test.ts`, add test verifying security symbol/name links contain `rounded-md` and `hover:bg-background/60` classes.
10. Update `openwiki/concepts/user-preferences.md` to document the new `expanded_account_ids` preference field.
11. Run `npm run check`, `npm run lint`, and `npm run test:run` in `frontend` to verify all acceptance criteria and ensure zero regressions.

**Verification:**
- **Account title hover style (AC 1):** Assert in `accounts-list-item.test.ts` that the title link contains classes `rounded-md hover:bg-background/60`. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Sync & 3-dots hover styles (AC 2):** Assert in `accounts-list-item.test.ts` that both the sync button and 3-dots button contain `hover:bg-background/60 rounded-md`. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Inline holdings link hover style (AC 3):** Assert in `account-inline-holdings.test.ts` that security links contain `rounded-md hover:bg-background/60`. Run `npm --prefix frontend test account-inline-holdings.test.ts`.
- **Rename & Delete menu items and icons (AC 4, 5):** Assert in `accounts-list-item.test.ts` that the 3-dots menu renders `Rename` with Pencil icon (default variant) and `Delete account` with Trash2 icon and `data-variant="destructive"`. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Rename triggers title edit mode & inline pencil removed (AC 6, 7):** Assert in `accounts-list-item.test.ts` that no static pencil button is next to title, and clicking `Rename` in the 3-dots menu opens the title input textbox. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Sync button position (AC 8):** Assert in `accounts-list-item.test.ts` that the sync button is the immediate previous sibling element of the 3-dots dropdown menu trigger. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Total profit/loss display & coloring (AC 9):** Assert in `accounts-list-item.test.ts` that profit/loss is rendered with sign prefix (`+`/`-`), formatted currency, and emerald (`text-emerald-600`) or rose (`text-rose-600`) text class. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Toggle persistence & restore from user preferences (AC 10, 11):** Assert in `accounts-list-item.test.ts` that toggling caret calls `userPreferencesService.patchPreferences({ expanded_account_ids: [...] })`, and mounting with initial expanded account ID initializes `isExpanded = true` and fetches holdings. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Layout load preferences (AC 11):** Run `npm --prefix frontend test layout.test.ts`.
- **Full suite & static checks (AC 12, 13):** Run `npm --prefix frontend run check`, `npm --prefix frontend run lint`, and `npm --prefix frontend run test:run`.

**Risks / watch-outs:**
- **Dropdown menu item trigger interaction with focus:** When "Rename" is selected from bits-ui dropdown, ensure dropdown close does not steal focus back from the newly rendered title input textbox. If needed, trigger focus via `tick()` or autofocus on the `EditableTitle` input.
- **Standalone `AccountsListItem` vs `AccountsList` context:** When `AccountsListItem` is rendered alone in existing unit tests without `AccountsList`, ensure context lookup safely falls back to a local set so `patchPreferences` still receives the single account ID without null pointer errors.
