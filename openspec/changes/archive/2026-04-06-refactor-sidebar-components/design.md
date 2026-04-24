## Context

The `actions-sidebar` contains several groups: Price Alerts, Documents, Notes, and AI Analysis. `price-alert` was recently refactored to use Svelte 5 runes, centralized `ModalState`, and improved UI feedback. `document`, `note`, and `ai` components still use an older pattern with logic split across multiple files or less consistent state management.

## Goals / Non-Goals

**Goals:**
- Unify the architecture of all `actions-sidebar` components.
- Move logic into `.svelte` files for better cohesion.
- Centralize modal state using the `ModalState` utility.
- Standardize data fetching and loading states at the group level.
- Improve UX with consistent loading/error states and keyboard shortcuts.
- Reorganize files into dedicated sub-directories.

**Non-Goals:**
- Adding new features to Documents, Notes, or AI Analysis.
- Refactoring backend services or APIs.
- Redesigning the overall sidebar layout.

## Decisions

1. **Sub-directory Organization**: Each group (document, note, ai) will have its own directory under `actions-sidebar/`. This improves discoverability and mirrors the `price-alert` structure.
2. **Logic Consolidation**: Logic currently in separate `.ts` or `.svelte.ts` files will be moved into the `<script>` block of the corresponding `.svelte` component, unless it's genuinely global (in which case it goes to `@/utils`).
3. **ModalState for All Dialogs**: All dialogs will be controlled by a `ModalState` instance passed as a prop from the parent group. This ensures a consistent interface for opening/closing/resetting modal state.
4. **Group-Level Data Ownership**: The `Group` component (e.g., `DocumentsGroup.svelte`) will be responsible for fetching data and managing the loading/error state for its children.
5. **Shadcn UI & Minimal Tailwind**: Leverage existing Shadcn components (Dialog, Button, Skeleton, etc.) and avoid custom utility classes where possible to maintain design consistency.

## Risks / Trade-offs

- **[Risk]** Breaking existing functionality during the move. -> **[Mitigation]** Manual verification and regression testing of all actions (upload, view, delete, etc.).
- **[Risk]** Merge conflicts if other changes are happening in the sidebar. -> **[Mitigation]** Keep the refactor focused and apply changes incrementally.
