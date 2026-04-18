## 1. Unified Price Alert Modal Component

- [x] 1.1 Create `src/lib/components/charts/dialogs/price-alert.svelte.ts` - Manage modal state with Svelte 5 classes, including `securityId`, `currentPrice`, `open`, `loading`, and `error`.
- [x] 1.2 Create `src/lib/components/charts/dialogs/price-alert.svelte` - Implement a robust, standalone modal that uses the state manager. Include security selection (if no `securityId` is present) and display current price.

## 2. Right Sidebar (ActionsSidebar) Enhancement

- [x] 2.1 Update `src/lib/components/actions-sidebar/alerts-group.svelte` to include a `Plus` button in the `Sidebar.GroupAction` slot.
- [x] 2.2 Wire the `Plus` button to open the `PriceAlertModal` for the current `securityId`.
- [x] 2.3 Move the expand/collapse trigger to the `Sidebar.GroupLabel` or add a dedicated chevron so `GroupAction` is free for the `+` action.

## 3. Cleanup and Polish

- [x] 3.1 Remove redundant `src/lib/components/actions-sidebar/alert-creation-dialog.svelte` once the new modal is fully integrated.
- [x] 3.2 Verify alert creation flows from all entry points.
- [x] 3.3 Ensure consistent styling with the existing Dashboard and Security pages.
