## 1. Setup and Component Preparation

- [x] 1.1 Update `app-sidebar.svelte` to include the `collapsible="icon"` prop on `Sidebar.Root`.
- [x] 1.2 Import necessary icons (`ChevronLeft`, `ChevronRight`) in `app-sidebar.svelte`.

## 2. Implement Toggle Mechanisms

- [x] 2.1 Add `Sidebar.Rail` component to `app-sidebar.svelte` within the `Sidebar.Root`.
- [x] 2.2 Create a floating toggle button within the `Sidebar.Rail`.
- [x] 2.3 Position the floating button absolutely at the center-right of the rail.
- [x] 2.4 Bind the `onclick` event of the floating button to `sidebar.toggle()`.

## 3. Visual Refinement and Styling

- [x] 3.1 Use the current sidebar state (expanded/collapsed) to rotate or change the chevron icon direction.
- [x] 3.2 Ensure the floating button is only visible or highlighted when hovering over the sidebar edge/rail.
- [x] 3.3 Verify that the sidebar content correctly collapses to show only icons.
- [x] 3.4 Update the user menu in `app-sidebar.svelte` to show `CircleUser` icon when collapsed.

## 4. Verification

- [x] 4.1 Verify that clicking the sidebar rail toggles the sidebar state.
- [x] 4.2 Verify that clicking the floating button toggles the sidebar state.
- [x] 4.3 Verify the sidebar behavior on mobile screens (ensure no regressions).
