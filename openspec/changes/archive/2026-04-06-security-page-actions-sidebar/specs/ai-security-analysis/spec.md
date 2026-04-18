## ADDED Requirements

### Requirement: Explain fundamentals
The system SHALL provide AI-powered explanation of a security's fundamentals.

#### Scenario: Request fundamentals explanation
- **WHEN** user clicks "Explain fundamentals" action
- **THEN** an AI analysis dialog opens with loading indicator
- **THEN** user's existing notes are included as context

#### Scenario: Fundamentals explanation response
- **WHEN** AI generates the explanation
- **THEN** a comprehensive summary of fundamentals is displayed
- **THEN** explanation covers business model, financial health, and key metrics

#### Scenario: No fundamentals data available
- **WHEN** insufficient data exists for the security
- **THEN** user is informed that analysis is limited
- **THEN** available information is still provided

### Requirement: Summarize notes
The system SHALL provide AI-powered summarization of user's notes for a security.

#### Scenario: Request notes summary
- **WHEN** user clicks "Summarize my notes" action
- **THEN** an AI analysis dialog opens with loading indicator
- **THEN** all user notes for the security are retrieved

#### Scenario: Notes summary response
- **WHEN** AI generates the summary
- **THEN** a concise summary of key points from all notes is displayed
- **THEN** summary highlights themes, decisions, and action items

#### Scenario: No notes exist
- **WHEN** user has no notes for the security
- **THEN** user is informed that no notes exist to summarize
- **THEN** option to add a note is provided

### Requirement: Portfolio debate
The system SHALL provide AI-powered analysis debating whether to add a security to portfolio.

#### Scenario: Request portfolio debate
- **WHEN** user clicks "Debate whether I should add this stock" action
- **THEN** an AI analysis dialog opens with loading indicator
- **THEN** user's current portfolio and notes are included as context

#### Scenario: Debate response
- **WHEN** AI generates the debate
- **THEN** both bull and bear cases are presented
- **THEN** analysis considers portfolio fit, diversification, and user's investment goals

#### Scenario: Debate with existing position
- **WHEN** user already holds the security
- **THEN** AI analyzes whether to add to position, hold, or reduce
- **THEN** current position size and performance are factored into analysis

### Requirement: AI response formatting
The system SHALL present AI responses in a readable, structured format.

#### Scenario: Formatted response
- **WHEN** AI generates analysis
- **THEN** response uses headings, bullet points, and paragraphs for readability
- **THEN** key insights are highlighted or emphasized

#### Scenario: Response actions
- **WHEN** AI response is displayed
- **THEN** user can copy the response to clipboard
- **THEN** user can save the response as a note

### Requirement: AI loading state
The system SHALL provide feedback during AI generation.

#### Scenario: AI processing
- **WHEN** AI is generating a response
- **THEN** loading indicator is displayed with estimated time
- **THEN** user can cancel the request if needed

#### Scenario: AI error
- **WHEN** AI generation fails or times out
- **THEN** user is informed of the error
- **THEN** retry option is provided

### Requirement: AI context inclusion
The system SHALL include relevant user context in AI requests.

#### Scenario: Context gathering
- **WHEN** any AI action is triggered
- **THEN** user's notes for the security are retrieved
- **THEN** user's portfolio holdings and allocation are included
- **THEN** recent price data and technical indicators are provided
