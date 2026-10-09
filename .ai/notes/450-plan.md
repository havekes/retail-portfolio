# Plan for ARCH-T01: Throttle drawing writes and cursor redraws (Issue #450)

## Plan

**Approach:**
Decouple continuous high-frequency chart mouse movement and anchor dragging from render requests and network I/O. Restrict `DrawingPrimitiveBase` redraw requests on `mouseMoved()` to active drawing creation mode while ignoring idle hover events, defer `userPreferencesService.patchPreferences` calls during dragging until `onDrawingDragEnd` while updating local UI state immediately, and optimize `DrawingHistoryManager` coalescing to bypass deep comparison and JSON serialization during drag moves until drag completion.

**Files:**
- `frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.ts` — modify: Guard `mouseMoved()` and `pointHovered()` subscriptions so chart redraw requests only fire when in drawing mode or when the hovered point target actually changes.
- `frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.test.ts` — modify: Add unit tests verifying `mouseMoved` triggers zero `_requestUpdate()` calls when not in drawing mode, and updates when in drawing mode.
- `frontend/src/lib/utils/finance/drawing-history.ts` — modify: Update `push()` during coalescing to store pending un-cloned state without executing `JSON.parse(JSON.stringify())` or notifying subscribers, and commit/clone upon `stopCoalescing()`, `undo()`, `redo()`, or non-coalesced pushes.
- `frontend/src/lib/utils/finance/drawing-history.test.ts` — modify: Add unit tests verifying zero `JSON.stringify` calls during intermediate coalescing moves, exactly one clone on `stopCoalescing()`, and accurate undo/redo state restoration.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: Track `isDraggingDrawing` and `pendingDrawingPreferences` in `onDrawingDragStart`/`onDrawingDragEnd`; update local state on intermediate moves in `handleWaveChange`, `handleFibChange`, `handleMeasureChange`, `handleHorizontalLineChange`, and `handleLineChange`, but bypass `patchPreferences` until `handleDrawingDragEnd`.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: Add integration tests verifying intermediate drag moves generate zero HTTP patch requests, drag end commits the final preference snapshot once, and undo/redo functions cleanly after dragging.

**Steps:**
1. In `DrawingPrimitiveBase` (`frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.ts`), update `attached()`:
   - Change `this._subscribeToUpdate(this._mouseHandlers.mouseMoved());` to subscribe with a check: `if (this._state.isDrawingMode()) this._requestUpdate?.();`.
   - Update `pointHovered()` handler so `this._requestUpdate?.()` is only called if `this._state.getHoveredPoint() !== null || target !== null` (avoiding redraws when moving across empty canvas where hovered target remains `null`).
2. In `DrawingPrimitiveBase` tests (`frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.test.ts`), update existing mouse movement test and add cases confirming moving the cursor across the chart when `isDrawingMode()` is `false` triggers 0 `_requestUpdate()` calls, while doing so when `isDrawingMode()` is `true` triggers `_requestUpdate()`.
3. In `DrawingHistoryManager` (`frontend/src/lib/utils/finance/drawing-history.ts`):
   - Add private property `_pendingCoalescedState: SecurityDrawingState | null = null`.
   - In `push(state, options)`: if `options?.coalesce` or `this._isCoalescing` is true, assign `this._pendingCoalescedState = state;` and return early without executing `areDrawingStatesEqual`, `cloneDrawingState`, or `_notify`.
   - Add private method `_flushCoalesced()`: if `this._pendingCoalescedState` is non-null, compare against top of `_undoStack` with `areDrawingStatesEqual`; if changed, push `cloneDrawingState(this._pendingCoalescedState)` to `_undoStack` (pruning to `_maxHistory`), clear `_redoStack`, and call `_notify()`. Reset `this._pendingCoalescedState = null`.
   - Call `_flushCoalesced()` in `stopCoalescing()`, `undo()`, `redo()`, non-coalesced `push()`, and `getCurrentState()`.
   - Update `canUndo()` to return `this._undoStack.length > 1 || (this._pendingCoalescedState !== null && this._undoStack.length >= 1)`.
   - In `clear()` and `init()`, reset `this._pendingCoalescedState = null`.
4. In `DrawingHistoryManager` tests (`frontend/src/lib/utils/finance/drawing-history.test.ts`):
   - Add test using `vi.spyOn(JSON, 'stringify')` ensuring 0 serialization calls occur across multiple `push()` calls during active coalescing, and exactly 1 call occurs when `stopCoalescing()` or `undo()` flushes the state.
   - Assert `undo()` restores pre-drag state and `redo()` restores final dragged state accurately.
5. In `frontend/src/routes/security/[security_id]/+page.svelte`:
   - Declare `let isDraggingDrawing = $state(false);` and `let pendingDrawingPreferences: Partial<UserPreferences> | null = null;`.
   - Define `handleDrawingDragStart()`: set `isDraggingDrawing = true`, `pendingDrawingPreferences = null`, call `drawingHistoryManager.startCoalescing()`.
   - Define `handleDrawingDragEnd()`: set `isDraggingDrawing = false`, call `drawingHistoryManager.stopCoalescing()`, and if `pendingDrawingPreferences` is non-null, store a copy, clear `pendingDrawingPreferences = null`, await `userPreferencesService.patchPreferences(copy)`, and call `scheduleWaveAlertsReconcile()` if `elliott_waves` was part of the payload.
   - In `handleMeasureChange`, `handleHorizontalLineChange`, `handleLineChange`, `handleFibChange`, and `handleWaveChange`:
     - Keep immediate local state updates (`userPreferences = ...`) and `recordDrawingStateChange({ coalesce: true })`.
     - Guard network write: if `isDraggingDrawing` is true, accumulate updated key into `pendingDrawingPreferences` (`drawings`, `fibonacci_tools`, or `elliott_waves`) and return early.
     - If `isDraggingDrawing` is false, proceed with `await userPreferencesService.patchPreferences(...)`.
   - Update `SecurityChart` props to bind `onDrawingDragStart={handleDrawingDragStart}` and `onDrawingDragEnd={handleDrawingDragEnd}`.
6. In `page.svelte.test.ts` (`frontend/src/routes/security/[security_id]/page.svelte.test.ts`):
   - Add integration tests for all 5 drawing tool types (measure, horizontal line, free-form line, fibonacci, elliott wave) verifying:
     - Firing `onDrawingDragStart()` followed by multiple change events emits 0 `patchPreferences` network calls during intermediate moves.
     - Firing `onDrawingDragEnd()` triggers exactly one `patchPreferences` call containing the final state.
     - Triggering undo/redo keyboard shortcuts or toolbar buttons after a drag restores pre-drag and post-drag states accurately.
7. Run verification suite (`./scripts/agent-test frontend`) and ensure all quality gates, linting, type checks, and tests pass.

**Verification:**
- AC 1 (Redraw throttling): `npx vitest run frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.test.ts` — verify that moving cursor when `isDrawingMode()` is false calls `_requestUpdate()` zero times, while moving cursor when `isDrawingMode()` is true requests updates.
- AC 2 & 3 (Preference write deferral & 0 intermediate network requests): `npx vitest run frontend/src/routes/security/ -t "drag"` — verify that dragging anchors of measure, horizontal line, free-form line, fibonacci, and elliott wave triggers 0 `patchPreferences` calls during drag moves and exactly 1 call on drag release.
- AC 4 (History serialization bypass): `npx vitest run frontend/src/lib/utils/finance/drawing-history.test.ts` — verify `JSON.stringify` spy confirms 0 invocations during intermediate moves while coalescing is active.
- AC 5 (Undo / Redo fidelity): `npx vitest run frontend/src/lib/utils/finance/drawing-history.test.ts` and `page.svelte.test.ts` undo/redo suites pass and confirm accurate pre-drag and post-drag state restoration.
- AC 6 (Full frontend check): `./scripts/agent-test frontend` passes Gate 0 (svelte-check, eslint, prettier) and Gate 1 tests cleanly.

**Risks / watch-outs:**
- Svelte reactivity timing: `isDraggingDrawing` must be synchronous so intermediate change events synchronously observe `isDraggingDrawing === true` before any async microtask runs.
- Empty drag gestures: If a user clicks an anchor (firing dragStart) and releases without moving (firing dragEnd), `pendingDrawingPreferences` remains `null`, avoiding spurious network writes or duplicate history frames.
- Reconciling Elliott wave alerts: Alert reconciliation (`scheduleWaveAlertsReconcile`) must be deferred to drag completion alongside the preference write to prevent debounce spam.
