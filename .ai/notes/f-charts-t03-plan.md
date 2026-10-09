## Plan

**Approach:**
Wire double-click handling through `ChartMouseHandlers` into `ElliottWavesPrimitive` by subscribing to `_mouseHandlers.doubleClicked()` and exposing a `doubleClicked()` subscription, mirroring the pattern established by `FibonacciPrimitive`. Expand `WaveDegree` and its visual constants to include all 9 Elliott wave degrees (Grand Supercycle through Subminuette) with standard formatting, and create a reusable `WaveDegreeModal` component allowing degree selection. In `ChartDrawingsService` and `security-chart.svelte`, implement `updateWaveDegree` to mutate the wave's degree, immediately re-render the chart, and persist the updated wave collection to `userPreferencesService`.

**Files:**
- `frontend/src/lib/utils/finance/elliott-wave.ts` — modify: Expand `WaveDegree` union to include `'grand_supercycle' | 'supercycle' | 'cycle' | 'primary' | 'intermediate' | 'minor' | 'minute' | 'minuette' | 'subminuette'`. Export `WAVE_DEGREES` metadata list containing value and human-readable label for all 9 degrees.
- `frontend/src/lib/components/charts/plugins/elliott-wave/constants.ts` — modify: Add visual styling configs (`GRAND_SUPERCYCLE_STYLE`, `SUPERCYCLE_STYLE`, `MINOR_STYLE`, `MINUTE_STYLE`, `MINUETTE_STYLE`, `SUBMINUETTE_STYLE`) and register all 9 degrees in `DEGREE_STYLES`.
- `frontend/src/lib/components/charts/plugins/elliott-wave/state.ts` — modify: Implement `updateWaveDegree(waveId: string, newDegree: WaveDegree): boolean` to update the wave's degree, sync selection if applicable, and emit `wavePointsChanged`.
- `frontend/src/lib/components/charts/plugins/elliott-wave/elliott-wave.ts` — modify: Listen to `_mouseHandlers.doubleClicked()` and expose `doubleClicked(): ISubscription<PointTarget>`. Implement `updateWaveDegree(waveId: string, newDegree: WaveDegree): boolean` delegating to state and triggering `_requestUpdate`.
- `frontend/src/lib/components/charts/plugins/elliott-wave/index.ts` — modify: Export new degree styles if applicable.
- `frontend/src/lib/components/charts/wave-degree-modal.svelte` — create: Dialog modal allowing selection of wave degree across all 9 degrees with `data-testid="wave-degree-modal"`, `data-testid="wave-degree-select"`, `data-testid="cancel-btn"`, and `data-testid="save-btn"`.
- `frontend/src/lib/components/charts/wave-degree-modal.test.ts` — create: Unit tests for `WaveDegreeModal` verifying rendering, option population, initial selection, save event dispatch, and cancel dismissal.
- `frontend/src/lib/components/charts/security-chart.svelte` — modify: Subscribe to `elliottWavesPrimitive.doubleClicked()`, forward to `onWaveDoubleClick` callback prop, and export `updateWaveDegree` method.
- `frontend/src/lib/services/ChartDrawingsService.svelte.ts` — modify: Add `updateWaveDegree(waveId: string, newDegree: WaveDegree, chartRef?: ChartInstance | null): Promise<void>` to update the wave via chart ref or direct preference patch, and push undo/redo history. Add `updateWaveDegree` to `ChartInstance` interface.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: Bind `onWaveDoubleClick` from `SecurityChart` to open `WaveDegreeModal` with the selected wave's degree, and call `drawingsService.updateWaveDegree` on save.
- `frontend/src/lib/components/charts/plugins/elliott-wave/elliott-wave.test.ts` — modify: Add unit tests verifying `doubleClicked` fires on double-clicking a point or line, `updateWaveDegree` updates degree and requests render update, and verify styling configurations for all 9 degrees.
- `frontend/src/lib/components/charts/security-chart.test.ts` — modify: Add unit tests verifying `onWaveDoubleClick` prop invocation when `elliottWavesPrimitive.doubleClicked()` fires and `updateWaveDegree` method.
- `frontend/src/lib/services/ChartDrawingsService.test.ts` — modify: Add unit tests verifying `updateWaveDegree` updates wave degree in preferences and persists via `userPreferencesService`.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: Add integration test verifying double-clicking an Elliott wave opens `WaveDegreeModal` and saving persists degree change.

**Steps:**
1. Update `WaveDegree` types and constants in `frontend/src/lib/utils/finance/elliott-wave.ts`:
   - Expand `type WaveDegree` union to include `'grand_supercycle' | 'supercycle' | 'cycle' | 'primary' | 'intermediate' | 'minor' | 'minute' | 'minuette' | 'subminuette'`.
   - Export `WAVE_DEGREES` constant array mapping all 9 degrees to their standard labels (`Grand Supercycle`, `Supercycle`, `Cycle`, `Primary`, `Intermediate`, `Minor`, `Minute`, `Minuette`, `Subminuette`).
2. Add visual styling configs in `frontend/src/lib/components/charts/plugins/elliott-wave/constants.ts`:
   - Define `DegreeVisualConfig` for each new degree following Elliott Wave Theory notation conventions (e.g. Grand Supercycle with `[I]..[V]` and `[A]..[C]`, Supercycle with `(I)..(V)` and `(A)..(C)`, Minor with `1..5` and `A..C`, Minute with `(i)..(v)` and `(a)..(c)`, Minuette with `i..v` and `a..c`, Subminuette with `((1))..((5))` and `((a))..((c))`).
   - Populate `DEGREE_STYLES: Record<WaveDegree, DegreeVisualConfig>` with all 9 degree styles.
   - Export new styles in `frontend/src/lib/components/charts/plugins/elliott-wave/index.ts`.
3. Implement double-click and degree update in Elliott Wave plugin:
   - In `frontend/src/lib/components/charts/plugins/elliott-wave/state.ts`, add `updateWaveDegree(waveId: string, newDegree: WaveDegree): boolean`. Locate wave by `id`, update `wave.degree = newDegree`, update `_selectedDegree` if this wave was selected, fire `_wavePointsChanged.fire({ degree: newDegree, waveCount: wave })`, and return `true`.
   - In `frontend/src/lib/components/charts/plugins/elliott-wave/elliott-wave.ts`, subscribe to `_mouseHandlers.doubleClicked()` in `_setupSubscriptions()` and fire `_doubleClicked.fire(hit)`. Expose `public doubleClicked(): ISubscription<PointTarget>`. Expose `public updateWaveDegree(waveId: string, newDegree: WaveDegree): boolean` calling `_state.updateWaveDegree` and `_requestUpdate?.()`. Clean up delegate in `destroy()`.
4. Create `WaveDegreeModal` component and tests:
   - Create `frontend/src/lib/components/charts/wave-degree-modal.svelte`: Dialog containing a `<select>` (or select component) bound to selected degree with options for all 9 `WAVE_DEGREES`, Cancel button, and Save button. Test IDs: `data-testid="wave-degree-modal"`, `data-testid="wave-degree-modal-title"`, `data-testid="wave-degree-select"`, `data-testid="cancel-btn"`, `data-testid="save-btn"`.
   - Create `frontend/src/lib/components/charts/wave-degree-modal.test.ts`: Test modal visibility, options rendering for all 9 degrees, pre-selection of `currentDegree`, change selection and click Save triggers `onSave(newDegree, waveId)`, and click Cancel triggers `onClose`.
5. Connect double-click and degree update in `SecurityChart`:
   - In `frontend/src/lib/components/charts/security-chart.svelte`, subscribe to `elliottWavesPrimitive.doubleClicked()` and invoke optional prop `onWaveDoubleClick?: (target: PointTarget) => void`.
   - Export `updateWaveDegree(waveId: string, newDegree: WaveDegree): boolean` calling `elliottWavesPrimitive.updateWaveDegree(waveId, newDegree)`.
   - Update `ChartInstance` interface in `ChartDrawingsService.svelte.ts` to include optional `updateWaveDegree`.
6. Implement `updateWaveDegree` in `ChartDrawingsService`:
   - In `frontend/src/lib/services/ChartDrawingsService.svelte.ts`, implement `updateWaveDegree = async (waveId: string, newDegree: WaveDegree, chartRef?: ChartInstance | null) => void`.
   - If `chartRef?.updateWaveDegree` is available, delegate to `chartRef.updateWaveDegree(waveId, newDegree)`.
   - In addition (or when `chartRef` is null), locate the wave in `userPreferences.elliott_waves[securityId]`, update its degree, record state in `DrawingHistoryManager`, persist via `_userPreferencesService.patchPreferences`, and trigger `onWaveAlertsReconcile`.
7. Wire modal and double-click in `+page.svelte`:
   - In `frontend/src/routes/security/[security_id]/+page.svelte`, add reactive state `isWaveDegreeModalOpen`, `modalWaveId`, and `modalWaveDegree`.
   - Pass `onWaveDoubleClick={(target) => { modalWaveId = target.waveId ?? null; modalWaveDegree = target.degree; isWaveDegreeModalOpen = true; }}` to `<SecurityChart>`.
   - Render `<WaveDegreeModal bind:open={isWaveDegreeModalOpen} waveId={modalWaveId} currentDegree={modalWaveDegree} onSave={(newDegree) => { if (modalWaveId) void drawingsService.updateWaveDegree(modalWaveId, newDegree, chartRef); }} />`.
8. Implement unit and integration tests:
   - In `frontend/src/lib/components/charts/plugins/elliott-wave/elliott-wave.test.ts`, add test for double-clicking an anchor handle firing `doubleClicked`, double-clicking a wave line firing `doubleClicked`, and `updateWaveDegree` updating wave degree and re-rendering.
   - In `frontend/src/lib/components/charts/security-chart.test.ts`, test `onWaveDoubleClick` callback fires on double-click and `updateWaveDegree` method.
   - In `frontend/src/lib/services/ChartDrawingsService.test.ts`, test `updateWaveDegree` updates preferences and calls `patchPreferences`.
   - In `frontend/src/routes/security/[security_id]/page.svelte.test.ts`, add integration test simulating `onWaveDoubleClick` from chart, verifying modal renders, selecting degree, clicking Save, and asserting preference patch with updated degree.
9. Verification:
   - Run unit and integration tests via `./scripts/agent-test`.
   - Confirm all linting, type checks, and test suites pass.

**Verification:**
- Elliott wave plugin unit tests: `./scripts/agent-test frontend/src/lib/components/charts/plugins/elliott-wave/elliott-wave.test.ts` (double-click handling, degree update, styles verification).
- Wave degree modal tests: `./scripts/agent-test frontend/src/lib/components/charts/wave-degree-modal.test.ts` (all 9 degrees, selection, save, cancel).
- Security chart tests: `./scripts/agent-test frontend/src/lib/components/charts/security-chart.test.ts` (`onWaveDoubleClick` event forwarding, `updateWaveDegree`).
- Drawings service tests: `./scripts/agent-test frontend/src/lib/services/ChartDrawingsService.test.ts` (`updateWaveDegree` preference persistence).
- Security page integration tests: `./scripts/agent-test frontend/src/routes/security/*/page.svelte.test.ts` (modal opening on double-click and save persistence).
- Full frontend regression and type-check: `./scripts/agent-test frontend` (zero lint, type, or test errors).

**Risks / watch-outs:**
- Shell discipline during tests: Never pass dynamic-route paths containing `[` or `]` directly to test commands; use glob wildcards like `frontend/src/routes/security/*/page.svelte.test.ts`.
- Svelte 5 Rune reactivity: Access reactive fields on `drawingsService` via property access without destructuring.
- Historical snapshots / alert reconciliation: Changing a wave's degree alters alert targets; calling `options.onWaveAlertsReconcile?.()` ensures alert proximity lines remain aligned with the newly assigned degree.
