---
date: 2026-09-20
verdict: sound-with-concerns
---

# Architecture Review 2026-09-20: PR 423 Drawing Tools & Chart Performance

## Summary
Review of PR 423 frontend changes (specifically Measure, Horizontal Line, and Free-Form Line drawing tools alongside Fibonacci and Elliott Waves). The tools function correctly and comply with the directory isolation rules, but introduce severe runtime performance bottlenecks (unthrottled network writes, full-chart redraws on every cursor movement, JSON serialization during dragging) and significant architectural duplication that hinders scalability when adding future tools. The verdict is **sound-with-concerns**, requiring targeted performance and harmonization tickets before merging or expanding the chart tools suite.

## Findings

### 1. Unthrottled network `PATCH` requests during anchor drag [severity: risk]
**Observation:**
In [`+page.svelte`](file:///home/greg/projects/retail-portfolio/frontend/src/routes/security/[security_id]/+page.svelte#L649-L768), handlers `handleMeasureChange`, `handleHorizontalLineChange`, `handleLineChange`, `handleFibChange`, and `handleWaveChange` are bound directly to primitive change delegates (`drawingsChanged`, `wavePointsChanged`). During mouse dragging, [`ChartMouseHandlers`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/helpers/mouse/chart-mouse-handlers.ts#L364-L370) fires `pointDragged` on every `mousemove` event at 60–120Hz, which triggers `state.updatePoint()` and immediately fires `drawingsChanged`. The page handler calls `await userPreferencesService.patchPreferences(...)` on every mousemove, flooding the network and server with hundreds of concurrent HTTP PATCH requests per drag gesture.
**Impact:**
Massive frame drops and UI stutter during interactive dragging, out-of-order HTTP completions clobbering final states, and unnecessary server load.
**Recommendation:**
Defer `patchPreferences` until drag completion via `dragEnded` / `onDrawingDragEnd`, with a debounced fallback. Update local drawing state during the drag without network I/O. Ticketed as ARCH-T01 (#450) (subsumes item 2 of #424).

### 2. Full-chart redraw triggered on every cursor movement across all primitives [severity: risk]
**Observation:**
In [`DrawingPrimitiveBase.attached`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.ts#L121):
```typescript
this._subscribeToUpdate(this._mouseHandlers.mouseMoved());
```
Every primitive extending [`DrawingPrimitiveBase`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.ts) (Elliott Wave, Fibonacci, Measure, Horizontal Line, Free-Form Line) subscribes to `mouseMoved()` and unconditionally calls `this._requestUpdate?.()`.
However, primitives only inspect [`getLastMousePosition()`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/free-form-line/free-form-line-primitive.ts#L247) when `isDrawingMode()` is true (for drawing preview rubber-band lines). When browsing normally or when other tools are inactive, every mouse move across the chart triggers up to 5 concurrent redraw requests to Lightweight Charts.
**Impact:**
Continuous canvas redraws and CPU/GPU usage while merely moving the mouse across the chart, causing noticeable performance degradation on high-DPI displays.
**Recommendation:**
Only subscribe to `mouseMoved()` for chart updates when `this._state.isDrawingMode()` is true, or guard the subscription so only the active tool requesting rubber-band preview lines requests updates.

### 3. CPU and GC thrashing from synchronous JSON serialization in history manager [severity: concern]
**Observation:**
In [`+page.svelte`](file:///home/greg/projects/retail-portfolio/frontend/src/routes/security/[security_id]/+page.svelte#L287-L290), `recordDrawingStateChange()` is executed on every drag move. While [`drawingHistoryManager.startCoalescing()`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/utils/finance/drawing-history.ts#L103) is active, [`push()`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/utils/finance/drawing-history.ts#L117-L138) still runs `areDrawingStatesEqual()` (deep comparison across all tools), executes `JSON.parse(JSON.stringify(state))` on the entire drawings state tree, and invokes `_notify()` which triggers Svelte reactive state updates for `canUndo` and `canRedo` at 60–120Hz.
**Impact:**
Frequent garbage collection spikes and micro-stutters during drag interactions.
**Recommendation:**
Capture history entry at `onDrawingDragStart` and commit the final state at `onDrawingDragEnd`. Bypass intermediate per-frame history snapshots.

### 4. Redundant DOM event listeners and layout recalculations [severity: debt]
**Observation:**
Each of the 5 drawing primitives attaches its own set of 7 DOM listeners (`mousemove`, `mousedown`, `mouseup`, `click`, `dblclick`, `mouseleave`, `contextmenu`) to the chart container and 2 listeners (`mouseup`, `keydown`) to `window` in [`ChartMouseHandlers.attached`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/helpers/mouse/chart-mouse-handlers.ts#L91-L111).
On each `mousemove`, each instance calls [`_determineMousePosition`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/helpers/mouse/chart-mouse-handlers.ts#L290-L320), invoking `element.getBoundingClientRect()` 5 times, price/time coordinate conversions 5 times, and separate hit testing.
**Impact:**
Layout thrashing if DOM measurements interleave with styles, plus 5x redundant event dispatch and geometry math per mouse move.
**Recommendation:**
Consolidate mouse handling into a shared chart interaction coordinator that computes canvas-space and chart coordinates once per event and dispatches to the active/hovered primitive.

### 5. Repetitive handle and label rendering logic across plugins [severity: debt]
**Observation:**
Canvas handle drawing [`_drawHandle`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/free-form-line/pane-renderer.ts#L169-L206) and [`_drawAnchorHandle`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/measure/pane-renderer.ts#L261-L298) is duplicated line-for-line across `free-form-line`, `measure`, `horizontal-line`, and `fibonacci`.
Handle constants (`DEFAULT_DRAG_RING_COLOR`, `DEFAULT_HOVER_RING_COLOR`, `DEFAULT_HANDLE_COLOR`, `DEFAULT_HANDLE_BORDER_COLOR`, `HANDLE_RADIUS`) are redefined in 4 separate plugin `constants.ts` files, violating the rule in `frontend/AGENTS.md` requiring shared functionality in `plugins/helpers/`.
Similarly, label background, accent bar, and typography logic in `measure` and `horizontal-line` are duplicated.
**Impact:**
Inconsistent handle visuals if updated in one place, redundant code (~300 lines of canvas drawing boilerplate across renderers), and increased maintenance friction.
**Recommendation:**
Extract shared canvas helpers into `src/lib/components/charts/plugins/helpers/renderer/`:
- `drawAnchorHandle(ctx, point, scope, options)`
- `drawChartLabel(ctx, scope, config)`
Centralize handle styling constants in `plugins/helpers/dimensions/`. Ticketed as ARCH-T02 (#451).

### 6. Duplicated tool state and mouse adapter boilerplate [severity: debt]
**Observation:**
- [`MeasureToolState`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/measure/state.ts), [`FreeFormLineToolState`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/free-form-line/state.ts), and [`HorizontalLineToolState`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/horizontal-line/state.ts) share ~90% identical state structure: collection arrays, selection ID, hover/drag targets, delegate declarations, and getter/setter lifecycles.
- [`mouse.ts`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/plugins/free-form-line/mouse.ts) in `measure` and `free-form-line` duplicate the exact `pointToSegmentDistance` math and line-segment hit-testing loops.
- `pane-view.ts` across all three tools is an identical 26-line pass-through class.
**Impact:**
Adding new tools requires re-implementing identical state machines, hit-testing, and pane view wrappers.
**Recommendation:**
Extract reusable abstractions in `plugins/helpers/`:
- `BaseCollectionToolState<TDrawing, TTarget>`
- `pointToSegmentDistance` and segment hit-testing in `plugins/helpers/mouse/geometry.ts`
- Generic `DelegatingPaneView<TRendererData>`
Ticketed as ARCH-T03 (#452).

### 7. O(N) boilerplate explosion and missing Layer 2 Drawings Service [severity: debt]
**Observation:**
Adding any new drawing tool currently requires changes across 7 distinct files:
1. [`drawings.ts`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/utils/finance/drawings.ts): adding to `DrawingToolType`, `SecurityDrawings`, and branching `if/else` ladders in 5 functions.
2. [`security-chart.svelte`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/security-chart.svelte): adding 5 props, 4 `$effect`s, series attachment, subscriptions in `onMount`, cleanup in `onDestroy`, and 3 exported methods per tool.
3. [`+page.svelte`](file:///home/greg/projects/retail-portfolio/frontend/src/routes/security/[security_id]/+page.svelte): has ballooned to **1,889 lines** with repetitive handlers (`handleMeasureChange`, `handleLineChange`, `handleHorizontalLineChange`), keyboard deletion routing, and history bindings.
4. [`drawing-toolbar.svelte`](file:///home/greg/projects/retail-portfolio/frontend/src/lib/components/charts/drawing-toolbar.svelte): copy-pasting tooltip/button markup and adding 2–3 props per tool.
**Impact:**
Violates Open/Closed Principle and Layer 1 / Layer 2 architecture from `frontend/AGENTS.md`. Extensibility is severely hindered.
**Recommendation:**
Introduce a Layer 2 service `ChartDrawingsService.svelte.ts` to manage active tools, selection, undo/redo, and debounced persistence outside of `+page.svelte`.
Create a unified tool registry or drawing plugin adapter in `security-chart.svelte` so drawing tools can be plugged in declaratively. Ticketed as ARCH-T04 (#453).

## What went well
- Clean separation between domain data (`drawings.ts`, `drawing-time.ts`, `measure.ts`) and visualization plugins.
- Strict isolation preserved between plugins (no illegal cross-plugin imports).
- Robust colocation of test suites for every new tool with comprehensive test coverage (~4,000 lines of tests added).
- Timeframe-aware coordinate projection via `TimeProjector` and epoch-second normalization ensures drawings persist cleanly across timeframe switches.
- Indicator pane resizing math in `indicator-pane-layout.ts` is pure, robust, and correctly defers persistence until drag end (`onPaneHeightsChange`).

## Prior finding disposition
- No previous `.agent/reviews/` reports exist.
- Open issue [#424](https://github.com/havekes/retail-portfolio/issues/424) (FOLLOWUP-T01):
  - Item 2: Address debounced drawing-tool preference writes. (Carried over and expanded in Finding 1).
  - Item 5: Normalize legacy drawing anchor times once at the seam to eliminate write-backs on load. (Still open in #424).
