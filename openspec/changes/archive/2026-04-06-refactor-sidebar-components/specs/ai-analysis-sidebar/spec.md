## ADDED Requirements

### Requirement: AI Analysis Group
The `AIAnalysisGroup` component MUST manage the initiation and display of AI analysis for a security.

#### Scenario: Requesting AI analysis
- **WHEN** the user initiates an AI analysis request
- **THEN** it SHALL display a `<Skeleton />` or loading indicator
- **AND** it SHALL open the AI response dialog on success

#### Scenario: AI Analysis error
- **WHEN** the AI analysis request fails
- **THEN** it SHALL display a `<SidebarError />` component
- **AND** it SHALL provide a retry mechanism

### Requirement: AI Response Dialog
The AI analysis response MUST be displayed in a dialog using `ModalState`.

#### Scenario: Displaying AI response
- **WHEN** the AI analysis is complete
- **THEN** the `AIResponseDialog` SHALL be opened via `ModalState`
- **AND** it SHALL show the generated analysis text
