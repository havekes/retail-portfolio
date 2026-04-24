## ADDED Requirements

### Requirement: Contextual Price Alert Creation
The security page's right sidebar (ActionsSidebar) should include a prominent button in the "Price Alerts" group header to add an alert for that specific security.

#### Scenario: Trigger Manual Alert from Right Sidebar
- **WHEN** the user clicks the `+` icon in the "Price Alerts" group header in the ActionsSidebar
- **THEN** the manual price alert creation modal should open for the current security.

### Requirement: Guided Manual Entry
The manual price alert creation modal should provide contextual information to help the user set accurate alert conditions.

#### Scenario: Set Alert with Current Price Context
- **WHEN** the manual alert creation modal opens for a security
- **THEN** the modal should display the security's symbols, name, and most recent close price, allowing the user to easily configure "above" or "below" conditions.
