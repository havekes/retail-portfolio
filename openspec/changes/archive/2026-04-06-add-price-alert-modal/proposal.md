## Why

The current price alert creation flow is primarily driven by chart interactions (clicking on the price scale). While there is an "Add Alert" button in the right sidebar's `AlertsGroup`, it is only visible when the group is expanded and resides at the bottom of the list. Furthermore, the UI text suggests users "Click + to add one," but no such button exists in the group header. Users need a more direct, manual, and accessible way to set price alerts without necessarily interacting with the chart or digging into the sidebar content.

## What Changes

1.  **Right Sidebar Enhancement**: Add a `+` (Plus) action button to the `Price Alerts` group header in the `ActionsSidebar` on the security page.
2.  **State Management**: Refactor `AlertCreationDialog` into a more robust `PriceAlertModal` component, potentially utilizing a Svelte 5 class-based state manager for better reactivity and external triggering.
3.  **UI/UX Improvement**: Update the modal to display the current market price of the security (if available) to help users set accurate "above/below" conditions.

## Capabilities

### New Capabilities
- `price-alert-management`: Enhanced manual price alert creation and management interface accessible via sidebars.

### Modified Capabilities
- None

## Impact

-   **Frontend**:
    -   `src/lib/components/actions-sidebar/alerts-group.svelte`: Add header action button.
    -   `src/lib/components/actions-sidebar/alert-creation-dialog.svelte`: Refactor/Enhance.
    -   `src/lib/components/charts/dialogs/price-alert.svelte`: New standalone modal component.
-   **API**: Uses existing `/market/securities/${id}/alerts` endpoints.
