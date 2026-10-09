## Plan

**Approach:**
Transition rewind snapshot storage from `UserPreferences` to the dedicated `snapshotsService` by introducing a component-level `securitySnapshots` state loaded via `snapshotsService.getSnapshots` on mount and security changes. Snapshot creation in `handleSaveSnapshot` calls `snapshotsService.createSnapshot` and updates local state on success, retaining the existing content-equality dedupe check, while scrubbing evaluates against `securitySnapshots` with an overloaded `findSnapshotAtOrBefore` utility.

**Files:**
- `frontend/src/lib/utils/finance/rewind.ts` — modify: overload `findSnapshotAtOrBefore` to accept a direct `RewindSnapshot[]` array while preserving the existing store-based signature for backward compatibility.
- `frontend/src/lib/utils/finance/rewind.test.ts` — modify: add unit tests for `findSnapshotAtOrBefore` with direct snapshot array inputs and verify existing store-based tests continue to pass.
- `frontend/src/lib/api/userPreferencesService.ts` — modify: remove `rewind_snapshots` from `UserPreferences` interface and remove unused rewind type imports/re-exports.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: import `snapshotsService`, add `securitySnapshots` state and `loadSnapshots()` fetcher in the security effect, update `handleSaveSnapshot` to call `snapshotsService.createSnapshot`, and wire timeline scrub to `securitySnapshots`.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: mock `snapshotsService`, update existing snapshot save, dedupe, scrub, and restore tests to assert against `snapshotsService` rather than `userPreferencesService.patchPreferences({ rewind_snapshots })`.

**Steps:**
1. In `frontend/src/lib/utils/finance/rewind.ts`, overload `findSnapshotAtOrBefore` to support both `(snapshots: RewindSnapshot[] | null | undefined, time: Date)` and `(allSnapshots: Record<string, RewindSnapshot[]> | null | undefined, securityId: string, time: Date)`. Handle null/undefined/empty arrays gracefully by returning `null`.
2. In `frontend/src/lib/utils/finance/rewind.test.ts`, add test cases for direct snapshot array usage in `findSnapshotAtOrBefore` covering before-first, exact match, intermediate time, after-last, empty array, null/undefined, and invalid Date.
3. In `frontend/src/lib/api/userPreferencesService.ts`, remove `rewind_snapshots?: Record<string, RewindSnapshot[]> | null` from the `UserPreferences` interface, and remove unused `RewindDataWindow, RewindDrawings, RewindSnapshot` type imports and exports.
4. In `frontend/src/routes/security/[security_id]/+page.svelte`:
   a. Import `snapshotsService` from `$lib/api/snapshotsService`.
   b. Replace derived `securitySnapshots` with local state `let securitySnapshots = $state<RewindSnapshot[]>([]);`.
   c. Add `loadSnapshots()` function to fetch snapshots via `snapshotsService.getSnapshots(security.id)` and update `securitySnapshots`.
   d. Call `loadSnapshots()` alongside `loadAlerts()` and `loadHoldings()` in the `$effect` when `security` changes.
   e. Update `handleSaveSnapshot` to verify deduplication against the last snapshot in `securitySnapshots` via `areSnapshotsEqual`, persist via `snapshotsService.createSnapshot(security.id, { drawings, data_window: dataWindow, captured_at: snapshot.captured_at })`, append the returned snapshot to `securitySnapshots`, and trigger `showSaveFeedback()`. Remove `userPreferencesService.patchPreferences({ rewind_snapshots })`.
   f. Update `activeSnapshot` derived state to pass `securitySnapshots` directly to `findSnapshotAtOrBefore(securitySnapshots, timelinePosition)`.
5. In `frontend/src/routes/security/[security_id]/page.svelte.test.ts`:
   a. Add a mock for `$lib/api/snapshotsService` providing `snapshotsService` and `getSnapshotsService` with mock implementations of `getSnapshots`, `createSnapshot`, and `deleteSnapshot`.
   b. Update snapshot tests to verify `snapshotsService.getSnapshots` is called on load and snapshot points are rendered.
   c. Update Save snapshot button and Cmd/Ctrl+S tests to verify `snapshotsService.createSnapshot` is called with `{ drawings, data_window }` and that `userPreferencesService.patchPreferences` is NOT called with `rewind_snapshots`.
   d. Update dedupe tests to verify `snapshotsService.createSnapshot` is called only once on duplicate saves and not called when pre-seeded with identical drawings.
   e. Update Rewind Scrub and Restore tests to seed snapshots via `snapshotsService.getSnapshots` mock resolution and verify scrubbing restores historical drawings without calling `patchPreferences`.
6. Run frontend tests and verification checks to ensure zero regressions and zero type errors.

**Verification:**
- Load on navigation: Run `docker compose exec frontend npm run test:run -- src/routes/security` to verify navigating to security page calls `snapshotsService.getSnapshots('sec-1')` and renders timeline markers.
- Save snapshot & shortcuts: In test run, verify clicking "Save snapshot", pressing Cmd+S, and pressing Ctrl+S calls `snapshotsService.createSnapshot('sec-1', ...)` and appends to timeline immediately.
- Dedupe guard: In test run, verify second identical save or saving identical to pre-seeded snapshot does not call `snapshotsService.createSnapshot`.
- Scrub & restore: In test run, verify scrubbing timeline displays historical drawings loaded via `snapshotsService.getSnapshots` and scrubbing triggers zero `patchPreferences` calls.
- Preferences cleanup: Verify `UserPreferences` in `userPreferencesService.ts` contains no `rewind_snapshots` property via `docker compose exec frontend npm run check`.
- Quality gates:
  - `docker compose exec frontend npm run check` -> 0 type errors.
  - `docker compose exec frontend npm run test:run -- src/lib/utils/finance/rewind.test.ts` -> 100% pass rate.
  - `docker compose exec frontend npm run test:run -- src/routes/security` -> 100% pass rate.
  - `docker compose exec frontend npm run lint` -> 0 errors/warnings.

**Risks / watch-outs:**
- Snapshot ordering: `findSnapshotAtOrBefore` assumes ascending chronological order. Ensure direct-array overload sorts or preserves ascending sort by `captured_at` before scanning so out-of-order snapshots never cause lookup anomalies.
- Dedupe timing: `handleSaveSnapshot` should check equality against `securitySnapshots[securitySnapshots.length - 1]` before triggering the async `createSnapshot` network call to prevent duplicate in-flight requests.
