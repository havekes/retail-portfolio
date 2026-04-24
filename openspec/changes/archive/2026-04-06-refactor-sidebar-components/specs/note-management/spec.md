## ADDED Requirements

### Requirement: Note Group
The `NotesGroup` component MUST manage the fetching and display of notes for a security.

#### Scenario: Successful note fetch
- **WHEN** the `NotesGroup` is expanded for a security
- **THEN** it SHALL fetch the notes list from the backend
- **AND** it SHALL display a `<Skeleton />` while loading
- **AND** it SHALL display the notes list on success

#### Scenario: Note fetch error
- **WHEN** the note fetch fails
- **THEN** it SHALL display a `<SidebarError />` component
- **AND** it SHALL provide a retry mechanism that calls the fetch function again

### Requirement: Note List Item
Each note in the list MUST support viewing and deletion actions.

#### Scenario: Viewing a note
- **WHEN** a user clicks on a note list item
- **THEN** it SHALL open the note view dialog

#### Scenario: Deleting a note via keyboard
- **WHEN** a note item is hovered or focused
- **AND** the user presses "Backspace" or "Delete"
- **THEN** it SHALL trigger the deletion confirmation dialog

### Requirement: Note Modals
Note-related dialogs MUST use a centralized `ModalState` and support primary action on "Enter".

#### Scenario: Creating a note
- **WHEN** the creation dialog is open
- **AND** the user presses "Enter"
- **THEN** it SHALL trigger the note creation
