## ADDED Requirements

### Requirement: Create price alert
The system SHALL allow users to create price alerts for a security.

#### Scenario: Alert creation
- **WHEN** user clicks "Add price alert" action
- **THEN** an alert creation dialog opens with price input and condition selector
- **THEN** user can specify target price and condition (above/below)

#### Scenario: Successful alert creation
- **WHEN** user submits a valid alert configuration
- **THEN** the alert is saved and appears in the alerts list
- **THEN** a confirmation message is displayed

#### Scenario: Invalid alert creation
- **WHEN** user submits invalid alert data (missing price, invalid condition)
- **THEN** form validation errors are displayed
- **THEN** the alert is not created

### Requirement: List existing alerts
The system SHALL display a list of existing price alerts for the security.

#### Scenario: Alerts list display
- **WHEN** user expands the price alerts group
- **THEN** all active alerts for the security are displayed
- **THEN** each alert shows target price, condition, and creation date

#### Scenario: No alerts exist
- **WHEN** user has no alerts for the security
- **THEN** an empty state message is displayed
- **THEN** "Add price alert" action remains available

### Requirement: Alert notification
The system SHALL notify users when their price alerts are triggered.

#### Scenario: Alert triggered
- **WHEN** security price meets alert condition
- **THEN** user receives a notification
- **THEN** the alert is marked as triggered in the list

#### Scenario: Notification delivery
- **WHEN** alert is triggered
- **THEN** notification appears in-app
- **THEN** optional email notification is sent if configured

### Requirement: Delete price alert
The system SHALL allow users to delete price alerts.

#### Scenario: Delete alert
- **WHEN** user clicks delete on an alert
- **THEN** a confirmation dialog appears
- **THEN** upon confirmation, the alert is deleted and removed from list

#### Scenario: Delete triggered alert
- **WHEN** user deletes a triggered alert
- **THEN** the alert is permanently removed
- **THEN** associated notification history is preserved

### Requirement: Alert status display
The system SHALL clearly show alert status in the list.

#### Scenario: Active alert display
- **WHEN** alert is active and not triggered
- **THEN** alert shows active status indicator
- **THEN** alert appears at the top of the list

#### Scenario: Triggered alert display
- **WHEN** alert has been triggered
- **THEN** alert shows triggered status with timestamp
- **THEN** triggered alerts are visually distinguished from active alerts
