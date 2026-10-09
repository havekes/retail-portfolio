## Plan

**Approach:**
Enable full-cell sorting on `<Table.Head>` by moving the sort trigger to the table header cell (`onclick`, `cursor-pointer`, `select-none`, `group/head`) while preserving keyboard accessibility on the inner button with click event stopPropagation. Prevent accidental sorts during column resizing by stopping event propagation on the resize handle's pointerdown and click handlers, show the sort icon on header hover via `group-hover/head:opacity-50`, and constrain ticker hover styling to `w-fit` with button padding (`rounded-md px-2 py-1`) to highlight only the ticker and company name.

**Files:**
- `frontend/src/lib/components/holdings/holdings-table.svelte` — modify: add `group/head cursor-pointer select-none` and `onclick={() => handleSort(column.id)}` to `<Table.Head>`, stop click propagation on the inner sort `<button>` to prevent double-toggling while retaining keyboard access, add `onclick={(e) => event.stopPropagation()}` to the resize separator `<span>`, change `ArrowUpDown` visibility class to `group-hover/head:opacity-50`, and update security link styling to `w-fit flex flex-col rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-accent-foreground`.
- `frontend/src/lib/components/holdings/holdings-table.test.ts` — modify: update sorting tests to verify clicking `<Table.Head>` columnheader cells sorts rows, add test ensuring resizing or clicking column resize handles does not trigger sorting, verify `group/head` and `group-hover/head:opacity-50` hover icon classes, and update security link assertions to verify `w-fit`, `rounded-md`, `px-2`, `py-1` and the absence of `w-full` / negative margins.

**Steps:**
1. Update `sortHeader` snippet in `frontend/src/lib/components/holdings/holdings-table.svelte`:
   - Add `group/head cursor-pointer select-none` to `<Table.Head>` class list and attach `onclick={() => handleSort(column.id)}`.
   - On the inner `<button>`, update `onclick` to `(event) => { event.stopPropagation(); handleSort(column.id); }` so keyboard/screen-reader navigation triggers sorting without bubbling to `<Table.Head>` and causing a double toggle.
   - On the resize separator `<span>`, add `onclick={(event) => event.stopPropagation()}` and ensure pointerdown stops propagation so dragging or clicking the resize handle never triggers sorting.
   - On `<ArrowUpDown>`, replace `group-hover:opacity-50` with `group-hover/head:opacity-50` so hovering anywhere over `<Table.Head>` reveals the sort icon.
2. Update `holdingRow` snippet in `frontend/src/lib/components/holdings/holdings-table.svelte`:
   - Replace the security link `<a>` class `group -mx-1.5 -my-1 flex w-full flex-col rounded-md px-1.5 py-1 transition-colors hover:bg-accent hover:text-accent-foreground` with `w-fit flex flex-col rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-accent-foreground`.
3. Update unit tests in `frontend/src/lib/components/holdings/holdings-table.test.ts`:
   - Update sorting tests to verify clicking `<Table.Head>` column headers directly (e.g. `screen.getByRole('columnheader', { name: /Security/i })`) sorts rows and toggles ascending/descending on repeat clicks.
   - Add a test verifying that clicking or dragging a column resize handle (`screen.getByTestId('column-resize-...')`) does not alter sort column or direction.
   - Add assertions verifying `<Table.Head>` has `group/head cursor-pointer select-none` and unsorted header `ArrowUpDown` has `opacity-0 group-hover/head:opacity-50`.
   - Update the security link test (`renders one row per holding and links each security cell...`) to assert `w-fit`, `rounded-md`, `px-2`, `py-1` and assert that `w-full`, `-mx-1.5`, and `-my-1` are not present.
4. Run validation checks:
   - Execute targeted tests: `cd frontend && npm run test:run src/lib/components/holdings/holdings-table.test.ts`.
   - Execute type checks: `cd frontend && npm run check`.
   - Execute linter: `cd frontend && npm run lint`.
   - Execute full regression test: `cd frontend && npm run test:run` or `./scripts/agent-test frontend`.

**Verification:**
- `cd frontend && npm run test:run src/lib/components/holdings/holdings-table.test.ts` (or `bun test src/lib/components/holdings/holdings-table.test.ts`): passes all unit tests, confirming full `<Table.Head>` click sorting (AC 1), resize handle event stopPropagation (AC 2), header hover sort icon visibility styling (AC 3), and `w-fit` rounded button-like security link styling (AC 4, AC 5).
- `cd frontend && npm run check`: SvelteKit type checking passes with zero errors or diagnostics.
- `cd frontend && npm run lint`: Prettier and ESLint pass without warnings or errors.
- `cd frontend && npm run test:run`: full frontend test suite passes cleanly (AC 6).

**Risks / watch-outs:**
- Event bubbling between inner sort `<button>` and outer `<Table.Head>`: without `event.stopPropagation()` on the button's `onclick`, clicking the button triggers both handlers in succession, canceling the sort toggle.
- Pointer vs click events on resize handle: resize handles intercept pointer events via `onpointerdown`, but a quick click can still emit a `click` event unless `onclick={(e) => e.stopPropagation()}` is attached to the separator `<span>`.
- In SvelteKit / Tailwind CSS, ensure `group/head` and `group-hover/head:opacity-50` syntax correctly maps to the parent `<Table.Head>` without conflicting with table row `group` classes.
