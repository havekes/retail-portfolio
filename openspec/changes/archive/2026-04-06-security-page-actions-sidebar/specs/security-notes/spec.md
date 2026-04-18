## ADDED Requirements

### Requirement: Add note to security
The system SHALL allow users to add notes to a security.

#### Scenario: Note creation dialog
- **WHEN** user clicks "Add note" action
- **THEN** a note creation dialog opens with text area
- **THEN** user can enter note content with rich text formatting

#### Scenario: Successful note creation
- **WHEN** user submits a note with content
- **THEN** the note is saved and appears in the notes list
- **THEN** the dialog closes automatically

#### Scenario: Empty note prevention
- **WHEN** user attempts to submit empty note
- **THEN** form validation prevents submission
- **THEN** error message prompts user to add content

### Requirement: List notes with summaries
The system SHALL display a list of existing notes with summaries.

#### Scenario: Notes list display
- **WHEN** user expands the notes group
- **THEN** all notes for the security are displayed chronologically
- **THEN** each note shows a summary (first 100 characters) and date

#### Scenario: No notes exist
- **WHEN** user has no notes for the security
- **THEN** an empty state message is displayed
- **THEN** "Add note" action remains available

### Requirement: View full note
The system SHALL allow users to view the complete content of a note.

#### Scenario: Open note
- **WHEN** user clicks on a note summary
- **THEN** the full note content opens in a dialog or expands inline
- **THEN** note metadata (date, last edited) is visible

#### Scenario: Close note view
- **WHEN** user closes the full note view
- **THEN** the note returns to summary view
- **THEN** scroll position is preserved

### Requirement: Edit note
The system SHALL allow users to edit existing notes.

#### Scenario: Edit note
- **WHEN** user clicks edit on a note
- **THEN** the note opens in edit mode with current content
- **THEN** user can modify the content

#### Scenario: Save edited note
- **WHEN** user saves changes to a note
- **THEN** the note is updated with new content
- **THEN** last edited timestamp is updated
- **THEN** the note summary reflects changes

### Requirement: Delete note
The system SHALL allow users to delete notes.

#### Scenario: Delete note
- **WHEN** user clicks delete on a note
- **THEN** a confirmation dialog appears
- **THEN** upon confirmation, the note is deleted and removed from list

### Requirement: Note sorting
The system SHALL allow users to sort notes by date.

#### Scenario: Sort by date descending
- **WHEN** notes are displayed in default sort order
- **THEN** most recent notes appear at the top
- **THEN** sort indicator shows current order

#### Scenario: Sort by date ascending
- **WHEN** user clicks to change sort order
- **THEN** oldest notes appear at the top
- **THEN** sort indicator updates to reflect new order
