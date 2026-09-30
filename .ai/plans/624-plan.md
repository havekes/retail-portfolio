## Plan

**Approach:** Centralize supported Elliott wave cycle definitions with notation metadata in `elliott-wave.ts` for consumption by both modal and toolbar, implement logarithmic-safe range calculation and auto-scale reset callbacks for mouse drag and wheel zoom on `SecurityChart`, and integrate inline overlay toggle checkboxes for Fair Value Range and Average Price in their respective sidebar groups with preference persistence.

*Alternative rejected:* Duplicating supported wave degree arrays inside individual components was rejected to maintain a single source of truth across the Elliott wave subsystem.

**Files:**
- `frontend/src/lib/utils/finance/elliott-wave.ts` — modify: Export `SUPPORTED_WAVE_DEGREES`, `SupportedWaveDegreeInfo`, `SUPPORTED_WAVE_DEGREE_CONFIGS`, and `SUPPORTED_WAVE_DEGREE_LIST` containing display names and impulse/corrective notation labels ('I'/'A', '①'/'Ⓐ', '1'/'(A)').
- `frontend/src/lib/utils/finance/elliott-wave.test.ts` — modify: Add unit tests validating exported supported wave degrees and notation metadata.
- `frontend/src/lib/components/charts/wave-degree-modal.svelte` — modify: Import `SUPPORTED_WAVE_DEGREES` from `$lib/utils/finance/elliott-wave` and restrict rendered degree options to only supported wave cycles.
- `frontend/src/lib/components/charts/wave-degree-modal.test.ts` — modify: Update unit tests to verify only supported wave cycles (`cycle`, `primary`, `intermediate`) are displayed and selectable.
- `frontend/src/lib/components/charts/drawing-toolbar.svelte` — modify: Import `SUPPORTED_WAVE_DEGREE_LIST` to generate impulse and corrective dropdown items dynamically from the central definition.
- `frontend/src/lib/components/charts/security-chart.svelte` — modify:
  - Add `onAutoScaleChange?: (autoScale: boolean) => void` prop.
  - Update `handleWheel`: In logarithmic mode (`logScale === true`), map the visible price range to log coordinates matching lightweight-charts logarithmic formula before calling `setVisibleRange`, and invoke `onAutoScaleChange?.(false)`.
  - Add mouse drag detection on the right price scale (`x >= containerRef.clientWidth - priceScaleWidth`) that detects vertical drags and invokes `onAutoScaleChange?.(false)`.
- `frontend/src/lib/components/charts/security-chart.test.ts` — modify: Add tests for `onAutoScaleChange(false)` on price scale wheel and drag interactions, and verify log scale visible range is preserved gradually without extreme jumps.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify:
  - Connect `onAutoScaleChange` callback on `<SecurityChart>` to update `userPreferences.chart_auto_scale` and persist `{ chart_auto_scale: false }` via `userPreferencesService.patchPreferences`.
  - Bind `showAveragePrice` on `<HoldingsGroup>` with `indicatorConfigs.avgPrice.enabled` and persist preference.
- `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.svelte` — modify: Move the valuation band overlay checkbox directly to the right of the Fair Value Range display inside the valuation card, default `showOverlay` to `true`, and persist `show_valuation_band`.
- `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.test.ts` — modify: Update tests for the relocated Fair Value Range overlay checkbox.
- `frontend/src/lib/components/actions-sidebar/holding-group/holding-group.svelte` — modify: Add `showAveragePrice` prop (default `true`) and an overlay toggle checkbox directly to the right of the Average Price display, toggling the chart line and persisting preference.
- `frontend/src/lib/components/actions-sidebar/holding-group/holding-group.test.ts` — modify: Add unit tests verifying the Average Price overlay checkbox renders (default checked) and toggling it persists user preferences.

**Steps:**
1. In `frontend/src/lib/utils/finance/elliott-wave.ts`, define and export `SUPPORTED_WAVE_DEGREES = ['cycle', 'primary', 'intermediate'] as const`, `type SupportedWaveDegree`, `SupportedWaveDegreeInfo` interface, `SUPPORTED_WAVE_DEGREE_CONFIGS`, and `SUPPORTED_WAVE_DEGREE_LIST` containing display names and notation labels. Add unit tests in `frontend/src/lib/utils/finance/elliott-wave.test.ts`.
2. In `frontend/src/lib/components/charts/wave-degree-modal.svelte`, import `SUPPORTED_WAVE_DEGREES` and restrict modal radio options to only `cycle`, `primary`, and `intermediate`. Update `wave-degree-modal.test.ts` to assert only supported cycles are present.
3. In `frontend/src/lib/components/charts/drawing-toolbar.svelte`, import `SUPPORTED_WAVE_DEGREE_LIST` and iterate over it to generate impulse and corrective dropdown items.
4. In `frontend/src/lib/components/charts/security-chart.svelte`, add `onAutoScaleChange?: (autoScale: boolean) => void`. Update `handleWheel` to compute logarithmic coordinates when `logScale === true` (`Math.log10(p + 0.0001) + 4`) so visible range transitions remain gradual without extreme jumps, and invoke `onAutoScaleChange?.(false)`.
5. In `frontend/src/lib/components/charts/security-chart.svelte`, add pointer/mouse drag tracking on the price scale bounding area (`x >= clientWidth - priceScaleWidth`), calling `onAutoScaleChange?.(false)` when dragged vertically. Add unit tests in `security-chart.test.ts`.
6. In `frontend/src/routes/security/[security_id]/+page.svelte`, wire `onAutoScaleChange` on `<SecurityChart>` to update `chart_auto_scale` reactive state and call `userPreferencesService.patchPreferences({ chart_auto_scale: false })`.
7. In `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.svelte`, relocate the valuation band toggle checkbox directly to the right of the Fair Value Range header inside the card, maintaining default checked state and `show_valuation_band` preference persistence. Update `fundamentals-group.test.ts`.
8. In `frontend/src/lib/components/actions-sidebar/holding-group/holding-group.svelte`, add `showAveragePrice` prop (default `true`), `onToggleAveragePrice` callback, and a toggle checkbox directly to the right of Average Price. Connect to `indicatorConfigs.avgPrice.enabled` in `frontend/src/routes/security/[security_id]/+page.svelte`. Add unit tests in `holding-group.test.ts`.
9. Execute `./scripts/agent-test` across all touched test suites and preflight checks to verify full regression and gate compliance.

**Verification:**
- `./scripts/agent-test frontend/src/lib/utils/finance/elliott-wave.test.ts`: Verify `SUPPORTED_WAVE_DEGREES` and notation metadata pass.
- `./scripts/agent-test frontend/src/lib/components/charts/wave-degree-modal.test.ts`: Verify modal only renders cycle, primary, and intermediate options.
- `./scripts/agent-test frontend/src/lib/components/charts/security-chart.test.ts`: Verify price scale wheel and drag invoke `onAutoScaleChange(false)` and logarithmic scaling behaves gradually.
- `./scripts/agent-test frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.test.ts`: Verify Fair Value Range inline toggle checkbox renders, toggles, and persists `show_valuation_band`.
- `./scripts/agent-test frontend/src/lib/components/actions-sidebar/holding-group/holding-group.test.ts`: Verify Average Price inline toggle checkbox renders, toggles, and persists average price preference.
- `./scripts/agent-test frontend/src/routes/security/*/page.svelte.test.ts`: Verify security page responds to autoScale deactivation and overlay toggles.
- `./scripts/agent-test --all`: Full pre-flight linting, type checks, and regression suite pass cleanly.

**Risks / watch-outs:**
- Lightweight-charts 5.2.1 expects logarithmic values in `setVisibleRange` when `PriceScaleMode.Logarithmic` is active; transforming price range with `toLog` (`Math.log10(price + 0.0001) + 4`) is required to prevent numeric overflow.
- In `holding-group.svelte`, the component must safely handle standalone usage and bound page usage so patching `avgPrice` does not inadvertently overwrite other active indicators.
