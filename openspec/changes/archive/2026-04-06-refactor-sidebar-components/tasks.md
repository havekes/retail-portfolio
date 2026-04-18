## 1. Preparation and Organization

- [x] 1.1 Move `document-list-item.svelte`, `document-upload-dialog.svelte`, `document-view-dialog.svelte`, `documents-group.svelte` to `frontend/src/lib/components/actions-sidebar/document/`
- [x] 1.2 Move `note-creation-dialog.svelte`, `note-list-item.svelte`, `note-view-dialog.svelte`, `notes-group.svelte` to `frontend/src/lib/components/actions-sidebar/note/`
- [x] 1.3 Move `ai-analysis-group.svelte`, `ai-response-dialog.svelte` to `frontend/src/lib/components/actions-sidebar/ai/`
- [x] 1.4 Update imports in `frontend/src/routes/security/[security_id]/+page.svelte` to reflect the new file locations and unified prop names.

## 2. Refactor Document Components

- [x] 2.1 Refactor `DocumentsGroup.svelte`: Implement `fetchDocuments`, handle loading/error states with `Skeleton` and `SidebarError`, use `GroupTitle`, and use `ModalState` for upload/view dialogs.
- [x] 2.2 Refactor `DocumentListItem.svelte`: Add keyboard shortcuts (Delete/Backspace), focus states, and use `formatDate` from global utils.
- [x] 2.3 Refactor `DocumentUploadDialog.svelte`: Use `ModalState`, handle "Enter" to upload, and ensure Shadcn UI consistency.
- [x] 2.4 Refactor `DocumentViewDialog.svelte`: Use `ModalState` and ensure Shadcn UI consistency.

## 3. Refactor Note Components

- [x] 3.1 Refactor `NotesGroup.svelte`: Implement `fetchNotes`, handle loading/error states, use `GroupTitle`, and use `ModalState` for creation/view dialogs.
- [x] 3.2 Refactor `NoteListItem.svelte`: Add keyboard shortcuts, focus states, and use `formatDate`.
- [x] 3.3 Refactor `NoteCreationDialog.svelte`: Use `ModalState`, handle "Enter" to create.
- [x] 3.4 Refactor `NoteViewDialog.svelte`: Use `ModalState`.

## 4. Refactor AI Components

- [x] 4.1 Refactor `AIAnalysisGroup.svelte`: Implement `handleRequestAnalysis`, handle loading/error states, use `GroupTitle`, and use `ModalState` for the response dialog.
- [x] 4.2 Refactor `AIResponseDialog.svelte`: Use `ModalState`.

## 5. Global Cleanup and Validation

- [x] 5.1 Ensure `formatDate` is in `@/utils/date.ts` and all components use it.
- [x] 5.2 Replace any standard `confirm()` calls with `ConfirmationModal`.
- [x] 5.3 Remove any redundant `.ts` or `.svelte.ts` files that were replaced by in-component logic.
- [x] 5.4 Verify all keyboard shortcuts and focus states across refactored components.
- [x] 5.5 Run linting and type checks on refactored files.
