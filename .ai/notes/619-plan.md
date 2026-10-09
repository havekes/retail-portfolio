## Plan

**Approach:**
Refine visual affordances on account cards and inline holdings rows by appending `dark:hover:bg-background/60` to icon buttons (expand/collapse chevron, sync button triggers, 3-dots actions menu) and the title link in `accounts-list-item.svelte` to prevent button hover states from blending into `bg-muted` in dark mode, adding `align="end"` to `DropdownMenu.Content` for clean right-edge alignment with the trigger, and replacing `w-fit` with `w-full` while stripping `group-hover:underline` on symbol links in `account-inline-holdings.svelte` for uniform, non-distracting row hover hitboxes.

**Files:**
- `frontend/src/lib/components/accounts/accounts-list-item.svelte` — modify: Add `dark:hover:bg-background/60` to expand/collapse chevron button, title link (`linkClass`), sync button triggers, and 3-dots button; add `align="end"` to `DropdownMenu.Content`.
- `frontend/src/lib/components/accounts/account-inline-holdings.svelte` — modify: Remove `group-hover:underline` from security symbol span; change `w-fit` to `w-full` on security symbol/name link `<a>` element (and add `dark:hover:bg-background/60` for consistency).
- `frontend/src/lib/components/accounts/accounts-list-item.test.ts` — modify: Update hover class tests to assert `dark:hover:bg-background/60` on chevron, title link, sync button, and 3-dots button; add test asserting `align="end"` (`data-align="end"`) on the dropdown content.
- `frontend/src/lib/components/accounts/account-inline-holdings.test.ts` — modify: Assert absence of `group-hover:underline` on symbol element and assert `w-full` styling across all row symbol/name links.

**Steps:**
1. In `frontend/src/lib/components/accounts/accounts-list-item.svelte`:
   - Add `dark:hover:bg-background/60` to the expand/collapse chevron `<Button>` class list.
   - Add `dark:hover:bg-background/60` to the `<EditableTitle>` `linkClass` string (`"rounded-md px-2 py-1 transition-colors hover:bg-background/60 dark:hover:bg-background/60 hover:no-underline"`).
   - Add `dark:hover:bg-background/60` to the sync `<Tooltip.Trigger>` class string for both the syncing (disabled) and idle states.
   - Add `dark:hover:bg-background/60` to the 3-dots overflow `<Button>` class list.
   - Add `align="end"` prop to `<DropdownMenu.Content>`.
2. In `frontend/src/lib/components/accounts/account-inline-holdings.svelte`:
   - On the symbol link `<a>` element, replace `w-fit` with `w-full` (e.g., `class="group -mx-2 -my-1 flex w-full flex-col rounded-md px-2 py-1 transition-colors hover:bg-background/60 dark:hover:bg-background/60"`).
   - On the symbol text `<span>`, remove `group-hover:underline` so it reads `<span class="text-sm font-semibold text-primary">`.
3. In `frontend/src/lib/components/accounts/accounts-list-item.test.ts`:
   - Update the hover styling test to verify `dark:hover:bg-background/60` is present on the expand/collapse chevron button, account title link, sync button, and 3-dots button.
   - Add a test that opens the 3-dots actions menu and asserts `data-align="end"` is set on `[data-slot="dropdown-menu-content"]`.
4. In `frontend/src/lib/components/accounts/account-inline-holdings.test.ts`:
   - Add assertion that symbol text does not have class `group-hover:underline` or `underline`.
   - Add assertion that all rendered symbol links have `w-full` class and do not have `w-fit`.
5. Run `npm --prefix frontend run check`, `npm --prefix frontend run lint`, and `npm --prefix frontend run test:run` to confirm all types, lint rules, and test suites pass.

**Verification:**
- **Dark hover styling on account card icon buttons and title link (AC 1):** In `accounts-list-item.test.ts`, assert `dark:hover:bg-background/60` exists on the chevron button, title link, sync button, and 3-dots button. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **Dropdown menu right-alignment (AC 2):** In `accounts-list-item.test.ts`, click the 3-dots menu button and verify `document.querySelector('[data-slot="dropdown-menu-content"]')?.getAttribute('data-align') === 'end'`. Run `npm --prefix frontend test accounts-list-item.test.ts`.
- **No hover underline on holding symbol (AC 3):** In `account-inline-holdings.test.ts`, assert `screen.getByText('TD')` does not have `group-hover:underline`. Run `npm --prefix frontend test account-inline-holdings.test.ts`.
- **Uniform holding symbol/name width across rows (AC 4):** In `account-inline-holdings.test.ts`, query all symbol/name links and assert each has `w-full` and does not have `w-fit`. Run `npm --prefix frontend test account-inline-holdings.test.ts`.
- **Unit test coverage (AC 5, 6):** Run `npm --prefix frontend test accounts-list-item.test.ts account-inline-holdings.test.ts` to ensure all new and existing tests pass cleanly.
- **Static checks & test suite (AC 7):** Run `npm --prefix frontend run check`, `npm --prefix frontend run lint`, and `npm --prefix frontend run test:run`.

**Risks / watch-outs:**
- **Dropdown menu content portal query:** Because `DropdownMenu.Content` is portaled into `document.body` asynchronously when triggered, tests asserting `data-align="end"` should use `await waitFor(() => ...)` similar to existing dropdown / popover tests in the codebase.
- **Table cell width with `w-full`:** Ensure `Table.Cell` in `account-inline-holdings.svelte` does not overflow or collide with the Quantity column when `w-full` is used with `-mx-2 -my-1 px-2 py-1`. Since `Table.Cell` default has `px-4 py-2`, `w-full` neatly fills the cell width while maintaining padding.
