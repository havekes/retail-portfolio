## Context

The current `app-sidebar.svelte` uses the `Sidebar.Root` component from the UI library but doesn't implement a toggle mechanism. The UI library already provides a `Sidebar.Rail` and a `SidebarState` with `toggle()` functionality, which are not currently being used in the application layout.

## Goals / Non-Goals

**Goals:**
- Enable the collapsible feature of the sidebar by setting `collapsible="icon"`.
- Implement a dual-toggle mechanism: clicking the sidebar rail and a new floating chevron button.
- Ensure the sidebar transition is smooth and visual changes (hiding text) are handled correctly.

**Non-Goals:**
- Changing the layout of the sidebar content itself beyond standard responsive behavior.
- Persistent state management in `localStorage` (this can be a follow-up task).

## Decisions

- **Toggle Logic**: Leverage the existing `sidebar.toggle()` method from `SidebarState` (provided by `useSidebar()`).
- **Sidebar Rail**: Add `Sidebar.Rail` to `app-sidebar.svelte`. It provides the border click functionality and appropriate cursors.
- **Floating Button**: Create a new `SidebarToggle` component (or add it directly to `Sidebar.Rail`) that renders a chevron icon. This button will be positioned absolutely on the border and centered vertically.
- **User Menu Icon**: Use a conditional check on `sidebar.state` within the user menu to swap the email string for a `CircleUser` icon from `@lucide/svelte/icons/circle-user`.
- **Visuals**: Use `ChevronLeft` / `ChevronRight` from `@lucide/svelte` for the toggle button, rotating based on the sidebar state.
- **Component Placement**: The `Sidebar.Rail` will be added inside `Sidebar.Root` in `app-sidebar.svelte`.

## Risks / Trade-offs

- **Click Interference**: Ensure the floating button click doesn't conflict with the rail's click handler. Both should trigger the same toggle action.
- **Responsive Behavior**: Verify the sidebar behaves correctly on mobile (where it typically uses a sheet). The `SidebarState` already handles mobile specifically in `toggle()`.
