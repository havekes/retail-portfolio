## ADDED Requirements

### Requirement: Collapsible Sidebar Component
The `Sidebar.Root` MUST support a `collapsible` state that can be toggled between "expanded" and "collapsed".

#### Scenario: Sidebar state toggle
- **WHEN** the user interacts with the toggle mechanisms
- **THEN** the sidebar SHALL transition between expanded and collapsed states

### Requirement: Rail Toggle Mechanism
The user MUST be able to toggle the sidebar's state by clicking on its right border (the "rail").

#### Scenario: Clicking on the rail
- **WHEN** the user clicks on the sidebar rail
- **THEN** the sidebar SHALL toggle its current state

### Requirement: Floating Toggle Button
A floating button (chevron) MUST be added in the middle of the sidebar's border to allow for easier toggling.

#### Scenario: Clicking on the floating button
- **WHEN** the user clicks the floating chevron button
- **THEN** the sidebar SHALL toggle its current state

### Requirement: Sidebar Content Adaptation
When collapsed, the sidebar MUST only show icons or a slimmed-down version of its content.

#### Scenario: Visual change on collapse
- **WHEN** the sidebar is collapsed
- **THEN** only the icons of the sidebar menu items SHALL be visible

### Requirement: User Menu Icon on Collapse
When the sidebar is collapsed, the user menu in the footer MUST show a user profile icon (`CircleUser`) instead of the user's email address.

#### Scenario: User menu in collapsed sidebar
- **WHEN** the sidebar is collapsed
- **THEN** the user menu SHALL display a `CircleUser` icon
- **AND** the user's email address SHALL be hidden
