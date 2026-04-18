## Why

The current implementation of `document`, `note`, and `ai` components in the `actions-sidebar` is inconsistent with the newly established patterns in `price-alert`. Logic is scattered, state management is not centralized using `ModalState`, and UI feedback (loading/error states) is not uniformly handled at the group level, leading to a fragmented user experience and harder maintenance.

## What Changes

- **Refactor `document` components**: Move files to `frontend/src/lib/components/actions-sidebar/document/`, consolidate logic, use `ModalState`, and implement group-level loading/error handling.
- **Refactor `note` components**: Move files to `frontend/src/lib/components/actions-sidebar/note/`, consolidate logic, use `ModalState`, and implement group-level loading/error handling.
- **Refactor `ai` components**: Move files to `frontend/src/lib/components/actions-sidebar/ai/`, consolidate logic, use `ModalState`, and implement group-level loading/error handling.
- **Standardize UI/UX**: Implement `<Skeleton />` for loading, `<SidebarError />` for errors, `<ConfirmationModal />` for destructive actions, and keyboard shortcuts (Enter/Delete) across all these components.
- **Clean up**: Remove redundant `.ts` or `.svelte.ts` files and ensure all event handlers follow the `handle*` and `fetch*` naming conventions.

## Capabilities

### New Capabilities
- `document-management`: Capability to upload, view, and delete documents for a security.
- `note-management`: Capability to create, view, and delete notes for a security.
- `ai-analysis-sidebar`: Capability to request and view AI-generated analysis for a security.

### Modified Capabilities
<!-- None -->

## Impact

- **Affected Code**: `frontend/src/lib/components/actions-sidebar/` file organization and component structure.
- **Utilities**: `frontend/src/lib/utils/` will house reusable logic like `formatDate`.
- **Dependencies**: Greater reliance on Shadcn UI components and `ModalState` utility.
