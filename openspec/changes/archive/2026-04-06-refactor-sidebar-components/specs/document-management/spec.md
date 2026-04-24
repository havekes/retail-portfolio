## ADDED Requirements

### Requirement: Document Group
The `DocumentsGroup` component MUST manage the fetching and display of documents for a security.

#### Scenario: Successful document fetch
- **WHEN** the `DocumentsGroup` is expanded for a security
- **THEN** it SHALL fetch the documents list from the backend
- **AND** it SHALL display a `<Skeleton />` while loading
- **AND** it SHALL display the documents list on success

#### Scenario: Document fetch error
- **WHEN** the document fetch fails
- **THEN** it SHALL display a `<SidebarError />` component
- **AND** it SHALL provide a retry mechanism that calls the fetch function again

### Requirement: Document List Item
Each document in the list MUST support viewing and deletion actions.

#### Scenario: Viewing a document
- **WHEN** a user clicks on a document list item
- **THEN** it SHALL open the document view dialog

#### Scenario: Deleting a document via keyboard
- **WHEN** a document item is hovered or focused
- **AND** the user presses "Backspace" or "Delete"
- **THEN** it SHALL trigger the deletion confirmation dialog

### Requirement: Document Modals
Document-related dialogs MUST use a centralized `ModalState` and support primary action on "Enter".

#### Scenario: Uploading a document
- **WHEN** the upload dialog is open
- **AND** the user presses "Enter"
- **THEN** it SHALL trigger the upload action
