## Context

The current price alert creation is fragmented. While users can add alerts via the chart, the manual sidebar option is less accessible. Specifically, the right sidebar requires the group to be expanded. We need a unified `PriceAlert` modal and better sidebar integration within the security view.

## Goals / Non-Goals

**Goals:**
- Provide a consistent, manual price alert creation experience accessible from the security page sidebar.
- Improve the UI of the alert creation dialog by including the current market price.

**Non-Goals:**
- Modifying the chart-based alert creation logic (which uses a separate plugin).
- Adding complex alert types (e.g., volume-based alerts) beyond simple price crossover.
- Adding global alert creation points outside the context of a specific security.

## Decisions

1.  **Unified Modal Component**: Create `src/lib/components/charts/dialogs/price-alert.svelte`. This component will handle targeted alert creation for a specific `securityId`.
2.  **Stateful Modal Manager**: Implement `src/lib/components/charts/dialogs/price-alert.svelte.ts` (following the Svelte 5 class-based pattern) to manage modal visibility, loading states, and error handling.
3.  **Right Sidebar (ActionsSidebar) Enhancement**:
    -   Update `AlertsGroup.svelte` to include a `Plus` icon in the `Sidebar.GroupAction` slot.
    -   Move the expand/collapse logic to the `Sidebar.GroupLabel` or use a standard chevron.
    -   Clicking the `+` button will trigger the `PriceAlert` modal for the current `securityId`.
4.  **UX Enhancement**: Fetch and display the last close price in the modal using `marketService.getLastClosePrice`.

## Risks / Trade-offs

-   **Contextual Limitation**: Limiting the modal to the security page sidebar means users cannot add alerts while on the dashboard, but it maintains a cleaner, more focused workflow for the initial implementation.

