---
type: architecture
title: "Charting: Chart Surface, Panes & Indicators"
description: "The chart rendering surface of the security route: security-chart.svelte's mount/series/primitive lifecycle, candle updates, pagination and future whitespace, the scaleMargins price-scale pane model with custom pane heights, price-scale zoom/auto-scale interaction, timeframe and chart-style preferences, the indicator pipeline through the Go sidecar with its Redis result cache and out-of-order guard, chart settings, the price-alert primitive and the rewind-aware valuation band."
tags: [charting, lightweight-charts, indicators, panes, price-alerts, valuation-band, chart-preferences, svelte]
sources:
  - id: openwiki-source-e483fd3285d99d05c7b265cf
    resource: repo://frontend/AGENTS.md
  - id: openwiki-source-31c465e6b7d0d36afe3ffe00
    resource: repo://frontend/src/lib/api/indicatorsService.ts
  - id: openwiki-source-95a24be7f44e810285a4bb5e
    resource: repo://frontend/src/lib/api/userPreferencesService.test.ts
  - id: openwiki-source-8a88da80cc6ed6d98b2035f2
    resource: repo://frontend/src/lib/api/userPreferencesService.ts
  - id: openwiki-source-fd6bc3ef355365f09e91de6e
    resource: repo://frontend/src/lib/chart-preferences.ts
  - id: openwiki-source-f873b1d824c5e165822317be
    resource: repo://frontend/src/lib/chart/indicator-defaults.test.ts
  - id: openwiki-source-31c8f2b5a9dd5358a3f2d5e4
    resource: repo://frontend/src/lib/chart/indicator-defaults.ts
  - id: openwiki-source-2e0c8f4697dcadec3fddbbfe
    resource: repo://frontend/src/lib/chart/indicator-pane-layout.test.ts
  - id: openwiki-source-8487e2b0202a176a8fe27c5e
    resource: repo://frontend/src/lib/chart/indicator-pane-layout.ts
  - id: openwiki-source-e1cb95ad60e9e5df185fb3aa
    resource: repo://frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.svelte
  - id: openwiki-source-6fefb7b02941c114f4550918
    resource: repo://frontend/src/lib/components/charts/chart-settings-modal.svelte
  - id: openwiki-source-e03b7d6203bf399f13c8a612
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/fibonacci.test.ts
  - id: openwiki-source-c19a08eca0dccf2c925cc86a
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/time/time.ts
  - id: openwiki-source-7d36a2f693a30c914e86e954
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/mouse.ts
  - id: openwiki-source-af5ee747460de5273d8c5d4a
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/state.ts
  - id: openwiki-source-d4f0cd24cd75b5cc0da82f96
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/user-price-alerts.ts
  - id: openwiki-source-9a33f2cd63de94dd97ff39f7
    resource: repo://frontend/src/lib/components/charts/plugins/valuation-band/valuation-band.test.ts
  - id: openwiki-source-0a9a504227d25141ac6e3e3a
    resource: repo://frontend/src/lib/components/charts/plugins/valuation-band/valuation-band.ts
  - id: openwiki-source-277415f21fdc20b26619d18d
    resource: repo://frontend/src/lib/components/charts/security-chart.svelte
  - id: openwiki-source-c3b7cc10403cbc15934d0991
    resource: repo://frontend/src/lib/components/charts/security-chart.test.ts
  - id: openwiki-source-d24fa40d87efc1e2c3422ea9
    resource: repo://frontend/src/lib/components/charts/sparkline.svelte
  - id: openwiki-source-ecd4b1167badc1f9ac4ea606
    resource: repo://frontend/src/lib/services/ChartDrawingsService.svelte.ts
  - id: openwiki-source-f97400306b886f7bcb3e07b4
    resource: repo://frontend/src/lib/utils/date.ts
  - id: openwiki-source-6eb7daa700f1b21e5dc1b9aa
    resource: repo://frontend/src/lib/utils/finance/wave-alerts.ts
  - id: openwiki-source-33c886f28072e35f81eadfae
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/%2Bpage.server.ts
  - id: openwiki-source-67b769eb99d4518b98fe1ca7
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/%2Bpage.svelte
  - id: openwiki-source-51676b3163748937a7f6b22d
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/page-data.svelte.ts
  - id: openwiki-source-0f254d3861bd88b12afd24c2
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/page.server.test.ts
  - id: openwiki-source-ddd6d556671e35d3baea7163
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/page.svelte.test.ts
  - id: openwiki-source-95aa045141f9e53c82a0bc2b
    resource: repo://services/indicator-service/handlers.go
  - id: openwiki-source-692344b8dd5d47fcc6f9bfe0
    resource: repo://services/indicator-service/README.md
  - id: openwiki-source-112661f7a5dd097320a9b5a8
    resource: repo://services/indicator-service/timeframe.go
  - id: openwiki-source-8a10008d9bf8365255edbb33
    resource: repo://src/market/cache.py
  - id: openwiki-source-d8383d22d61483b00080a280
    resource: repo://src/market/router.py
  - id: openwiki-source-9fc85bceeb3edfbe3ab56a7c
    resource: repo://src/market/service.py
  - id: openwiki-source-4a4ca3cbe0b274d6c82e4e15
    resource: repo://tests/market/test_indicator_client.py
  - id: openwiki-source-d5f24b3551e2c9a796e0c850
    resource: repo://tests/market/test_indicator_compute_api.py
generated: { by: "openwiki/0.7.0", at: "2026-10-06T14:42:34.222Z" }
verified:
  - by: openwiki/0.7.0
    at: 2026-10-06T14:42:34.222Z
---

This page covers the chart *surface*: the `lightweight-charts` wrapper, its data and pane lifecycle, chart preferences, the indicator pipeline, the price-alert primitive and the valuation band. Drawing tools, their series-primitive plugins, drawing persistence and the snapshot/rewind pipeline are documented on [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md) — this page only points at them. The fair-value range concept itself (model, routes, client, sidebar modal) lives on [Security Valuations](../concepts/security-valuation.md), the price/candle side of the indicator pipeline on [Market Data & Indicators](../workflows/market-data-and-indicators.md), and the sidecar as an outbound dependency on [External Services & Adapters](../integrations/external-services.md).

| Layer | Location | Owns |
|---|---|---|
| Chart surface | `frontend/src/lib/components/charts/security-chart.svelte` | chart instance, candlestick series, price-scale panes, primitives, indicator series, whitespace, price-scale zoom/auto-scale |
| Route orchestration | `frontend/src/routes/security/[security_id]/+page.svelte` + `page-data.svelte.ts` | data loading, timeframe/style preferences, indicator requests, pane-height and valuation-overlay persistence |
| Pane math | `frontend/src/lib/chart/indicator-pane-layout.ts` | pure pane-height distribution and `scaleMargins` computation |
| Indicator defaults | `frontend/src/lib/chart/indicator-defaults.ts` | the frozen default table and per-page copies |
| Indicator API | `frontend/src/lib/api/indicatorsService.ts` → `src/market/router.py` → indicator sidecar | compute request/response contract, backend cache |
| Chart settings | `frontend/src/lib/components/charts/chart-settings-modal.svelte` | hide-labels / auto-scale / log-scale, wave settings, fib level/width editing |
| Price alerts | `frontend/src/lib/components/charts/plugins/user-price-alerts/` | alert lines, add/remove buttons, price-axis labels |
| Valuation band | `frontend/src/lib/components/charts/plugins/valuation-band/valuation-band.ts` | shaded lower/upper fair-value band on the main price scale |
| Drawings & rewind | `frontend/src/lib/components/charts/plugins/*`, `$lib/utils/finance/*`, `$lib/services/ChartDrawingsService.svelte.ts` | see [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md) |

## Ground rules

- **Commands run inside Docker.** Frontend work is executed in the `frontend` service (`docker compose exec frontend ...`); the agent harness wraps that (`./scripts/agent-test frontend/src/...`).
- **Frontend tests must mock every API client and `lightweight-charts`.** CI has no backend and no real canvas, so an unmocked client or a real chart import is a broken test by definition (see `frontend/AGENTS.md`).
- **A new indicator type belongs in the Go sidecar, not in Python.** The chart's compute route forwards specs to `services/indicator-service`; adding a type means a new case in its `ComputeIndicator` switch plus README documentation, not new Python math.
- **Nothing in a test dials a real dependency.** Frontend tests mock every API client and `lightweight-charts`; backend indicator tests use `httpx.MockTransport` for the sidecar and patch the cache, so no test reaches the sidecar, Redis or EODHD for real.

## Entry points

| Concern | Location |
|---|---|
| Chart component | `frontend/src/lib/components/charts/security-chart.svelte` |
| Security page | `frontend/src/routes/security/[security_id]/+page.svelte` |
| Route load (identity only) | `frontend/src/routes/security/[security_id]/+page.server.ts` |
| Post-navigation data wave | `frontend/src/routes/security/[security_id]/page-data.svelte.ts` |
| Pane layout math | `frontend/src/lib/chart/indicator-pane-layout.ts` |
| Indicator defaults | `frontend/src/lib/chart/indicator-defaults.ts` |
| Chart preference helpers | `frontend/src/lib/chart-preferences.ts` |
| Time helpers | `frontend/src/lib/utils/date.ts`, `frontend/src/lib/utils/finance/candle.ts` |
| Indicator API client | `frontend/src/lib/api/indicatorsService.ts` |
| Chart settings modal | `frontend/src/lib/components/charts/chart-settings-modal.svelte` |
| Price-alert primitive | `frontend/src/lib/components/charts/plugins/user-price-alerts/` |
| Valuation band primitive | `frontend/src/lib/components/charts/plugins/valuation-band/valuation-band.ts` |
| Bands overlay primitive | `frontend/src/lib/components/charts/plugins/bands-indicator.ts` |
| SVG sparkline (no chart library) | `frontend/src/lib/components/charts/sparkline.svelte` |

The chart bundle is loaded lazily: the page `await import('$lib/components/charts/security-chart.svelte')`s only after the security and its `1d` series resolve, so chart code never runs during SSR.

## Route data: identity first, series after navigation

`+page.server.ts` deliberately does almost nothing — it validates the `security_id` param (400 `Security ID is required` when absent) and returns `{ security_id }`. It never fetches the security or its prices.

`SecurityPageDataService` (`page-data.svelte.ts`) owns the post-navigation data wave. `load(securityId)`:

- increments a private `loadSeq` and discards its own result when a newer soft navigation has superseded it (the `finally` only clears `isLoading` for the newest sequence);
- fetches `getSecurity(securityId)` and `getPrices(securityId, from, to, '1d')` in parallel, using `getChartDateWindow(new SvelteDate(), '1d')`;
- treats a missing or empty `items` array as a *successful* load whose message lands in `error` (`No price data available for this security`);
- never throws — it returns the caught error so the page can route a 401 through `redirectOn401`.

Because identity and prices resolve after navigation, the page can render its shell immediately: `instantSecurity` is looked up in the already-loaded default watchlist so the titlebar shows the symbol before the fetch lands, and the chart region shows `Loading chart data...` until the dynamic import resolves. A per-security `$effect` resets tool state, `timeframeError`, `hasMoreData`, `isLoadingMore` and `securityChart` on every route transition, then runs the async init chain (preferences → candle mapping → alerts/holdings/valuation/snapshots → chart import). The async load always fetches the `1d` series, so on soft navigation the page force-refetches the active timeframe (`changeTimeframe(selectedInterval, { persist: false, force: true })`) unless a timeframe change is already in flight.

## The chart surface (`security-chart.svelte`)

### Props and ownership

The component receives data and drawing-model state as props and reports intent back through callbacks; it persists nothing itself:

- Core: `candles`, `containerId`, `hasMoreData`, `isLoadingMore` (bindable), `onLoadMoreData`, `hideLabels`, `averagePrice`/`showAveragePrice`, `futureBars` (default `DEFAULT_FUTURE_BARS` = 100), `onPaneHeightsChange`.
- Price scale: `autoScale` (default true), `logScale` (default false) and `onAutoScaleChange(autoScale)`, which the page persists as `chart_auto_scale`.
- Valuation: `valuation` (`{ lower_bound, upper_bound } | null`), `showValuation` and `showValuationBand`.
- Alerts: `alerts`, `onAddAlert(price, condition)`, `onRemoveAlert(id)`.
- Drawings: the Elliott-wave and Fibonacci prop/callback pairs, `securityDrawings` plus the measure / horizontal-line / free-form-line drawing flags, selections and change callbacks, and `onDrawingDragStart` / `onDrawingDragEnd`.

Prop→primitive syncing happens in guarded `$effect`s that compare the primitive's current value against the incoming prop (using the finance-layer equality helpers) before calling a setter, so no update loop forms between prop and primitive.

### Mount, series and primitive wiring

`onMount` creates the chart with `CrosshairMode.Normal`, a transparent background, `formatLocalTime` as the time formatter, `formatLocalTickMark` as the tick-mark formatter, `ignoreWhitespaceIndices: false`, a hidden left price scale and a right price scale with `minimumWidth` 75 (`DEFAULT_PRICE_SCALE_MIN_WIDTH`), `autoScale` and `mode` taken from the `autoScale`/`logScale` props. It then:

1. Subscribes `timeScale().subscribeVisibleLogicalRangeChange` for two duties: pagination and future-whitespace expansion.
2. Adds the main `CandlestickSeries` (`#26a69a` up / `#ef5350` down, borders and border colors set, wicks colored).
3. Creates the `ValuationBandPrimitive` from the `valuation`/`showValuationBand` props and attaches it to that series, then calls `updatePanes()`.
4. Attaches six more primitives to the same series: `UserPriceAlerts` (with `setSymbolName('Price')`), `ElliottWavesPrimitive`, `FibonacciPrimitive`, `MeasurePrimitive`, `HorizontalLinePrimitive`, `FreeFormLinePrimitive`.
5. Subscribes each primitive's delegates and re-emits them as page callbacks — `alertAdded`/`alertRemoved`, `wavePointsChanged`, `drawingModeChanged`, `degreeChanged`, `waveTypeChanged`, `selectionChanged`, `doubleClicked`, `toolChanged`, `drawingsChanged`, `dragStarted`/`dragEnded`.
6. Installs a capture-phase, non-passive `wheel` listener that zooms the **price scale** (not the time scale) over the price-scale strip, plus mouse/pointer down-move-up listeners that detect a vertical price-scale drag and report `onAutoScaleChange(false)`, and a `ResizeObserver` that resizes the chart to the container and re-runs `checkAndExpandWhitespace`.
7. Returns a teardown that removes the wheel, mouse and pointer listeners, disconnects the observer, destroys the six alert/drawing primitives and only then calls `chartInstance.remove()`.

```mermaid
flowchart TD
    MOUNT["onMount with a container ref"] --> CREATE["createChart with crosshair, layout, time formatters, axes and price scale options"]
    CREATE --> RANGE["subscribeVisibleLogicalRangeChange for pagination and whitespace"]
    RANGE --> SERIES["addSeries CandlestickSeries"]
    SERIES --> BAND["create and attach ValuationBandPrimitive then updatePanes"]
    BAND --> ALERTS["attach UserPriceAlerts and subscribe its delegates"]
    ALERTS --> DRAWINGS["attach the five drawing primitives and subscribe their delegates"]
    DRAWINGS --> INPUT["wheel, mouse and pointer listeners plus ResizeObserver"]
    INPUT --> LIVE["live chart: prop effects write into the series and primitives"]
    LIVE --> TEARDOWN["teardown removes every listener and disconnects the observer"]
    TEARDOWN --> DESTROY["destroy the six alert and drawing primitives"]
    DESTROY --> REMOVE["chartInstance.remove"]
```

Mount order and teardown order for the chart instance. The valuation band is attached before the other primitives but is not in the destroy list.

Separate `$effect`s keep the chart in sync with props: container size, the average-price dashed `IPriceLine`, the right price scale's `autoScale`/`mode`, `hideLabels` (which drives `lastValueVisible` / `priceLineVisible` / `title` across every indicator series group, including the three MACD series and the three BB series), and the valuation band's range.

### Drawing mode locks panning

One `$effect` ORs all five drawing flags and applies `handleScroll: { pressedMouseMove: !isDrawing }`. Each primitive's `drawingModeChanged` subscription restores `pressedMouseMove: true` only once *every* other drawing flag is off, so finishing one tool does not unlock panning while another is still active.

### Candle updates, pagination and future whitespace

The `candles` `$effect` is the single writer of series data:

- Same array reference as `lastCandlesRef` → no-op (the page replaces the array when data changes, which is the change signal).
- Empty array → clear series data and every drawing primitive's candle set, reset `currentWhitespaceCount` to `futureBars`, clear `previousFirstCandleTime` and `isLoadingMore`.
- **Prepending** (the first candle is older than the previously-seen first candle) → locate the previously-first candle's index, write data, then shift the visible logical range by that index so the viewport does not jump.
- **First load** (`previousFirstCandleTime === null`) → size `currentWhitespaceCount` from `futureBars` and the container width, then show the last 250 bars.
- Every non-empty update writes `seriesInstance.setData([...candles, ...generateFutureWhitespace(candles, currentWhitespaceCount)])`, pushes the raw candles into all five drawing primitives and clears `isLoadingMore`.

```mermaid
flowchart TD
    CHANGE["candles prop changes"] --> EMPTY{"array is empty"}
    EMPTY -- "yes" --> CLEAR["clear series data, every drawing primitive candle set and the whitespace count"]
    EMPTY -- "no" --> SAME{"same array reference as lastCandlesRef"}
    SAME -- "yes" --> NOOP["no-op"]
    SAME -- "no" --> PREPEND{"first candle older than the previously seen first candle"}
    PREPEND -- "yes" --> SHIFT["write data and whitespace then shift the visible logical range by the prepended count"]
    PREPEND -- "no" --> FIRST{"previousFirstCandleTime is null"}
    FIRST -- "yes" --> WINDOW["size the whitespace from futureBars and the container width then show the last 250 bars"]
    FIRST -- "no" --> WRITE["write data and whitespace"]
    SHIFT --> PUSH["push the raw candles into all five drawing primitives"]
    WINDOW --> PUSH
    WRITE --> PUSH
    RANGE["visible logical range change"] --> PAGINATION{"range.from is at or before bar 10 and more history exists"}
    PAGINATION -- "yes" --> LOADMORE["set isLoadingMore and call onLoadMoreData"]
    PAGINATION -- "no" --> EXPAND["checkAndExpandWhitespace grows the count as the viewport nears the right edge"]
    EXPAND --> SAVED["write the larger whitespace tail and re-apply the saved logical range"]
```

Candle-update branches and the two duties of the visible-logical-range subscription.

Pagination lives on the same subscription: when `range.from <= 10 && !isLoadingMore && hasMoreData`, the component sets `isLoadingMore = true` and calls `onLoadMoreData()`. The page's `handleLoadMoreData` returns immediately while rewound, guards with `shouldFetchMoreData(isLoadingMore, hasMoreData, securityId, rawCandles.length)`, fetches the older window computed from the oldest candle for the active interval, maps and sorts candles, merges with `mergeCandles` (dedupe by `String(time)`, prepend), recomputes Heikin-Ashi candles and refreshes indicators — setting `hasMoreData = false` when the fetch is empty or adds nothing. An `$effect` also forces `isLoadingMore = false` whenever `hasMoreData` goes false.

Future whitespace is what makes drawing *ahead* of the last candle possible. `generateFutureWhitespace(candles, count)` returns `[]` for fewer than two candles, a non-positive count or a non-positive derived interval, derives the bar interval from the median spacing of the most recent candles (`computeIntervalSeconds`, last 8 spacings) and appends `count` whitespace points one interval apart via `addIntervalToTime`, preserving the reference candle's `Time` shape (epoch seconds vs. `YYYY-MM-DD` vs. `BusinessDay`). `checkAndExpandWhitespace(range)` re-enters only when it is not already updating, grows the count when the visible range approaches the right edge (threshold `max(lastCandleIndex + 1, currentEndIndex - 30)`, target `ceil(range.to - lastCandleIndex) + 100`) or when the container is wide enough to need more bars (`ceil(clientWidth / 4) + 100`), and re-applies the previously saved visible logical range so the expansion is invisible to the user.

### Price-scale zoom and auto-scale

The right price scale is the user's to manipulate, and every manipulation flips the chart out of auto-scale:

- **Wheel zoom.** A capture-phase, non-passive `wheel` listener on the container checks whether `event.clientX` falls inside the strip `containerWidth - priceScale.width() || 75`; if so it calls `preventDefault()`/`stopPropagation()` and rescales the price scale's visible range span by `1.025` (scroll down) or `0.975` (scroll up) around the range mid-point, then reports `onAutoScaleChange(false)`. In log-scale mode the span is computed in log coordinates (`toLogCoord(price) = sign(price) * (log10(|price| + 0.0001) + 4)`) so zooming stays visually even. Wheel events over the chart canvas are left to `lightweight-charts`.
- **Price-scale drag.** Mouse *and* pointer `down`/`move`/`up` listeners on the container and the window note the initial `clientY` when the press lands in the price-scale strip and fire `onAutoScaleChange(false)` once the pointer has moved more than 2 px vertically; a press over the canvas never triggers it.

The page reacts by persisting `chart_auto_scale: false` (`handleAutoScaleChange`), which disables the chart's own auto-scaling, and the `autoScale`/`logScale` props feed one `$effect` that applies `priceScale('right').applyOptions({ autoScale, mode })`.

### Imperative surface

Exports consumed through `bind:this` from the page (plus a few that exist for the drawings service and tests):

| Export | Purpose |
|---|---|
| `updateData(candles)` | Replace series data (plus whitespace) and show the last 250 bars; sets `lastCandlesRef` so the candle effect does not re-apply, and does **not** push candles into the drawing primitives |
| `addIndicator` / `updateIndicatorData` / `removeIndicator` | Add, refresh or drop an indicator series group |
| `getPaneHeights` / `setPaneHeights` / `resetPaneHeights` | Read, restore (no change callback) or clear the custom pane layout |
| `clearWave`, `getAllWaves`, `getSelectedWaveDegree` / `setSelectedWaveDegree`, `getSelectedWaveId` / `setSelectedWaveId`, `updateWaveDegree`, `getElliottWavesPrimitive` | Elliott-wave proxy API |
| `clearFibonacci`, `getSelectedFibTool` / `setSelectedFibTool`, `getFibonacciPrimitive` | Fibonacci proxy API |
| `getMeasurePrimitive`, `getSelectedMeasureId` / `setSelectedMeasureId`, `getHorizontalLinePrimitive`, `getSelectedHorizontalLineId` / `setSelectedHorizontalLineId`, `getLinePrimitive`, `getSelectedLineId` / `setSelectedLineId` | New-tool proxy API |
| `getValuationBandPrimitive` | Access to the valuation band primitive (tests) |

## Panes: price scales carved out with `scaleMargins`

`lightweight-charts` has no native panes here. Every "pane" is a **price-scale id** whose visible band is expressed with `scaleMargins` (`top`/`bottom` fractions of the chart height):

- `MAIN_PANE_ID` = `'main'` is the candlestick series' own scale (the right price scale); `VOLUME_PANE_ID` = `'volume'`; `OSCILLATOR_PANE_IDS` = `['rsi', 'macd', 'obv']` fixes the stacking order.
- The component keeps `orderedPaneIds` in explicit state (not derived from `indicatorSeries`) so it updates reliably when indicators are added or removed imperatively. `getOrderedPaneIds()` builds `main`, then `volume` when present, then the oscillators in order, and `refreshOrderedPaneIds()` only replaces the array when it actually changed.
- `applyPaneMargins()` refreshes the ids, calls `computePaneScaleMargins(paneIds, customPaneHeights)` and applies the result — `seriesInstance.priceScale().applyOptions({ scaleMargins })` for `main`, `chartInstance.priceScale(id).applyOptions({ scaleMargins })` for the others. `updatePanes()` is that same call, invoked after every add/remove, on restore and on every pane-drag move.
- `paneBoundaries` derives one boundary per *adjacent* pane pair from those same margins and drives the resize handles.

`bb` (Bollinger Bands) is an *overlay*, not an oscillator: it is drawn on the main price scale and never triggers a pane re-layout.

### Default layout math (`indicator-pane-layout.ts`)

The pure module is the single owner of the arithmetic; the chart only applies the result. With no applicable custom height it returns the exact margins the chart used before resizing existed (`computeDefaultPaneScaleMargins`):

- No oscillators, no volume → `main { top: 0.1, bottom: 0.1 }`.
- Volume only → `volume { top: 0.7, bottom: 0 }`, `main { top: 0.1, bottom: 0.35 }`.
- Oscillators present → per-oscillator height `0.25` (one), `0.18` (two), `0.14` (three), a `0.02` gap between panes, `mainAreaHeight = max(0.3, 1 - count * (paneHeight + gap))`; volume (when enabled) takes the bottom 25% of the main area and the candlestick scale is squeezed accordingly; oscillators are stacked below the main area in `OSCILLATOR_PANE_IDS` order.

With custom heights, `computePaneScaleMargins` switches to the custom path: `distributePaneHeights` allocates `1 - TOP_MARGIN (0.05) - BOTTOM_MARGIN (0) - (n - 1) * PANE_GAP (0.02)` across the ordered panes proportionally to their weights — the custom height when valid, otherwise the derived default band height, otherwise the `DEFAULT_PANE_HEIGHTS` fallback (`main 0.5`, `volume 0.15`, `rsi 0.25`, `macd 0.18`, `obv 0.14`) — clamped to `[MIN_PANE_FRACTION (0.08), MAX_PANE_FRACTION (0.8)]`. `allocatePaneHeights` is a water-filling allocator: panes whose proportional share falls outside the bounds are pinned to the bound and the remainder is redistributed among the rest, so the result is always non-overlapping and inside `[0, 1]`. `computePaneBandHeights` converts the resulting margins back into visible band heights for the drag logic. If the custom map exists but matches no present pane, the defaults are returned unchanged.

### Custom pane heights

The component renders one absolutely-positioned resize handle per *adjacent* pane pair (`data-testid="pane-resize-handle-<upper>-<lower>"`, positioned at the mid-point between the upper pane's bottom edge and the lower pane's top edge):

- `pointerdown` captures the pointer (best-effort, jsdom-safe) and records `startY` plus `computePaneBandHeights(getOrderedPaneIds(), customPaneHeights)`.
- `pointermove` converts `(clientY - startY) / containerHeight` into a fraction delta, moves it between the two panes while preserving their sum and clamping both to `[MIN_PANE_FRACTION, MAX_PANE_FRACTION]`, updates `customPaneHeights` and re-applies the margins immediately — the chart re-renders on every move, not only on release.
- `pointerup` / `pointercancel` (window-level) end the drag and fire `onPaneHeightsChange({ ...customPaneHeights })` exactly once.
- A `Reset pane sizes` button (`data-testid="reset-pane-heights"`) is rendered only while a custom height applies to a present pane; it clears the custom layout, re-applies the defaults and reports `onPaneHeightsChange(null)`.
- `removeIndicator(type)` also deletes that indicator's entry from `customPaneHeights` (collapsing to `null` when it becomes empty), so re-adding an oscillator starts from the default height rather than a stale fraction.

### Persistence: the `indicator_pane_heights` preference

The page owns persistence:

- `handlePaneHeightsChange(heights)` updates local `userPreferences` and PATCHes `{ indicator_pane_heights: heights }` — the whole key every time, because PATCH replaces it; a reset sends `null`.
- `applySavedPaneHeights(prefs)` calls `chartRef?.setPaneHeights?.(heights)` behind a `setTimeout(..., 100)` so the chart ref is bound first, and does nothing when the stored map is absent or empty. It runs from `onPreferencesLoaded` and from the init chain.
- `ChartInstance` (the interface `ChartDrawingsService` and the page use) exposes `setPaneHeights` as optional, which is why the call is guarded.

## Timeframe and chart-style preferences

The toolbar offers five intervals — `1h`, `4h`, `1d`, `1w`, `1m` — and two chart styles, `candlestick` and `heikin_ashi`.

`changeTimeframe(interval, { persist, force })` bails out without a security id, while `isChangingTimeframe`, or when `shouldForceRefetch(selectedInterval, interval, force)` is false (it is true when `force` is set or the interval differs). It then resets pagination state, computes the window with `getChartDateWindow(new Date(), interval)` (a 30-day window for intraday intervals, a 2-year window otherwise), fetches through `MarketService.getPrices`, maps rows with `mapPriceToCandle(p, isIntraday)` (intraday rows become `UTCTimestamp` epoch seconds through their `timestamp`, daily-and-coarser rows keep their date string), sorts oldest→newest, sets `rawCandles`, recomputes `haCandles = convertToHeikinAshi(rawCandles)` and calls `refreshActiveIndicators()`. An empty response sets `timeframeError` (`No price data available for this timeframe`) and returns. The preference patch is issued **after** the fetch `try/catch` and only when `persist && fetchOk`, so a failed preference write can neither mask a fetch error nor hold `isChangingTimeframe` open.

`allDisplayCandles = displayCandlesFor(chartStyle, rawCandles, haCandles)` is the styled series, and `displayCandles` — what the chart, the locally-rendered volume histogram and the indicator payloads actually read — is `allDisplayCandles` unless the user is rewound, in which case it is the candles sliced at the playhead (the slice itself belongs to [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md)). The two style buttons set `chartStyle`, call `refreshActiveIndicators()` and PATCH `chart_style`; a `loading-indicators-spinner` sits beside the timeframe buttons while `isLoadingIndicators` is set. `chart-preferences.ts` holds the pure helpers: `mergeChartPreferences` (read-merge-write that keeps the `indicators` key), `displayCandlesFor`, `shouldForceRefetch`, `parseCandleTime` (number / `YYYY-MM-DD` / ISO string / `BusinessDay` → `Date`), `mergeCandles` and `shouldFetchMoreData`. The page imports and uses five of them; `mergeChartPreferences` is exported and unit-tested but is *not* on the live write path, because the page persists single-key patches through `patchPreferences` and lets the backend merge.

`onPreferencesLoaded(prefs)` applies the persisted state in order: `show_valuation_band` into `showValuationOverlay`, the saved pane heights, the preferences object into `ChartDrawingsService`, the chart style (falling back to `heikin_ashi`), the saved timeframe via `changeTimeframe(prefs.timeframe, { persist: false })`, and finally the saved indicator toggles — each `onIndicatorToggle(id, true)` deferred through `setTimeout(..., 100)` so the chart ref is bound.

## Indicators

### Defaults

`INDICATOR_DEFAULTS` is the single source of truth: ids `volume`, `avgPrice`, `ma50`, `ma200`, `ma50w`, `ma200w`, `bb`, `macd`, `rsi`, `obv`, in sidebar render order (do not reorder), deep-frozen so accidental mutation throws. Only `avgPrice` is enabled by default. `createIndicatorConfigs()` returns a fully independent copy (including nested `settings`) for the page to mutate; the page keeps it in `indicatorConfigs` state.

### Series composition

`addIndicator(indicator)` switches on `indicator.type`:

| Type | Series composition | Price scale |
|---|---|---|
| `volume` | one `HistogramSeries`, `priceFormat: { type: 'volume' }` | `volume` |
| `rsi` | one `LineSeries` | `rsi` |
| `macd` | `HistogramSeries` + MACD `LineSeries` + signal `LineSeries`, histogram colored per sign (`#26a69a80` / `#ef535080`) | `macd` |
| `obv` | one `LineSeries` with a custom `M/1M` price formatter | `obv` |
| `bb` | three `LineSeries` (upper/middle/lower, `hexToRgba` alpha 0.5/1/0.5) + a `BandsIndicator` primitive attached to `middle` | main |
| everything else (`ma50`, `ma200`, …) | one `LineSeries` overlay | main |

Overlay series (the `bb` trio and the generic branch) set `autoscaleInfoProvider: () => null`, so the main price scale keeps scaling to candles only. Each branch records the group in `indicatorSeries` and appends to `activeIndicators`, then calls `updatePanes()` (except `bb`, which is an overlay). `removeIndicator(type)` detaches the bands primitive before removing the three BB series, removes all three MACD series, or removes the single series, then drops the group and any stale custom pane height and re-applies the margins. `updateIndicatorData(indicator)` refreshes `setData` per series shape and falls back to `addIndicator` when the group does not exist yet.

### The compute request/response contract

`IndicatorsService.computeIndicators(securityId, request)` POSTs to `/api/v1/market/securities/{security_id}/indicators/compute`:

```ts
interface IndicatorComputeRequest {
    interval: string;
    chart_style?: 'candlestick' | 'heikin_ashi';
    indicators: IndicatorSpec[];   // { id?, type, period?, fast?, slow?, signal?, stdDev?, settings? }
    candles?: IndicatorCandle[];   // caller-supplied series
    from_date?: string;
    to_date?: string;
}
interface IndicatorComputeResponse {
    indicators: Record<string, unknown[]>;
}
```

The backend `IndicatorComputeRequest` defaults `interval` to `1d` and `chart_style` to `candlestick`, and `IndicatorSpecSchema` mirrors the spec (`stdDev` is aliased to `std_dev`). The response map is keyed by spec id/type — the page reads `res.indicators[id] ?? res.indicators[spec.type] ?? []`. `buildIndicatorSpec` copies only the positive numeric fields (`period`, `fast`, `slow`, `signal`, `stdDev`) plus `settings` from the indicator config.

The route validates the window (`from_date > to_date` → 422, after normalizing date/datetime unions to plain dates), then:

- builds candles from the daily price repository (aggregating to weekly or monthly when asked, applying the same split-ratio adjustment the price endpoints use) or from the intraday repository (aggregating to 4h), or uses `request.candles` verbatim;
- converts to Heikin-Ashi server-side when `chart_style === 'heikin_ashi'`;
- calls the external indicator service through `IndicatorServiceClient.compute`, which POSTs `{ interval, candles, indicators }` to `<indicator_service_url>/compute` (timeouts become 504 `Indicator service timed out`, connection errors and 5xx become 503 `Indicator service unavailable`, a sidecar 400 is surfaced as 400 with the sidecar's `error` text);
- **consults and populates `IndicatorCache` only when `request.candles` is absent**. That is the point of the caller-supplied path: the rewind payload (`getRewoundCandlesPayload()`, which slices `rawCandles` at the timeline position) must never be served from, or written to, the cache, because the cache key is `indicators:<security>:<interval>:<chart_style>:<sha256 digest>` — the digest covering the canonicalized specs plus the normalized date window — and cannot describe the caller's candle set. Entries are written with `setex` and the cache's default TTL (3600 s / 1 hour).

The chart's own defaults to `ma*` indicators are period-scaled in the sidecar: `ma50`/`ma200` (day unit) multiply by `7` on `1h`, `2` on `4h`, stay put on `1d` and divide by 5 / 21 on `1w` / `1m`; the `ma*w` variants use `35`, `10`, `5`, `1` and `round(period * 12 / 52)`. The page's `IndicatorsService` still exposes the older `getIndicatorData` / `getAllIndicatorData` GET methods backed by the in-Python `GET /securities/{security_id}/indicators` route, but the security route computes through `computeIndicators` only.

### The sidecar contract (`services/indicator-service`)

The Go sidecar is a stateless calculator: `POST /compute` takes `{ interval, candles, indicators }`, where `interval` **defaults to `"1d"`** when omitted or empty (the backend always sends the resolved enum), and answers `{ "indicators": { ... } }` with one series per spec keyed by `ResultKey()` — the spec `id` when set, otherwise `type`. `type` is matched case-insensitively after trimming, the `ma*` aliases are accepted (`ma_50`, `ma_50_day`, `50ma`, …), parameter resolution is top-level field (`> 0`) → `settings` map entry → built-in default, and output points drop `NaN`/`Inf`. When there are too few candles to compute an indicator (or the period scales to `0`), that spec's series is an **empty array, not an error** — the circuit returns 200, which is why a newly enabled indicator can legitimately render nothing. Errors are limited to 400 (`invalid json body: ...` or `unsupported indicator type: <type>`), a 405 for any method other than POST, and the 10 MB body cap (`http.MaxBytesReader`).

### Round trip and the out-of-order guard

```mermaid
sequenceDiagram
    participant Page as Security page
    participant Api as IndicatorsService
    participant Router as Market router
    participant Cache as IndicatorCache
    participant Engine as Indicator sidecar

    Page->>Page: refreshActiveIndicators bumps sequenceCounter and stamps indicatorSeq
    Page->>Api: computeIndicators with interval, chart style and specs
    alt rewound
        Page->>Page: getRewoundCandlesPayload slices the candles at the playhead
        Page->>Api: the request carries the caller-supplied candles
    end
    Api->>Router: POST to the security indicators compute route
    alt no caller candles
        Router->>Cache: look up security, interval, chart style and spec digest
        Cache-->>Router: cached indicators or a miss
    end
    Router->>Engine: POST interval, candles and specs to /compute
    Engine-->>Router: series keyed by spec id or type
    Router->>Cache: store the result only when no caller candles were sent
    Router-->>Api: indicators map
    Api-->>Page: indicators map
    Page->>Page: discard the response when indicatorSeq no longer matches
    Page->>Api: removeIndicator then addIndicator per accepted spec
```

Indicator compute round trip: the page stamps a monotonic sequence per request, the backend caches only cache-eligible requests, and a response whose sequence is stale is discarded.

Two request paths share one guard:

- `refreshActiveIndicators()` (bulk: timeframe change, chart-style change, rewind scrub, load-more) increments `sequenceCounter`, records it in `activeRefreshSeq`, and writes that sequence into `indicatorSeq[id]` for **every enabled indicator**. It re-renders `volume` locally, then sends one spec per enabled indicator except `volume` and `avgPrice`. When the response lands it is accepted per indicator only if `indicatorConfigs[id]?.enabled && indicatorSeq[id] === seq`, and `isLoadingIndicators` is only cleared by the newest request.
- `onIndicatorToggle(id, enabled)` (single) bumps `sequenceCounter` into `indicatorSeq[id]`, sends one spec, and accepts the response only if the stored sequence still matches, the indicator is still enabled and the chart ref exists. Disabling removes the series immediately and bumps `indicatorSeq[id]` so an in-flight response cannot resurrect a disabled indicator.

This is the standard defence against out-of-order responses when the user toggles indicators quickly or changes timeframe mid-flight; the page suite covers exactly that race (a newer timeframe request resolving before an older toggle request).

Two "indicators" never reach the backend:

- `volume` is rendered locally from `displayCandles` (`removeIndicator('volume')` then `addIndicator` with `close >= open ? '#26a69a80' : '#ef535080'`).
- `avgPrice` is not a series at all: it is a dashed `IPriceLine` created/removed by an `$effect` from `averagePrice` + `showAveragePrice`, fed by `blendedAverageCost(holdings)`, and it is skipped when building specs.

## Chart settings

`chart-settings-modal.svelte` renders three tab sections (`general`, `waves`, `fibonacci`, switchable with `Cmd/Ctrl+1/2/3`), each with local draft state that is re-synced from props (via serialized `JSON.stringify` keys or previous-value comparisons, to avoid spurious resyncs from `$state` proxies) and a save/cancel pair:

- **General** — three toggles persisted through the page's `onSaveGeneral`: `chart_hide_labels`, `chart_auto_scale` and `chart_log_scale` (the modal also accepts the older per-key callbacks, but the page only passes the combined one; the page's `handleGeneralSettingsChange` writes all three keys in one PATCH, while `handleAutoScaleChange` writes `chart_auto_scale` alone when the user zooms or drags the price scale).
- **Waves** — `snap_to_wicks` plus per-degree wave-3/wave-5 alert percentages. Percentages are parsed and validated (non-numeric, non-finite or negative input blocks the save), and saving calls `onSaveWaveSettings`, which the page persists as `wave_settings` and follows with a wave-alert reconcile.
- **Fibonacci** — level toggles, enable-all/disable-all/reset and width-stop/`extendLines` editing for the retracement/extension tabs. Every fib handler returns early while `isFibInteractivityDisabled` (`disabled || !hasActiveDrawing`), and the page computes `hasActiveDrawing` from whether an effective retracement or extension drawing exists.

The modal is opened from the toolbar settings button or with `Cmd/Ctrl+,`, which `ChartDrawingsService.handleKeyDown` routes to `onChartSettingsOpen` — the page flips `isChartSettingsOpen`.

## Price alerts on the chart

### The alert primitive

`frontend/src/lib/components/charts/plugins/user-price-alerts/` renders price alerts as a series primitive and is deliberately **not** built on the shared drawing-primitive base: it needs pointer positions over the price scale (which the shared mouse engine clips away), so it ships its own `MouseHandlers` that attach `mouseleave`/`mousemove`/`click` to `chart.chartElement()`, and it exposes both pane views and **price-axis pane views** (`zOrder: 'top'`).

- `UserPriceAlerts.attached` creates one `UserAlertPricePaneView(false)` and one `UserAlertPricePaneView(true)`, attaches the mouse handlers and subscribes `alertsChanged` / `mouseMoved` / `clicked` to `requestUpdate`. A click inside the price-scale button column (`xPositionRelativeToPriceScale` between 1 and `buttonWidth`) adds an alert at `series.coordinateToPrice(y)`; a click on a hovered alert's remove button removes it.
- `updateAllViews` computes renderer data once for both renderers, finds the alert closest to the pointer within `showCentreLabelDistance`, and sets `_hoveringID` / `_currentCursor = 'pointer'` when the pointer is over the add button or a remove button. `hitTest()` reports `externalId: 'user-alerts-primitive'`.
- `UserAlertsState` stores alerts in a `Map`, exposes `alertAdded` / `alertRemoved` / `alertChanged` / `alertsChanged` delegates, keeps a price-descending array view, and generates random 6-digit ids, regenerating on collision.
- Rendering uses `positionsLine` for the alert line, the centre label, its divider and the price-scale label.

The chart component bridges the primitive to the backend: an `$effect` pushes `alerts` into `setAlerts([{ id: String(a.id), price: a.target_price }])`; `alertAdded` derives the condition from the last candle close (`price > close ? 'above' : 'below'`) and calls `onAddAlert`; `alertRemoved` parses the string id back to a number and calls `onRemoveAlert`. The page then creates/deletes through `AlertsService` and reloads the alert list, so the primitive always renders server state.

### Wave-derived alerts

Wave targets produce real price alerts with `source: 'wave'`. `handleWaveSettingsChange` (and the drawings service's wave-change path) call `scheduleWaveAlertsReconcile`, which chains `reconcileWaveAlertsForSecurity` onto a single promise — `onWaveChange` fires once per placed point, and concurrent reconciles reading stale `alerts` state would double-create. The reconcile reads `wave_settings` (defaulting to `DEFAULT_WAVE_SETTINGS`), computes desired levels with `computeWaveAlertLevels(settings, securityElliottWaves, lastClose)`, diffs them with `reconcileWaveAlerts(alerts, desired)`, applies the deletes and creates in parallel and calls `loadAlerts()` when anything changed. The initial page load also reconciles, but only after preferences have loaded, so a failed preference fetch can never mass-delete wave alerts. A reconcile failure only logs — the next run self-heals.

## The valuation band

The fair-value range reaches the chart as one primitive on the main price scale; the concept's own page ([Security Valuations](../concepts/security-valuation.md)) owns the model, routes, client and sidebar modal.

**Flow.** The page holds `valuation = $state<SecurityValuationRead | null>(null)` and mirrors it into `ChartDrawingsService` through a `setValuation` `$effect`. It is filled twice over: `loadValuation()` calls `valuationClient.getValuation(security.id)` in the init chain's parallel wave, and the fundamentals sidebar group — bound with `bind:valuation` and expanded by default — fetches the same endpoint through its own `$effect` and rebinds on save. The chart is **not** fed that state directly: the page passes `valuation={drawingsService.effectiveValuation}`, so the band renders the live valuation normally and the active rewind snapshot's range while rewound (the page suite asserts exactly that switch), and it passes `showValuation={showValuationOverlay}` and `showValuationBand={showValuationOverlay}`, so both gates carry the same flag. A save through the sidebar (`handleValuationSaved`) updates the page state and the service, then persists a rewind snapshot.

**The gate.** `showValuationOverlay` is seeded from the `show_valuation_band` user preference (`onPreferencesLoaded` and again in the init chain when preferences are fetched there), and toggled by `FundamentalsGroup`, which persists `userPreferencesService.patchPreferences({ show_valuation_band: val })`. Inside the chart, `isValuationBandVisible` is `showValuationBand !== undefined ? showValuationBand : showValuation`, so the narrower prop wins when supplied. One `$effect` pushes the state into the primitive: `setRange(visible ? valuation.lower_bound : null, visible ? valuation.upper_bound : null, visible)`, and the constructor at mount is seeded the same way — a `null` bound or `visible: false` makes the renderer return without drawing.

**The primitive.** `ValuationBandPrimitive` is a minimal `ISeriesPrimitive` with a single pane view (`zOrder: 'bottom'`, default fill `rgba(59, 130, 246, 0.12)`) whose renderer converts the two bounds to y coordinates via `series.priceToCoordinate` and, in one `useBitmapCoordinateSpace` callback, fills the band between them plus two dashed `rgba(59, 130, 246, 0.4)` boundary lines drawn with pixel-ratio-aware dash lengths. `setRange` forwards to the pane view and calls the stored `requestUpdate`. It has no delegates, no state class, no hit-test and no price-axis pane view.

**Relationship to the alert primitive.** Both are series primitives attached to the candlestick series and both are re-seeded from props by `$effect`s, but that is where the resemblance stops:

| | `ValuationBandPrimitive` | `UserPriceAlerts` |
|---|---|---|
| Pane views | one, `zOrder: 'bottom'` | one pane view plus one price-axis pane view, `zOrder: 'top'` |
| Mouse handling | none | own `MouseHandlers` over the chart element |
| Own state / delegates | none | `UserAlertsState` + four delegates |
| Backend round trip | read-only, rendered from a prop | click → `onAddAlert` → `AlertsService` → reload → `setAlerts` |
| Lifetime | attached at mount, never `destroy()`ed by the teardown | destroyed in the mount teardown |

Two consequences worth knowing when changing this area: the band's pane view declares `zOrder: 'bottom'`, so it paints under the candlestick series and under every drawing overlay; and because the mount teardown never calls its `destroy()`, only `detached()` runs when the chart is removed.

## Related rendering surfaces

- `utils/date.ts` supplies the chart's time formatting: `formatLocalTime` renders epoch seconds as `YYYY-MM-DD HH:mm` and passes date strings through unchanged (and formats a `BusinessDay` object itself), while `formatLocalTickMark` returns `null` for non-numeric times and otherwise formats by `TickMarkType` (year / month / day / time / time-with-seconds). `getChartDateWindow` is the shared window helper for the initial load, every timeframe change and every pagination fetch.
- `sparkline.svelte` is a chart-library-free SVG sparkline: it derives values from numbers or `Candle.close`, builds a Catmull-Rom smoothed line plus an area path in a fixed `0 0 100 height` view box with a gradient fill, colors by first-vs-last trend (or an explicit `isPositive`/`color`), and is used by the holdings views (`holdings-modal.svelte`) — it never touches `lightweight-charts`.

## Testing conventions

Chart tests are colocated with their subject and follow the repository rules in `frontend/AGENTS.md` and [Testing](../operations/testing.md). The binding constraint for this subsystem: **no test may perform a real network call or render a real chart.**

- `lightweight-charts` is replaced with a `vi.mock` factory exposing `createChart`, `CrosshairMode`, `CandlestickSeries`, `LineSeries`, `HistogramSeries`, `PriceScaleMode` and chainable `timeScale` / `priceScale` / `addSeries` / `attachPrimitive` mocks (the attach mock even fires `primitive.attached(...)` with a fake chart/series pair); `security-chart.test.ts` also stubs `Path2D` and `ResizeObserver` before importing the component.
- Canvas targets are faked: `useBitmapCoordinateSpace` invokes its callback with a fake `BitmapCoordinatesRenderingScope` (recording 2D context, media/bitmap sizes, `horizontalPixelRatio` / `verticalPixelRatio`), so renderer draw calls can be asserted — see `plugins/fibonacci/fibonacci.test.ts` and `plugins/valuation-band/valuation-band.test.ts`.
- Every API client a subject calls is mocked: the page suite `vi.mock`s `marketService`, `userPreferencesService`, `alertsService`, `notesService`, `documentsService`, `accountService`, `valuationClient`, `snapshotsService`, `indicatorsService` (keeping the real types via `importOriginal`) and the chart component itself, capturing its props so page→chart wiring can be asserted.
- `security-chart.test.ts` covers the surface directly: infinite scroll / logical-range behaviour, oscillator panes and custom price scales, `hideLabels`, the price-scale wheel zoom (linear and logarithmic, plus the "does not intercept wheel events over the canvas" case), the price-scale drag reporting `onAutoScaleChange(false)`, the drawing pan-lock and its restore rules, future whitespace, resizable indicator panes (legacy default margins, handle rendering per adjacent pair, drag bounds, restore via `setPaneHeights`, dropping a removed oscillator's height, and the reset affordance), overlay autoscale exclusion and the valuation band attachment.
- `indicator-pane-layout.test.ts` pins the pure math: the legacy margins for 0/1/2/3 oscillators and the volume variants, custom-height normalization, min/max clamping, and the water-filling allocator. `indicator-defaults.test.ts` pins the frozen table, key order and copy independence. `valuation-band.test.ts` pins the renderer's fill/dash behaviour and its no-draw cases.
- Page-level suites live in `routes/security/[security_id]/page.svelte.test.ts` (`Security Page - Asynchronous Indicator Integration`, `Security Page - Indicator Pane Heights`, `Security Page - Instant Shell with Async Chart Data`, `Security Page - Top Toolbar`, `Security Page - Viewport Containment & Scrolling Layout`, …), and `page.server.test.ts` asserts the load returns only `security_id` and never calls the market service.
- The backend side of the pipeline never dials a real sidecar or Redis in tests either: `tests/market/test_indicator_client.py` drives `IndicatorServiceClient` through `httpx.MockTransport` handlers (asserting the `/compute` path and the 504/503/400 mappings), while `tests/market/test_indicator_compute_api.py` patches `IndicatorServiceClient.compute` and `IndicatorCache.get`/`set` to cover the date-window 422, the cache hit/miss and read-write window symmetry, and the caller-supplied-candle path.

Run the chart suites with `./scripts/agent-test frontend/src/lib/components/charts/...` while iterating and `./scripts/agent-test frontend` before finishing.

## Invariants and safe-change notes

- **One writer for series data.** The `candles` `$effect` is the only place that calls `setData` on the candlestick series outside `updateData`; it no-ops on the same array reference, so the page must always replace the array (never mutate it) to signal a change.
- **Panes are price scales.** A new oscillator needs a price-scale id registered in `OSCILLATOR_PANE_IDS` (or an explicit entry in `orderedPaneIds`) *before* margins are applied, or its `scaleMargins` are silently skipped. Never let two panes claim overlapping bands — the default path and the custom path must both stay inside `[0, 1]`.
- **The default pane layout is legacy-exact by construction.** `computePaneScaleMargins` must keep delegating to `computeDefaultPaneScaleMargins` when no custom height applies to a present pane, otherwise the default chart look changes for every user.
- **Custom pane heights are a whole-key preference.** PATCH replaces `indicator_pane_heights`, so always send the complete map (or `null`); restoring a stored layout must go through `setPaneHeights` (no callback) to avoid an echo write-back.
- **Any manual price-scale interaction disables auto-scale.** Wheel zoom and price-scale drag both call `onAutoScaleChange(false)`, which is persisted as `chart_auto_scale`; a new scale-manipulating affordance must report the same way or the chart will fight the user on the next data update.
- **Stale-response guards are per indicator.** New indicator work must thread `sequenceCounter` / `indicatorSeq` (bulk) or the per-id sequence (single toggle), or a slow response can overwrite newer data or re-enable a disabled indicator.
- **Caller-supplied candles bypass the backend cache.** The cache key cannot describe a client-side candle set, so any new caller-candle path must keep the `if not request.candles` guard on both the read and the write.
- **A new indicator type is a sidecar change.** Add the type in `services/indicator-service` (`ComputeIndicator` plus the README table) and expose it through `INDICATOR_DEFAULTS`; do not add Python math for the compute path. Remember that too-few candles legitimately returns an empty series, so the UI must treat "no points yet" as normal rather than an error.
- **Chart code is browser-only.** The component is dynamically imported after navigation; anything that assumes `window`, `ResizeObserver` or a DOM container must stay inside that import (and inside `onMount`) so SSR never executes it.
- **Frontend tests never touch a real API or a real chart.** Mock every client module a subject calls and mock `lightweight-charts`; a `fetch` or canvas that actually runs is a broken test.
- **Preferences are additive.** New chart preferences belong in `UserPreferences` and must be persisted with a partial `patchPreferences` call; keep the key inventory authoritative on [User Preferences](../concepts/user-preferences.md).
- **Drawings and rewind have their own page.** Anything about the series-primitive plugin contract, drawing persistence, `ChartDrawingsService`, snapshots or the rewind timeline belongs in [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md) — do not duplicate it here. The valuation story belongs on [Security Valuations](../concepts/security-valuation.md).
