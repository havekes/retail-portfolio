## ADDED Requirements

### Requirement: Average buying price calculation
The system SHALL calculate the weighted average buying price for a security across all accounts where the user has a position.

#### Scenario: Multiple accounts with positions
- **WHEN** user has 10 shares at $100 in Account A and 20 shares at $110 in Account B
- **THEN** the average buying price is calculated as $106.67
- **THEN** this value is available to the frontend

#### Scenario: Single account with position
- **WHEN** user has 10 shares at $100 in only one account
- **THEN** the average buying price is $100

#### Scenario: No positions
- **WHEN** user does not own any shares of the security
- **THEN** no average buying price is calculated

### Requirement: Average buying price visualization
The system SHALL display a horizontal line on the security chart at the calculated average buying price.

#### Scenario: Displaying the line
- **WHEN** user views a security they own
- **THEN** a horizontal line appears on the chart at the average buying price
- **THEN** the line is labeled "Avg Price" with the value

#### Scenario: Line visibility toggle
- **WHEN** user toggles the visibility of the average price line
- **THEN** the line is shown or hidden according to the toggle state

#### Scenario: Distinct styling
- **WHEN** the average price line is displayed
- **THEN** it has a visually distinct color or style compared to other indicators (e.g., dashed line)

### Requirement: API data enhancement
The holdings API SHALL include the `average_cost` for each account position.

#### Scenario: Fetching holdings
- **WHEN** frontend requests holdings for a security
- **THEN** the response includes `average_cost` for each account holding record
- **THEN** the `average_cost` is a decimal value representing the entry price in the security's currency
