## Plan

**Approach:** Move bottom-pane oscillators (RSI, MACD, OBV) into the main `chartInstance` using custom `priceScaleId`s and dynamically calculated `scaleMargins`, eliminating `bottomChartInstance` entirely. This native approach automatically resolves the timeframe misalignment bug and stacks indicators properly. We will also clear all indicators from the chart during timeframe refreshes before conditionally re-adding enabled ones to fix the unselected indicator display bug, and introduce an educational modal toggled from the indicator sidebar.

**Files:**
- `frontend/src/lib/components/actions-sidebar/indicator/indicator-help-modal.svelte` — create: A new dialog component containing educational explanations for MACD, Bollinger Bands, RSI, and OBV.
- `frontend/src/lib/components/actions-sidebar/indicator/indicator-group.svelte` — modify: Add an `Info` icon button next to the settings button for the supported indicators, wiring it to toggle the new `IndicatorHelpModal`.
- `frontend/src/lib/components/charts/security-chart.svelte` — modify: Delete all `bottomChartInstance` setup, DOM elements, and crosshair sync logic. Change `addIndicator`/`removeIndicator` to place RSI, MACD, OBV onto the main `chartInstance` with unique `priceScaleId`s. Implement an `updatePanes()` helper that dynamically assigns `scaleMargins` to the main series and any active oscillator series to stack them without overlapping.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: Update `refreshActiveIndicators` to unconditionally call `chartRef.removeIndicator(id)` for every indicator before checking `config.enabled` to prevent zombie indicators.

**Steps:**
1. Create `indicator-help-modal.svelte` using Bits/shadcn `Dialog` to display a title and explanation text based on the active `indicatorId` (MACD, BB, RSI, OBV).
2. Modify `indicator-group.svelte` to import `Info` from `@lucide/svelte/icons/info` and `IndicatorHelpModal`. Render the info button next to the settings button for the relevant indicators and bind its state.
3. In `security-chart.svelte`, remove `bottomChartInstance`, `bottomContainerRef`, `padIndicatorData`, and all crosshair/timeScale sync subscriptions from `onMount`. Clean up the DOM to use only the main container.
4. In `security-chart.svelte`, create an `updatePanes()` function that counts active oscillator indicators (RSI, MACD, OBV), calculates percentage-based `scaleMargins` for each, applies them to `chartInstance.priceScale(id)`, and shrinks the main `seriesInstance` bottom margin accordingly.
5. In `security-chart.svelte`, update `addIndicator` and `removeIndicator` to attach RSI, MACD, OBV to `chartInstance` using `priceScaleId: indicator.type` and call `updatePanes()`. Remove custom padding since they now share the master time scale natively.
6. In `+page.svelte`, update the `refreshActiveIndicators` function to unconditionally call `chartRef.removeIndicator(id)` for all non-`avgPrice` indicators before evaluating if they should be re-added, ensuring disabled ones vanish on timeframe changes.

**Verification:**
- Run `docker compose exec frontend npm run check` and `docker compose exec frontend npm run test:run`.
- Open the UI and select RSI, MACD, and OBV. Ensure they stack in separate panes at the bottom of the main chart and do not overlap the candlesticks.
- Switch the timeframe from 1D to 1H. Verify the x-axis aligns perfectly between the candlesticks and the indicators.
- Deselect RSI, switch timeframe, and verify RSI does not reappear (fixing the zombie indicator bug).
- Click the new info button next to MACD in the sidebar and verify the educational modal opens.

**Risks / watch-outs:**
- The Lightweight Charts `priceScale` configurations must correctly handle multiple axes and their visibility so the right-side labels render properly without colliding.
- Ensure the `volume` scale margins are also accounted for or placed correctly alongside the oscillators in `updatePanes()`.
