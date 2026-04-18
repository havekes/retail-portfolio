## ADDED Requirements

### Requirement: Sidebar component structure
The system SHALL provide a reusable ActionsSidebar component with expandable action groups.

#### Scenario: Default state
- **WHEN** ActionsSidebar component mounts
- **THEN** all action groups are collapsed by default
- **THEN** each group displays a header with icon and label

#### Scenario: Expand group
- **WHEN** user clicks on a group header
- **THEN** the group expands to show its actions
- **THEN** the header icon rotates to indicate expanded state

#### Scenario: Collapse group
- **WHEN** user clicks on an expanded group header
- **THEN** the group collapses to hide its actions
- **THEN** the header icon returns to default state

### Requirement: Grouped actions layout
The system SHALL organize actions into distinct groups with visual separation.

#### Scenario: Multiple groups
- **WHEN** multiple action groups are rendered
- **THEN** each group is visually separated by a divider
- **THEN** groups maintain consistent padding and spacing

### Requirement: Action item display
The system SHALL display individual actions as clickable menu items within groups.

#### Scenario: Action item rendering
- **WHEN** an action is rendered in a group
- **THEN** the action displays an icon, label, and optional badge
- **THEN** the action has hover and focus states for accessibility

#### Scenario: Action click
- **WHEN** user clicks an action item
- **THEN** the associated action handler is invoked
- **THEN** optional dialog or panel opens based on action type

### Requirement: Responsive behavior
The system SHALL adapt the sidebar layout for different screen sizes.

#### Scenario: Mobile view
- **WHEN** screen width is below mobile breakpoint
- **THEN** sidebar converts to a bottom sheet or drawer
- **THEN** swipe gestures are available to dismiss

#### Scenario: Desktop view
- **WHEN** screen width is at or above desktop breakpoint
- **THEN** sidebar displays as a fixed left panel
- **THEN** sidebar width is collapsible via rail or trigger

### Requirement: Accessibility
The system SHALL ensure the ActionsSidebar is accessible to all users.

#### Scenario: Keyboard navigation
- **WHEN** user navigates with keyboard
- **THEN** all actions are focusable via Tab key
- **THEN** Enter or Space activates the focused action

#### Scenario: Screen reader support
- **WHEN** screen reader is active
- **THEN** group expansion state is announced
- **THEN** action labels are properly read aloud
