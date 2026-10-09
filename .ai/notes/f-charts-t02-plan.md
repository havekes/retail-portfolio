## Plan

**Approach:**
Extend `UserPreferences` with `chart_auto_scale` and `chart_log_scale`, expose "Auto vertical scaling" and "Logarithmic price scale" toggle controls in `ChartSettingsModal`'s General tab alongside the existing hide-labels toggle, wire the toggles through the security page container to `SecurityChart` props (`autoScale` and `logScale`), and reactively apply `autoScale` and `PriceScaleMode.Logarithmic` vs `PriceScaleMode.Normal` to the chart's right price scale (`chartInstance.priceScale('right').applyOptions(...)`). Rejected alternative: replacing individual callback props with a single merged general settings object callback was rejected to preserve backward compatibility with existing tests and call sites.

**Files:**
- `frontend/src/lib/api/userPreferencesService.ts` — modify: add `chart_auto_scale?: boolean | null` and `chart_log_scale?: boolean | null` to `UserPreferences` interface.
- `src/account/api_types.py` — modify: add `chart_auto_scale: bool | None = None` and `chart_log_scale: bool | None = None` to `UserPreferences` model for server schema completeness.
- `frontend/src/lib/components/charts/chart-settings-modal.svelte` — modify: accept `chartAutoScale` and `chartLogScale` props with defaults (`true` and `false`), provide change callbacks `onSaveChartAutoScale` and `onSaveChartLogScale`, track draft states, and render two toggle checkboxes with labels "Auto vertical scaling" and "Logarithmic price scale" in the General panel.
- `frontend/src/lib/components/charts/security-chart.svelte` — modify: import `PriceScaleMode` from `lightweight-charts`, add `autoScale` and `logScale` props, initialize `rightPriceScale` with `autoScale` and `mode`, and add a reactive `$effect` calling `chartInstance.priceScale('right').applyOptions({ autoScale, mode })`.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: pass `autoScale` and `logScale` to `<ChartComponent>`, bind `chartAutoScale`, `chartLogScale`, and save handlers (`handleChartAutoScaleChange`, `handleChartLogScaleChange`) to `<ChartSettingsModal>`, saving updates via `userPreferencesService.patchPreferences`.
- `frontend/src/lib/components/charts/chart-settings-modal.test.ts` — modify: add unit tests verifying initial toggle rendering, toggling and saving `chartAutoScale` and `chartLogScale`, and discarding unsaved changes on cancel.
- `frontend/src/lib/components/charts/security-chart.test.ts` — modify: add `PriceScaleMode` to `vi.mock('lightweight-charts')`, and add unit tests verifying `autoScale` and `mode` (Logarithmic vs Normal) options are applied to `priceScale('right')`.
- `frontend/src/lib/api/userPreferencesService.test.ts` — modify: add unit test verifying `chart_auto_scale` and `chart_log_scale` persistence in `patchPreferences`.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: add tests verifying that loaded preferences populate chart `autoScale` and `logScale`, and saving modal toggles triggers `patchPreferences`.

**Steps:**
1. Update `frontend/src/lib/api/userPreferencesService.ts` and `src/account/api_types.py`:
   - In `frontend/src/lib/api/userPreferencesService.ts`: add `chart_auto_scale?: boolean | null` and `chart_log_scale?: boolean | null` to the `UserPreferences` interface.
   - In `src/account/api_types.py`: add `chart_auto_scale: bool | None = None` and `chart_log_scale: bool | None = None` to the `UserPreferences` model.
2. Update `frontend/src/lib/components/charts/chart-settings-modal.svelte`:
   - Extend `$props` with:
     - `chartAutoScale?: boolean;` (default `true`)
     - `chartLogScale?: boolean;` (default `false`)
     - `onSaveChartAutoScale?: (autoScale: boolean) => void | Promise<void>;`
     - `onSaveChartLogScale?: (logScale: boolean) => void | Promise<void>;`
   - Add draft state:
     - `let draftChartAutoScale = $state<boolean>(untrack(() => chartAutoScale ?? true));`
     - `let draftChartLogScale = $state<boolean>(untrack(() => Boolean(chartLogScale)));`
   - In `syncGeneralFromProps()`, reset `draftChartAutoScale = chartAutoScale ?? true` and `draftChartLogScale = Boolean(chartLogScale)`.
   - Update the `$effect` tracking prop changes to resync when `chartAutoScale` or `chartLogScale` changes.
   - In `handleSaveGeneral()`, invoke `onSaveChartAutoScale?.(draftChartAutoScale)` and `onSaveChartLogScale?.(draftChartLogScale)` alongside `onSaveChartHideLabels`.
   - In the General panel template (`#if activeSection === 'general'`), add two toggle rows matching the "Hide indicator labels" layout:
     - Checkbox with `id="chart-auto-scale"`, `checked={draftChartAutoScale}`, `onCheckedChange={(checked) => (draftChartAutoScale = checked === true)}`, `data-testid="auto-scale-checkbox"`, and `<label for="chart-auto-scale">Auto vertical scaling</label>`.
     - Checkbox with `id="chart-log-scale"`, `checked={draftChartLogScale}`, `onCheckedChange={(checked) => (draftChartLogScale = checked === true)}`, `data-testid="log-scale-checkbox"`, and `<label for="chart-log-scale">Logarithmic price scale</label>`.
3. Update `frontend/src/lib/components/charts/security-chart.svelte`:
   - Import `PriceScaleMode` from `'lightweight-charts'`.
   - In props declaration and types, add `autoScale = true` and `logScale = false` (types: `autoScale?: boolean; logScale?: boolean;`).
   - In `onMount`, update `createChart` options to configure `rightPriceScale`:
     ```ts
     rightPriceScale: {
         visible: true,
         minimumWidth: DEFAULT_PRICE_SCALE_MIN_WIDTH,
         autoScale,
         mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal
     }
     ```
   - Add a reactive `$effect`:
     ```ts
     $effect(() => {
         if (!chartInstance) return;
         chartInstance.priceScale('right').applyOptions({
             autoScale,
             mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal
         });
     });
     ```
4. Update `frontend/src/routes/security/[security_id]/+page.svelte`:
   - Implement handlers:
     - `handleChartAutoScaleChange(autoScale: boolean)`: updates `userPreferences.chart_auto_scale` and calls `userPreferencesService.patchPreferences({ chart_auto_scale: autoScale })`.
     - `handleChartLogScaleChange(logScale: boolean)`: updates `userPreferences.chart_log_scale` and calls `userPreferencesService.patchPreferences({ chart_log_scale: logScale })`.
   - Pass `autoScale={userPreferences?.chart_auto_scale ?? true}` and `logScale={Boolean(userPreferences?.chart_log_scale)}` to `<ChartComponent>`.
   - Pass `chartAutoScale={userPreferences?.chart_auto_scale ?? true}`, `onSaveChartAutoScale={handleChartAutoScaleChange}`, `chartLogScale={Boolean(userPreferences?.chart_log_scale)}`, and `onSaveChartLogScale={handleChartLogScaleChange}` to `<ChartSettingsModal>`.
5. Add unit tests in `frontend/src/lib/components/charts/chart-settings-modal.test.ts`:
   - Test default states: "Auto vertical scaling" checked by default; "Logarithmic price scale" unchecked by default.
   - Test initializing with custom props (`chartAutoScale: false`, `chartLogScale: true`).
   - Test checking/unchecking toggles and clicking Save calls `onSaveChartAutoScale` and `onSaveChartLogScale` with updated boolean values.
   - Test clicking Cancel reverts draft state and does not call save callbacks.
6. Add unit tests in `frontend/src/lib/components/charts/security-chart.test.ts`:
   - Update `vi.mock('lightweight-charts')` to include `PriceScaleMode = { Normal: 0, Logarithmic: 1, Percentage: 2, IndexedTo100: 3 }`.
   - Test that `createChart` is called with initial `autoScale` and `mode`.
   - Test that changing `autoScale` prop applies `{ autoScale: false, mode: PriceScaleMode.Normal }` to `mainChart.priceScale('right')`.
   - Test that changing `logScale` prop applies `{ autoScale: true, mode: PriceScaleMode.Logarithmic }` to `mainChart.priceScale('right')`.
7. Add tests in `frontend/src/lib/api/userPreferencesService.test.ts`:
   - Test `patchPreferences` sending `{ chart_auto_scale: false, chart_log_scale: true }` and returning the updated preference blob.
8. Add integration tests in `frontend/src/routes/security/[security_id]/page.svelte.test.ts`:
   - Test that initial `userPreferences` with `chart_auto_scale: false` and `chart_log_scale: true` sets `autoScale={false}` and `logScale={true}` on `mockChartProps`.
   - Test that saving updated values from `ChartSettingsModal` triggers `patchPreferences({ chart_auto_scale: ... })` and `patchPreferences({ chart_log_scale: ... })`.
9. Run verification commands:
   - Run vitest on modified test suites.
   - Run type checking and linting to ensure zero regressions.

**Verification:**
- AC1: `npm --prefix frontend run test -- chart-settings-modal.test.ts` — verify "Auto vertical scaling" and "Logarithmic price scale" checkboxes render in General section, toggle, and respond to Save/Cancel.
- AC2: `npm --prefix frontend run test -- security-chart.test.ts` — verify `priceScale('right').applyOptions` receives `{ autoScale, mode }` when toggles change.
- AC3: `npm --prefix frontend run test -- userPreferencesService.test.ts` and `npm --prefix frontend run test -- page.svelte.test.ts` — verify preferences are saved to `/accounts/me/preferences` via `patchPreferences` and restored on mount.
- AC4: `npm --prefix frontend run test -- chart-settings-modal.test.ts security-chart.test.ts userPreferencesService.test.ts` — all toggle interaction and persistence tests pass.
- AC5: `npm --prefix frontend run check && pytest tests/routers/test_accounts.py` — frontend type check passes and backend account preference routes pass.

**Risks / watch-outs:**
- `PriceScaleMode` must be exported from the lightweight-charts mock in `security-chart.test.ts`, otherwise importing it in `security-chart.svelte` causes `undefined` reference errors in tests.
- Maintain default `autoScale = true` so existing charts without saved preferences continue to auto-scale vertically by default as before.
