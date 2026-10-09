# Plan: F-rewind-polish-T01

**Approach:**
Build a lightweight Svelte 5 toast state store and container component mounted in the root layout, providing global toast capabilities. Wire snapshot save events and duplicate attempt guards in the security chart page to trigger clear toast feedback (success, info, error) and reactively auto-reveal/update the rewind timeline upon snapshot load and creation. Preserve manual timeline toggle capabilities and update component tests to verify auto-visibility, deduplication feedback, live updates, and keyboard/button save flows.

**Files:**
- `frontend/src/lib/components/ui/toast/toast.svelte.ts` — create: Svelte 5 `$state`-based toast store supporting `success`, `error`, `info`, `warning`, auto-dismiss timers, and dismiss actions.
- `frontend/src/lib/components/ui/toast/toaster.svelte` — create: Toast container component rendering active toasts with accessible roles, Lucide icons, close buttons, and smooth styling.
- `frontend/src/lib/components/ui/toast/index.ts` — create: Public exports for `toast` store, `Toaster` component, and toast types.
- `frontend/src/lib/components/ui/toast/toast.test.ts` — create: Unit tests for toast store actions, auto-dismiss, and toaster rendering.
- `frontend/src/routes/+layout.svelte` — modify: Render `<Toaster />` in root layout for application-wide toast notifications.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: Auto-show rewind timeline when `securitySnapshots.length > 0` on load; show success toast and reveal timeline when first snapshot is saved; show info toast when attempting duplicate unchanged saves; show error toast on save failure; ensure live update of `securitySnapshots`.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: Add unit and integration tests for save toasts (button and Cmd/Ctrl+S), duplicate save feedback, timeline auto-visibility on initial load when snapshots exist, first snapshot save auto-reveal, and live marker updates. Update existing timeline toggle tests for auto-visible default.
- `frontend/.prettierignore` — modify: Ensure `.svelte-kit` is ignored by prettier so `npm run lint` passes cleanly.

**Steps:**
1. Create `frontend/src/lib/components/ui/toast/toast.svelte.ts` implementing `ToastState` using Svelte 5 runes (`$state`) with `add`, `remove`, `clear`, `success`, `error`, `info`, and `warning` helpers and configurable duration auto-dismiss.
2. Create `frontend/src/lib/components/ui/toast/toaster.svelte` displaying active toasts with distinct icons (`Check`, `AlertCircle`, `Info`, `TriangleAlert`), dismiss buttons, and accessible markup (`role="status"` / `role="alert"`), and export from `frontend/src/lib/components/ui/toast/index.ts`.
3. Add unit tests in `frontend/src/lib/components/ui/toast/toast.test.ts` verifying toast store actions, auto-removal on timeout, manual dismissal, and helper methods.
4. Mount `<Toaster />` in `frontend/src/routes/+layout.svelte` so toasts can be triggered across the application.
5. In `frontend/src/routes/security/[security_id]/+page.svelte`:
   - In `loadSnapshots()`, automatically set `isTimelineVisible = true` when `securitySnapshots.length > 0` (and reset `isTimelineVisible = false` on security change in the route `$effect`).
   - In `handleSaveSnapshot()`, display `toast.info('Chart snapshot already up to date')` (or 'No changes to save') when drawings are unchanged from the previous snapshot without creating a snapshot.
   - On successful snapshot creation, append to `securitySnapshots`, auto-reveal the timeline bar (`isTimelineVisible = true`) if initially hidden or on first snapshot, trigger `showSaveFeedback()`, and show `toast.success('Chart snapshot saved')`.
   - On snapshot creation failure, log error and show `toast.error('Failed to save chart snapshot')`.
6. Update `frontend/src/routes/security/[security_id]/page.svelte.test.ts`:
   - Verify success toast is displayed on snapshot save via Save button and Cmd/Ctrl+S shortcut.
   - Verify duplicate snapshot attempts display info toast and do not call `snapshotsService.createSnapshot`.
   - Verify timeline bar is automatically visible on initial load when security has 1+ snapshots.
   - Verify timeline bar is not visible initially when security has 0 snapshots, and saving the first snapshot immediately reveals the timeline bar with the newly created marker.
   - Verify saving subsequent snapshots updates timeline markers and domain without page reload.
   - Update existing timeline toggle tests to account for initial auto-visibility when snapshots exist.
7. Run verification commands: `npm run check`, `npm run test:run`, and `npm run lint` in `frontend/`.

**Verification:**
- Run `npm run check` in `frontend/` — ensure zero TypeScript and Svelte diagnostic errors or warnings.
- Run `npm run test:run` in `frontend/` — ensure all tests in `toast.test.ts`, `page.svelte.test.ts`, `drawing-toolbar.test.ts`, and `rewind-timeline.test.ts` pass:
  - Acceptance criterion 1: Test verifies toast containing "Chart snapshot saved" appears on button click and Cmd/Ctrl+S.
  - Acceptance criterion 2: Test verifies duplicate unchanged snapshot attempt shows info feedback and does not call `createSnapshot`.
  - Acceptance criterion 3: Test verifies timeline element (`[data-testid="rewind-timeline"]`) is in document on initial load when snapshots are returned from `getSnapshots`.
  - Acceptance criterion 4: Test verifies saving first snapshot when `snapshots = []` immediately renders timeline and marker without page reload.
  - Acceptance criterion 5: Test verifies saving subsequent snapshot updates snapshot markers in the timeline.
  - Acceptance criterion 6: Test verifies clicking toolbar timeline button toggles timeline visibility.
  - Acceptance criterion 7: `npm run check`, `npm run test:run`, `npm run lint` all pass with exit code 0.

**Risks / watch-outs:**
- Existing component tests in `page.svelte.test.ts` assumed `isTimelineVisible` defaulted to `false` even when snapshots were mocked; updating default behavior to auto-show on snapshot count >= 1 requires adjusting those test setups (either by testing the toggle behavior or starting from empty snapshots where appropriate).
- Ensure toast container has `pointer-events-none` on outer wrapper and `pointer-events-auto` on individual toast cards so chart interactions and clicks are not blocked.
