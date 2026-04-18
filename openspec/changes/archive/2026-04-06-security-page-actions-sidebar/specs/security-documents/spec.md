## ADDED Requirements

### Requirement: Add document to security
The system SHALL allow users to upload documents to a security.

#### Scenario: Document upload dialog
- **WHEN** user clicks "Add document" action
- **THEN** a document upload dialog opens with file picker
- **THEN** user can select files from their device

#### Scenario: File type validation
- **WHEN** user selects a file for upload
- **THEN** file type is validated against allowed formats (PDF, DOC, DOCX, TXT)
- **THEN** invalid file types are rejected with error message

#### Scenario: File size validation
- **WHEN** user selects a file larger than maximum size (10MB)
- **THEN** upload is rejected with size limit error
- **THEN** user is prompted to select a smaller file

#### Scenario: Successful document upload
- **WHEN** user uploads a valid document
- **THEN** the document is saved and appears in the documents list
- **THEN** upload progress is shown during the process
- **THEN** the dialog closes upon completion

### Requirement: List existing documents
The system SHALL display a list of existing documents for the security.

#### Scenario: Documents list display
- **WHEN** user expands the documents group
- **THEN** all documents for the security are displayed
- **THEN** each document shows filename, upload date, and file size

#### Scenario: No documents exist
- **WHEN** user has no documents for the security
- **THEN** an empty state message is displayed
- **THEN** "Add document" action remains available

### Requirement: View document
The system SHALL allow users to view or download documents.

#### Scenario: View PDF document
- **WHEN** user clicks on a PDF document
- **THEN** the document opens in a preview dialog or new tab
- **THEN** user can navigate through document pages

#### Scenario: Download document
- **WHEN** user clicks download on a document
- **THEN** the document file is downloaded to user's device
- **THEN** original filename is preserved

### Requirement: Delete document
The system SHALL allow users to delete documents.

#### Scenario: Delete document
- **WHEN** user clicks delete on a document
- **THEN** a confirmation dialog appears
- **THEN** upon confirmation, the document is deleted and removed from list

### Requirement: Document metadata
The system SHALL display relevant metadata for each document.

#### Scenario: Metadata display
- **WHEN** document is listed
- **THEN** filename, upload date, file size, and file type icon are shown
- **THEN** metadata is formatted in a readable way

### Requirement: Document search
The system SHALL allow users to filter documents by name.

#### Scenario: Filter documents
- **WHEN** user types in document filter input
- **THEN** document list filters by filename match
- **THEN** no results message appears if no matches found
