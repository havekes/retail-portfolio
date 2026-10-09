## Plan

**Approach:**
Extract drawing orchestration, active tool state, selection tracking, history/undo/redo, drag-end preference debouncing, snapshot management, and keyboard event dispatch from `+page.svelte` into a dedicated Layer 2 service class `ChartDrawingsService.svelte.ts` using Svelte 5 Runes. Instantiate `ChartDrawingsService` per page and expose it via Svelte context (`setChartDrawingsService`), binding it into `drawing-toolbar.svelte` and `+page.svelte` while maintaining backwards-compatible prop interfaces for existing tests and child components.

**Files:**
- `frontend/src/lib/services/ChartDrawingsService.svelte.ts` — create: Layer 2 ES6 service class using Svelte 5 Runes (`$state`, `$derived`) managing active tools, selection, undo/redo (`DrawingHistoryManager`), debounced preference patching, snapshot persistence (`snapshotsService`), and keyboard handling (Delete, Backspace, Escape, Undo, Redo, Save). Includes `setChartDrawingsService` / `getChartDrawingsService` context helpers.
- `frontend/src/lib/services/ChartDrawingsService.test.ts` — create: Unit test suite for `ChartDrawingsService` validating tool switching, selection, point deletion via Delete/Backspace, Escape cancellation, history undo/redo state restoration, drag persistence deferral, and snapshots.
- `frontend/src/lib/components/charts/drawing-toolbar.svelte` — modify: Streamline component to bind against optional `service` prop / context while retaining optional fallback props so existing `drawing-toolbar.test.ts` tests continue to pass untouched.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: Instantiate `ChartDrawingsService`, register in context via `setChartDrawingsService`, delegate all drawing state, handlers, keyboard dispatch, and snapshot operations to the service, and preserve `<ChartComponent>` prop bindings and `getEffectiveSecurityDrawings()` export for tests.

**Steps:**
1. Create `frontend/src/lib/services/ChartDrawingsService.svelte.ts`:
   - Implement `ChartDrawingsService` class with reactive `$state` fields for active tools (`activeWaveDegree`, `activeWaveType`, `isDrawingWave`, `activeFibTool`, `isDrawingFib`, `isDrawingMeasure`, `isDrawingHorizontalLine`, `isDrawingLine`), selections (`selectedWaveDegree`, `selectedFibTool`, `selectedMeasureId`, `selectedHorizontalLineId`, `selectedLineId`), history state (`canUndo`, `canRedo`, `isDraggingDrawing`), and rewind state (`snapshots`, `isTimelineVisible`, `timelinePosition`, `saveFeedback`).
   - Implement derived properties for effective drawings (`effectiveElliottWaves`, `effectiveFibonacciTools`, `effectiveSecurityDrawings`, `isRewound`).
   - Integrate `DrawingHistoryManager` for session-based undo/redo, supporting coalesced drag operations with drag start/end hooks (`handleDrawingDragStart`, `handleDrawingDragEnd`) and preference patch calls (`userPreferencesService.patchPreferences`).
   - Implement tool mutation and deletion methods: `handleWaveChange`, `handleClearWave`, `handleFibChange`, `handleClearFib`, `handleFibLevelsChange`, `handleFibWidthSave`, and generic `handleDrawingChange` / `handleRemoveDrawing` (with convenience wrappers `handleMeasureChange`, `handleRemoveMeasure`, `handleHorizontalLineChange`, `handleRemoveHorizontalLine`, `handleLineChange`, `handleRemoveLine`).
   - Implement snapshot operations (`handleSaveSnapshot`, `loadSnapshots`) calling `snapshotsService`.
   - Implement DOM-decoupled keyboard dispatcher `handleKeyDown(event: KeyboardEvent, chartRef?: ChartInstance | null)` handling Delete, Backspace, Escape, Undo/Redo (Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl/Cmd+Y), and Save snapshot (Ctrl/Cmd+S).
   - Export context helpers `setChartDrawingsService` and `getChartDrawingsService`.
2. Add unit tests in `frontend/src/lib/services/ChartDrawingsService.test.ts`:
   - Verify tool activation mutually excludes other drawing tools.
   - Verify point and drawing deletion on Delete and Backspace keys for each tool type.
   - Verify Escape cancels active drawing mode and clears current selection.
   - Verify Undo and Redo revert and re-apply drawing preferences.
   - Verify intermediate dragging changes do not trigger immediate preference PATCH calls until `handleDrawingDragEnd`.
   - Verify snapshot capture and creation delegating to `snapshotsService.createSnapshot`.
3. Streamline `frontend/src/lib/components/charts/drawing-toolbar.svelte`:
   - Accept optional `service?: ChartDrawingsService` prop.
   - Use `$derived` to resolve active tools, drawing modes, undo/redo states, and save feedback from `service` or fallback props.
   - Connect button callbacks (`onSelectWaveDegree`, `onToggleFib`, `onMeasureSelect`, `onHorizontalLineSelect`, `onLineSelect`, `onUndo`, `onRedo`, `onSave`, `onToggleTimeline`) to delegate to `service` methods when individual prop callbacks are not provided.
4. Refactor `frontend/src/routes/security/[security_id]/+page.svelte`:
   - Instantiate `ChartDrawingsService` using `setChartDrawingsService(new ChartDrawingsService({ ... }))`.
   - Wire `drawingsService.setSecurity(security?.id)` and `drawingsService.setPreferences(prefs)` on route and preference loading.
   - Remove all manual drawing handler sprawl (`handleMeasureChange`, `handleLineChange`, `handleHorizontalLineChange`, `handleRemoveMeasure`, `handleWaveChange`, `handleFibChange`, etc.), history state tracking, and drawing keydown routing from the script tag.
   - Pass `service={drawingsService}` to `<DrawingToolbar>` and forward `ChartComponent` drawing props/callbacks directly to `drawingsService`.
   - Keep `export function getEffectiveSecurityDrawings()` as a wrapper around `drawingsService.getEffectiveSecurityDrawings()`.
   - Verify `+page.svelte` line count is reduced to < 1,400 lines.
5. Verify test suite and code quality:
   - Run unit tests for `ChartDrawingsService.test.ts`.
   - Run `drawing-toolbar.test.ts`.
   - Run `page.svelte.test.ts` to confirm all existing integration tests pass without regressions.
   - Run full frontend check `./scripts/agent-test frontend`.

**Verification:**
- `ChartDrawingsService` unit tests: `./scripts/agent-test frontend/src/lib/services/ChartDrawingsService.test.ts` (all pass).
- Drawing toolbar tests: `./scripts/agent-test frontend/src/lib/components/charts/drawing-toolbar.test.ts` (all 27 pass).
- Security page tests: `./scripts/agent-test frontend/src/routes/security/*/page.svelte.test.ts` (all pass).
- Line count check: `wc -l frontend/src/routes/security/*/+page.svelte` confirms line count is < 1,400.
- Full suite & lint: `./scripts/agent-test frontend` passes with zero lint, type, or test errors.

**Risks / watch-outs:**
- Svelte 5 Rune reactivity: Never destructure reactive properties from the `drawingsService` instance in `.svelte` templates or components (Gotcha 1 in `frontend/AGENTS.md`); always access them via property access (e.g. `drawingsService.isDrawingMeasure`).
- Test mock compatibility: `page.svelte.test.ts` spies on `mockChartProps` from `security-chart.svelte`; `<ChartComponent>` must continue to receive and bind these props through `drawingsService` to keep integration assertions green.
