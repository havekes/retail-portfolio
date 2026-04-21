## ADDED Requirements

### Requirement: Navigate to Account Details
The system SHALL allow users to navigate from the Accounts list to an Account Details page by clicking on an account name.

#### Scenario: User clicks account name
- **WHEN** the user clicks on an account name in the accounts list page
- **THEN** the system navigates to the Account Details page for that specific account

### Requirement: Display Account Holdings
The system SHALL display a list of all security holdings for the selected account on the Account Details page.

#### Scenario: View account details
- **WHEN** the user visits the Account Details page
- **THEN** the system displays a table or list of all securities held in that account
- **AND** the list includes the security name, shares owned, total amount (market value), and profit/loss

### Requirement: Navigate to Security Details
The system SHALL allow users to navigate from the Account Details holdings list to the Security Details page by clicking on a security name.

#### Scenario: User clicks security name in holdings list
- **WHEN** the user clicks on a security name in the Account Details holdings list
- **THEN** the system navigates to the Security Details page for that specific security
