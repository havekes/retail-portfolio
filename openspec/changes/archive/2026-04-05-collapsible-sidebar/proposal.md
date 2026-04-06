## Why

The current sidebar is fixed and takes up significant screen real estate, which can be suboptimal for users on smaller screens or those who want to focus on the main content. Making the sidebar collapsible provides a more flexible and customizable user interface.

## What Changes

- **Collapsible Sidebar**: Modify the `Sidebar.Root` to support a collapsible state.
- **Toggle via Rail**: Enable collapsing/expanding by clicking the sidebar's border (rail).
- **Floating Toggle Button**: Add a chevron-style floating button in the middle of the sidebar border for a more intuitive toggle action.
- **User Menu Icon**: Show a user profile icon instead of the email address when the sidebar is collapsed.
- **State Persistence**: (Optional but recommended) Ensure the sidebar state is consistent across page reloads.

## Capabilities

### New Capabilities
- `collapsible-sidebar`: Implementation of a collapsible sidebar with multiple toggle methods (rail click and floating chevron).

### Modified Capabilities
- (None)

## Impact

- `frontend/src/lib/components/layout/app-sidebar.svelte`: Main component to be updated.
- `frontend/src/lib/components/ui/sidebar/`: Existing sidebar UI components will be utilized and potentially refined.
