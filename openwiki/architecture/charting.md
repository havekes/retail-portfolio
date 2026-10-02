---
type: architecture
title: "Charting: Chart Surface, Panes & Indicators"
description: "The chart rendering surface of the security route: security-chart.svelte's mount, series and primitive lifecycle, candle updates, pagination and future whitespace, the price-scale pane model with custom pane heights and resize handles, timeframe and chart-style preferences, the indicator overlay/pane composition and stale-response guard, chart settings, and the price-alert primitive."
tags: [charting, lightweight-charts, indicators, panes, price-alerts, chart-preferences, svelte]
sources:
  - id: openwiki-source-e483fd3285d99d05c7b265cf
    resource: repo://frontend/AGENTS.md
  - id: openwiki-source-828ca202b10416efee3043c1
    resource: repo://frontend/src/lib/api/buildIndicatorEntry.ts
  - id: openwiki-source-31c465e6b7d0d36afe3ffe00
    resource: repo://frontend/src/lib/api/indicatorsService.ts
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
  - id: openwiki-source-8a10008d9bf8365255edbb33
    resource: repo://src/market/cache.py
  - id: openwiki-source-d8383d22d61483b00080a280
    resource: repo://src/market/router.py
  - id: openwiki-source-9fc85bceeb3edfbe3ab56a7c
    resource: repo://src/market/service.py
generated: { by: "openwiki/0.6.1", at: "2026-10-02T14:25:20.147Z" }
verified:
  - by: openwiki/0.6.1
    at: 2026-10-02T14:25:20.147Z
---

This page covers the chart *surface*: the `lightweight-charts` wrapper, its data and pane lifecycle, chart preferences, chart-side indicator consumption and the price-alert primitive. The server-side indicator compute contract (request/response schema, backend candle assembly, cache, timeouts) is owned by [Market Data & Indicators](../workflows/market-data-and-indicators.md) — this page only points at the client end of it. Drawing tools, their series-primitive plugins, drawing persistence and the snapshot/rewind pipeline are documented on [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md).

| Layer | Location | Owns |
|---|---|---|
| Chart surface | `frontend/src/lib/components/charts/security-chart.svelte` | chart instance, candlestick series, series primitives, price-scale panes, indicator series, whitespace, resize handles |
| Route orchestration | `frontend/src/routes/security/[security_id]/+page.svelte` + `page-data.svelte.ts` | data loading, timeframe/style preferences, indicator requests, pane-height persistence |
| Pane math | `frontend/src/lib/chart/indicator-pane-layout.ts` | pure pane-height distribution and `scaleMargins` computation |
| Indicator defaults | `frontend/src/lib/chart/indicator-defaults.ts` | the frozen default table and per-page copies |
| Indicator API client | `frontend/src/lib/api/indicatorsService.ts`, `$lib/api/buildIndicatorEntry.ts` | compute request/response types, preference-entry building |
| Chart settings | `frontend/src/lib/components/charts/chart-settings-modal.svelte` | general (labels / autoscale / log scale), wave settings, fib level/width editing |
| Price alerts | `frontend/src/lib/components/charts/plugins/user-price-alerts/` | alert lines, add/remove buttons, price-axis labels |
| Drawings & rewind | `frontend/src/lib/components/charts/plugins/*`, `$lib/utils/finance/*`, `$lib/services/ChartDrawingsService.svelte.ts` | see [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md) |

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
| Indicator preference entries | `frontend/src/lib/api/buildIndicatorEntry.ts` |
| Chart settings modal | `frontend/src/lib/components/charts/chart-settings-modal.svelte` |
| Price-alert primitive | `frontend/src/lib/components/charts/plugins/user-price-alerts/` |
| Bands overlay primitive | `frontend/src/lib/components/charts/plugins/bands-indicator.ts` |
| SVG sparkline (no chart library) | `frontend/src/lib/components/charts/sparkline.svelte` |

The chart bundle is loaded lazily: the page `await import('$lib/components/charts/security-chart.svelte')`s only after the security and its `1d` series resolve, so chart code never runs during SSR.

## Route data: identity first, series after navigation

`+page.server.ts` deliberately does almost nothing — it validates the `security_id` param (400 `Security ID is required` when absent) and returns `{ security_id }`. It never fetches the security or its prices.

`SecurityPageDataService` (`page-data.svelte.ts`) owns the post-navigation data wave. `load(securityId)`:

- increments a private `loadSeq` and discards its own result when a newer soft navigation has superseded it;
- fetches `getSecurity(securityId)` and `getPrices(securityId, from, to, '1d')` in parallel, using `getChartDateWindow(new SvelteDate(), '1d')`;
- treats a missing or empty `items` array as a *successful* load whose message lands in `error` (`No price data available for this security`);
- never throws — it returns the caught error so the page can route a 401 through `redirectOn401`.

Because identity and prices resolve after navigation, the page can render its shell immediately: `instantSecurity` is looked up in the already-loaded default watchlist so the titlebar shows the symbol before the fetch lands, and the chart region shows `Loading chart data...` until the dynamic import resolves. A per-security `$effect` resets tool state, `timeframeError`, `hasMoreData`, `isLoadingMore` and `securityChart` on every route transition, then runs the async init chain (preferences → candle mapping → alerts/holdings/valuation/snapshots → chart import). The async load always fetches the `1d` series, so after the chart module resolves the page force-refetches the active timeframe (`changeTimeframe(selectedInterval, { persist: false, force: true })`) when the selected interval is not `1d` and no timeframe change is already in flight.

## The chart surface (`security-chart.svelte`)

### Props and ownership

The component receives data and drawing-model state as props and reports intent back through callbacks; it persists nothing itself:

- Core: `candles`, `containerId`, `hasMoreData`, `isLoadingMore` (bindable), `onLoadMoreData`, `hideLabels`, `averagePrice`/`showAveragePrice`, `futureBars` (default `DEFAULT_FUTURE_BARS` = 100), `onPaneHeightsChange`.
- Price scale: `autoScale` (bindable intent via `onAutoScaleChange`), `logScale`, and `valuation` / `showValuation` / `showValuationBand`.
- Alerts: `alerts`, `onAddAlert(price, condition)`, `onRemoveAlert(id)`.
- Drawings: the Elliott-wave and Fibonacci prop/callback pairs, `securityDrawings` plus the measure / horizontal-line / free-form-line drawing flags, selections and change callbacks, `onDrawingDragStart` / `onDrawingDragEnd`, `onWaveDoubleClick`.
- Pane heights: `onPaneHeightsChange(heights | null)`.

Prop→primitive syncing happens in guarded `$effect`s that compare the primitive's current value against the incoming prop (using the finance-layer equality helpers) before calling a setter, so no update loop forms between prop and primitive.

### Mount, series and primitive wiring

`onMount` creates the chart with `CrosshairMode.Normal`, a transparent background, `formatLocalTime` as the time formatter, `formatLocalTickMark` as the tick-mark formatter, `ignoreWhitespaceIndices: false`, a hidden left price scale and a right price scale with `minimumWidth` 75 (`DEFAULT_PRICE_SCALE_MIN_WIDTH`), `autoScale` and `mode` seeded from the `autoScale`/`logScale` props. It then:

1. Subscribes `timeScale().subscribeVisibleLogicalRangeChange` for two duties: pagination and future-whitespace expansion.
2. Adds the main `CandlestickSeries` (`#26a69a` up / `#ef5350` down, borders off), instantiates a `ValuationBandPrimitive` and attaches it, then calls `updatePanes()`.
3. Attaches six more primitives to that series: `UserPriceAlerts` (with `setSymbolName('Price')`), `ElliottWavesPrimitive`, `FibonacciPrimitive`, `MeasurePrimitive`, `HorizontalLinePrimitive`, `FreeFormLinePrimitive`.
4. Subscribes each primitive's delegates and re-emits them as page callbacks — `alertAdded`/`alertRemoved`, `wavePointsChanged`, `drawingModeChanged`, `degreeChanged`, `waveTypeChanged`, `selectionChanged`, `doubleClicked`, `toolChanged`, `drawingsChanged`, `dragStarted`/`dragEnded`.
5. Installs a capture-phase, non-passive `wheel` listener that zooms the **price scale** (not the time scale) when the pointer sits over the price-scale strip, plus mouse/pointer down-move-up listeners (on the container and on `window`) that detect a vertical price-scale drag of more than 2 px and report `onAutoScaleChange(false)`, so the user's manual scale wins over autoScale.
6. Installs a `ResizeObserver` that resizes the chart to the container and re-runs `checkAndExpandWhitespace`.
7. Returns a teardown that removes every wheel/mouse/pointer listener, disconnects the observer, destroys the six drawing/alert primitives and only then calls `chartInstance.remove()`.

```mermaid
flowchart TD
    MOUNT["onMount"] --> CREATE["createChart with crosshair, localization, tickMarkFormatter, hidden left scale and right scale minimumWidth 75"]
    CREATE --> RANGE["subscribeVisibleLogicalRangeChange for pagination and whitespace expansion"]
    RANGE --> CANDLE["addSeries CandlestickSeries"]
    CANDLE --> VALBAND["attach ValuationBandPrimitive and updatePanes"]
    VALBAND --> SIX["attach UserPriceAlerts, ElliottWaves, Fibonacci, Measure, HorizontalLine, FreeFormLine"]
    SIX --> DELEGATES["subscribe every primitive delegate and re-emit as page callbacks"]
    DELEGATES --> INPUT["add capture-phase wheel zoom and price-scale drag listeners"]
    INPUT --> RESIZE["ResizeObserver resizes the chart and expands whitespace"]
    RESIZE --> TEARDOWN["teardown removes listeners, disconnects the observer, destroys six primitives then chartInstance.remove"]
```

Chart mount, series and primitive lifecycle. The valuation band is attached before, and destroyed separately from, the six drawing/alert primitives.

Separate `$effect`s keep the chart in sync with props: container size, the average-price dashed `IPriceLine`, the right price scale's `autoScale`/`mode`, the valuation band's range, and `hideLabels`, which drives `lastValueVisible` / `priceLineVisible` / `title` across every indicator series group (including the three MACD series and the three BB series).

### Drawing mode locks panning

One `$effect` ORs all five drawing flags and applies `handleScroll: { pressedMouseMove: !isDrawing }`. Each primitive's `drawingModeChanged` subscription restores `pressedMouseMove: true` only once *every* other drawing flag is off, so finishing one tool does not unlock panning while another is still active.

### Candle updates, pagination and future whitespace

The `candles` `$effect` is the single writer of series data:

- Same array reference → no-op (the page replaces the array when data changes, which is the change signal).
- Empty array → clear series data and every primitive's candle set, reset `currentWhitespaceCount` to `futureBars`, clear `previousFirstCandleTime` and `isLoadingMore`.
- **Prepending** (the first candle is older than the previously-seen first candle) → set data, then shift the visible logical range by the number of prepended candles so the viewport does not jump.
- **First load** → size `currentWhitespaceCount` from `futureBars` and the container width, then show the last 250 bars.
- Every non-empty update writes `seriesInstance.setData([...candles, ...generateFutureWhitespace(candles, currentWhitespaceCount)])` and pushes the raw candles into all five drawing primitives.

```mermaid
flowchart TD
    CHANGE["candles prop changes"] --> REF{"same array reference"}
    REF -- "yes" --> NOOP["no-op"]
    REF -- "no" --> EMPTY{"array is empty"}
    EMPTY -- "yes" --> CLEAR["clear series data and every primitive candle set and reset the whitespace count"]
    EMPTY -- "no" --> PREPEND{"first candle older than the previously seen first candle"}
    PREPEND -- "yes" --> SHIFT["set data then shift the visible logical range by the added candle count"]
    PREPEND -- "no" --> FIRST{"first load"}
    FIRST -- "yes" --> WINDOW["set data then show the last 250 bars"]
    SHIFT --> PUSH["push the candles into every drawing primitive"]
    WINDOW --> PUSH
    RANGE["visible logical range change"] --> PAGINATION{"range starts at or before bar 10 and more history exists"}
    PAGINATION -- "yes" --> LOADMORE["set isLoadingMore and call onLoadMoreData"]
    PAGINATION -- "no" --> EXPAND["checkAndExpandWhitespace grows the count when the viewport nears the right edge"]
    EXPAND --> SAVED["set data with the larger whitespace tail and re-apply the saved logical range"]
```

The candle `$effect` is the only writer of series data; the visible-range subscription drives pagination and whitespace expansion from the same prop.

Pagination lives on the same subscription: when `range.from <= 10 && !isLoadingMore && hasMoreData`, the component sets `isLoadingMore = true` and calls `onLoadMoreData()`. The page's `handleLoadMoreData` returns early while rewound, guards with `shouldFetchMoreData(...)`, fetches the older window for the active interval (anchored on the oldest candle's time), maps and sorts the rows, merges with `mergeCandles` (dedupe by `String(time)`, prepend), recomputes Heikin-Ashi candles and refreshes indicators — setting `hasMoreData = false` when the fetch is empty or adds no new candles, and clearing `isLoadingMore` in a `finally`. A separate `$effect` in the component also forces `isLoadingMore = false` whenever `hasMoreData` goes false.

Future whitespace is what makes drawing *ahead* of the last candle possible. `generateFutureWhitespace(candles, count)` returns `[]` for fewer than two candles or a non-positive count, derives the bar interval from the median spacing of the most recent candles (`computeIntervalSeconds`, last 8 spacings) and appends `count` whitespace points one interval apart via `addIntervalToTime`, preserving the reference candle's `Time` shape (epoch seconds vs. `YYYY-MM-DD` vs. `BusinessDay`). `checkAndExpandWhitespace(range)` re-enters only when it is not already updating, grows the count when the visible range approaches the right edge (threshold `max(lastCandleIndex + 1, currentEndIndex - 30)`, target `ceil(range.to - lastCandleIndex) + 100`) or when the container is wide enough to need more bars (`ceil(clientWidth / 4) + 100`), and re-applies the previously saved visible logical range so the expansion is invisible to the user.

### Imperative surface

Exports consumed through `bind:this` from the page:

| Export | Purpose |
|---|---|
| `updateData(candles)` | Replace series data (plus whitespace) and show the last 250 bars; sets `lastCandlesRef` so the candle effect does not re-apply, and does **not** push candles into the drawing primitives |
| `addIndicator` / `updateIndicatorData` / `removeIndicator` | Add, refresh or drop an indicator series group |
| `getPaneHeights` / `setPaneHeights` / `resetPaneHeights` | Read, restore (no change callback) or clear the custom pane layout |
| `clearWave`, `getAllWaves`, `getSelectedWaveDegree` / `setSelectedWaveDegree`, `getSelectedWaveId` / `setSelectedWaveId`, `getElliottWavesPrimitive` | Elliott-wave proxy API |
| `clearFibonacci`, `getSelectedFibTool` / `setSelectedFibTool`, `getFibonacciPrimitive` | Fibonacci proxy API |
| `getMeasurePrimitive`, `getSelectedMeasureId` / `setSelectedMeasureId`, `getHorizontalLinePrimitive`, `getSelectedHorizontalLineId` / `setSelectedHorizontalLineId`, `getLinePrimitive`, `getSelectedLineId` / `setSelectedLineId` | New-tool proxy API |
| `updateWaveDegree`, `getValuationBandPrimitive` | Wave-degree reassignment and valuation-band access |

## Panes: price scales carved out with `scaleMargins`

`lightweight-charts` has no native panes here. Every "pane" is a **price-scale id** whose visible band is expressed with `scaleMargins` (`top`/`bottom` fractions of the chart height):

- `MAIN_PANE_ID` = `'main'` is the candlestick series' own scale (the right price scale); `VOLUME_PANE_ID` = `'volume'`; `OSCILLATOR_PANE_IDS` = `['rsi', 'macd', 'obv']` fixes the stacking order.
- The component keeps `orderedPaneIds` in explicit state (not derived from `indicatorSeries`) so it updates reliably when indicators are added or removed imperatively. `getOrderedPaneIds()` builds `main`, then `volume` when present, then the oscillators in order.
- `applyPaneMargins()` refreshes the ids, calls `computePaneScaleMargins(paneIds, customPaneHeights)` and applies the result — `seriesInstance.priceScale().applyOptions({ scaleMargins })` for `main`, `chartInstance.priceScale(id).applyOptions({ scaleMargins })` for the others. `updatePanes()` is that same call, invoked after every add/remove, on restore and on every pane-drag move.

`bb` (Bollinger Bands) is an *overlay*, not an oscillator: it is drawn on the main price scale and never triggers a pane re-layout.

### Default layout math (`indicator-pane-layout.ts`)

The pure module is the single owner of the arithmetic; the chart only applies the result. With no applicable custom height it returns the exact margins the chart used before resizing existed (`computeDefaultPaneScaleMargins`):

- No oscillators, no volume → `main { top: 0.1, bottom: 0.1 }`.
- Volume only → `volume { top: 0.7, bottom: 0 }`, `main { top: 0.1, bottom: 0.35 }`.
- Oscillators present → per-oscillator height `0.25` (one), `0.18` (two), `0.14` (three), a `0.02` gap between panes, `mainAreaHeight = max(0.3, 1 - count * (paneHeight + gap))`; volume (when enabled) takes the bottom 25% of the main area and the candlestick scale is squeezed accordingly; oscillators are stacked below the main area in `OSCILLATOR_PANE_IDS` order.

With custom heights, `distributePaneHeights` allocates `1 - TOP_MARGIN (0.05) - BOTTOM_MARGIN (0) - (n - 1) * PANE_GAP (0.02)` across the ordered panes proportionally to their weights — the custom height when valid, otherwise the derived default band height, otherwise the `DEFAULT_PANE_HEIGHTS` fallback (`main 0.5`, `volume 0.15`, `rsi 0.25`, `macd 0.18`, `obv 0.14`) — clamped to `[MIN_PANE_FRACTION (0.08), MAX_PANE_FRACTION (0.8)]`. `allocatePaneHeights` is a water-filling allocator: panes whose proportional share falls outside the bounds are pinned to the bound and the remainder is redistributed among the rest, so the result is always non-overlapping and inside `[0, 1]`. `computePaneBandHeights` converts the margins back into visible band heights for the drag logic.

```mermaid
flowchart TD
    IDS["orderedPaneIds: main then volume then rsi, macd, obv in order"] --> CUSTOM{"any custom height applies to a present pane"}
    CUSTOM -- "no" --> DEFAULT["computeDefaultPaneScaleMargins returns the legacy layout"]
    CUSTOM -- "yes" --> DIST["distributePaneHeights allocates 1 minus margins and gaps by weight"]
    DIST --> ALLOC["allocatePaneHeights water-fills around MIN and MAX pane fractions"]
    ALLOC --> STACK["lay the panes top-to-bottom with PANE_GAP between them"]
    DEFAULT --> APPLY["apply scaleMargins per price scale id"]
    STACK --> APPLY
```

Pane model: the default path and the custom path both end in the same per-price-scale `scaleMargins` application.

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
- `applySavedPaneHeights(prefs)` calls `chartRef?.setPaneHeights?.(heights)` behind a `setTimeout(..., 100)` so the chart ref is bound first, and does nothing when the stored map is absent or empty. It runs both from the init chain and from `onPreferencesLoaded`.
- `ChartInstance` (the interface `ChartDrawingsService` and the page use) exposes `setPaneHeights` as optional, which is why the call is guarded.

## Timeframe and chart-style preferences

The toolbar offers five intervals — `1h`, `4h`, `1d`, `1w`, `1m` — and two chart styles, `candlestick` and `heikin_ashi`.

`changeTimeframe(interval, { persist, force })` bails out without a security id, while `isChangingTimeframe`, or when `shouldForceRefetch(selectedInterval, interval, force)` is false (it is true when `force` is set or the interval differs). It then resets pagination state, computes the window with `getChartDateWindow(new Date(), interval)` (a 30-day window for intraday intervals, a 2-year window otherwise), fetches through `MarketService.getPrices`, maps intraday rows to `UTCTimestamp` epoch seconds and daily-or-coarser rows to their date string, sorts oldest→newest, sets `rawCandles`, recomputes `haCandles = convertToHeikinAshi(rawCandles)` and calls `refreshActiveIndicators()`. An empty response sets `timeframeError` (`No price data available for this timeframe`). The preference patch is issued **after** the fetch `try/catch` and only when `persist && fetchOk`, so a failed preference write can neither mask a fetch error nor hold `isChangingTimeframe` open.

`displayCandles = displayCandlesFor(chartStyle, rawCandles, haCandles)` feeds the chart; the two style buttons set `chartStyle`, call `refreshActiveIndicators()` and PATCH `chart_style`. Rewind slices that derived array (`sliceCandlesBefore`) before it reaches the chart. `chart-preferences.ts` holds the pure helpers the page relies on: `mergeChartPreferences` (preserves the `indicators` key across partial writes), `displayCandlesFor`, `shouldForceRefetch`, `parseCandleTime` (number / `YYYY-MM-DD` / ISO string / `BusinessDay` → `Date`), `mergeCandles` and `shouldFetchMoreData`.

`onPreferencesLoaded(prefs)` applies the persisted state in order: `show_valuation_band`, the saved pane heights, the drawings service's preferences, chart style (falling back to `heikin_ashi`), the saved timeframe via `changeTimeframe(prefs.timeframe, { persist: false })`, and finally the saved indicator toggles — each `onIndicatorToggle(id, true)` deferred through `setTimeout(..., 100)` so the chart ref is bound.

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

Each branch records the group in `indicatorSeries` and appends to `activeIndicators`, then calls `updatePanes()` (except `bb`, which is an overlay). `removeIndicator(type)` detaches the bands primitive before removing the three BB series, removes all three MACD series, or removes the single series, then drops the group and any stale custom pane height and re-applies the margins. `updateIndicatorData(indicator)` refreshes `setData` per series shape and falls back to `addIndicator` when the group does not exist yet.

### Chart-side consumption of the compute response

The request/response contract and the backend path (candle assembly, Heikin-Ashi conversion, cache, indicator-service timeouts) live on [Market Data & Indicators](../workflows/market-data-and-indicators.md). The chart-side obligations are:

- `IndicatorsService.computeIndicators(securityId, request)` POSTs to `/api/v1/market/securities/{security_id}/indicators/compute`; the page reads each series from `res.indicators[id] ?? res.indicators[spec.type] ?? []` and converts it into an `IndicatorData` group for `removeIndicator` + `addIndicator`.
- `buildIndicatorSpec(id, config)` copies only the **positive** numeric fields (`period`, `fast`, `slow`, `signal`, `stdDev`) plus the raw `settings` bag. `buildIndicatorEntry(newConfig, current)` in `$lib/api/buildIndicatorEntry.ts` is the inverse mapping used when persisting: it promotes the flat numeric fields emitted by the config modal into the `settings` bag and preserves existing `settings` keys as a fallback.
- Each request carries `interval`, `chart_style` and the specs, and adds `candles` only when the chart is rewound (`getRewoundCandlesPayload()` slices `rawCandles` at the timeline position). The backend then bypasses its cache for such requests — see the workflow page.

### Round trip and the out-of-order guard

```mermaid
sequenceDiagram
    participant Page as Security page
    participant Api as IndicatorsService
    participant Router as Market router
    participant Engine as Indicator service

    Page->>Page: refreshActiveIndicators bumps sequenceCounter and stamps indicatorSeq
    Page->>Api: computeIndicators with interval, chart style and specs
    alt rewound
        Page->>Page: getRewoundCandlesPayload slices the candles at the playhead
        Page->>Api: the request carries the caller-supplied candles
    end
    Api->>Router: POST to the security indicators compute route
    Router->>Engine: compute with candles and specs
    Engine-->>Router: indicators keyed by spec id
    Router-->>Api: indicators map
    Api-->>Page: indicators map
    Page->>Page: discard the response when indicatorSeq no longer matches
    Page->>Api: removeIndicator then addIndicator per accepted spec
```

Indicator compute round trip: the page stamps a monotonic sequence per request and discards a response whose sequence is stale.

Two request paths share one guard:

- `refreshActiveIndicators()` (bulk: timeframe change, chart-style change, rewind scrub, load-more) increments `sequenceCounter`, records it in `activeRefreshSeq`, and writes that sequence into `indicatorSeq[id]` for **every enabled indicator**. When the response lands it is accepted per indicator only if `indicatorConfigs[id]?.enabled && indicatorSeq[id] === seq`.
- `onIndicatorToggle(id, enabled)` (single) bumps `sequenceCounter` into `indicatorSeq[id]`, sends one spec, and accepts the response only if the stored sequence still matches, the indicator is still enabled and the chart ref exists. Disabling removes the series immediately and bumps `indicatorSeq[id]` so an in-flight response cannot resurrect a disabled indicator.

This is the standard defence against out-of-order responses when the user toggles indicators quickly or changes timeframe mid-flight; `isLoadingIndicators` drives the toolbar spinner and is only cleared by the newest request.

Two "indicators" never reach the backend:

- `volume` is rendered locally from `displayCandles` (`removeIndicator('volume')` then `addIndicator` with `close >= open ? '#26a69a80' : '#ef535080'`).
- `avgPrice` is not a series at all: it is a dashed `IPriceLine` created/removed by an `$effect` from `averagePrice` + `showAveragePrice`, fed by `blendedAverageCost(holdings)`, and it is skipped when building specs.

## Chart settings

`chart-settings-modal.svelte` has three sections, each with local draft state and a save/cancel pair. Two of them resync from props through a `$effect` guard rather than a raw identity comparison: general compares the three boolean props against their previous values, and waves compares `JSON.stringify(waveSettings)` keys, because `waveSettings` is a `$state` proxy re-created on parent re-renders (a `!==` check trips Svelte's `state_proxy_equality_mismatch`).

- **General** — the hide-labels, auto-scale and log-scale toggles. Saving invokes each dedicated `onSaveChart*` callback *and* `onSaveGeneral({ hideLabels, autoScale, logScale })`; the page passes `onSaveGeneral` = `handleGeneralSettingsChange`, which PATCHes `chart_hide_labels`, `chart_auto_scale` and `chart_log_scale` in one partial write.
- **Waves** — `snap_to_wicks` plus per-degree wave-3/wave-5 alert percentages for `cycle` and `primary`. Each percentage goes through `parsePercentInput`, and non-numeric, non-finite or negative input blocks the save (`isWavesValid` is false); saving calls `onSaveWaveSettings`, which the page persists as `wave_settings` and follows with a wave-alert reconcile.
- **Fibonacci** — level toggles, enable-all/disable-all/reset and width-stop/`extendLines` editing for the retracement/extension tabs. `isFibInteractivityDisabled = disabled || !hasActiveDrawing` gates every handler, and the page computes `hasActiveDrawing` from whether a retracement or extension drawing exists.

The modal is opened from the toolbar settings button or with `Cmd/Ctrl+,`, which `ChartDrawingsService.handleKeyDown` routes to `onChartSettingsOpen` — the page flips `isChartSettingsOpen`.

## Price alerts on the chart

### The alert primitive

`frontend/src/lib/components/charts/plugins/user-price-alerts/` renders price alerts as a series primitive and is deliberately **not** built on the shared drawing-primitive base: it needs pointer positions over the price scale (which the shared mouse engine clips away), so it ships its own `MouseHandlers`, and it exposes both pane views and **price-axis pane views**.

- `UserPriceAlerts.attached` creates one `UserAlertPricePaneView(false)` and one `UserAlertPricePaneView(true)`, attaches the mouse handlers and subscribes `alertsChanged` / `mouseMoved` / `clicked` to `requestUpdate`. A click inside the price-scale button column (`_isHovering` tests `xPositionRelativeToPriceScale` against `buttonWidth`) adds an alert at `series.coordinateToPrice(y)`; a click on a hovered alert's remove button removes it.
- `updateAllViews` computes renderer data once for both renderers, finds the alert closest to the pointer within `showCentreLabelDistance`, and sets `_hoveringID` / `_currentCursor = 'pointer'` when the pointer is over the add button or a remove button. `hitTest()` reports `externalId: 'user-alerts-primitive'`.
- `UserAlertsState` stores alerts in a `Map`, exposes `alertAdded` / `alertRemoved` / `alertChanged` / `alertsChanged` delegates, keeps a price-descending array view, and generates random 6-digit ids, regenerating on collision.
- Rendering uses `positionsLine` for the alert line, the centre label, its divider and the price-scale label.

The chart component bridges the primitive to the backend: an `$effect` pushes `alerts` into `setAlerts([{ id: String(a.id), price: a.target_price }])`; `alertAdded` derives the condition from the last candle close (`alert.price > currentPrice ? 'above' : 'below'`) and calls `onAddAlert`; `alertRemoved` parses the string id back to a number and calls `onRemoveAlert`. The page then creates/deletes through `AlertsService` and reloads the alert list, so the primitive always renders server state.

### Wave-derived alerts

Wave targets produce real price alerts with `source: 'wave'`. `handleWaveSettingsChange` (and the drawings service's wave-change path) call `scheduleWaveAlertsReconcile`, which chains `reconcileWaveAlertsForSecurity` onto a single promise — `onWaveChange` fires once per placed point, and concurrent reconciles reading stale `alerts` state would double-create. The reconcile reads `wave_settings` (defaulting to `DEFAULT_WAVE_SETTINGS`), computes desired levels with `computeWaveAlertLevels(settings, securityElliottWaves, lastClose)`, diffs them with `reconcileWaveAlerts(alerts, desired)`, applies the deletes and creates in parallel and calls `loadAlerts()` when anything changed. Reconciles are skipped entirely while rewound, and the initial page load reconciles only after preferences have loaded, so a failed preference fetch can never mass-delete wave alerts. A reconcile failure only logs — the next run self-heals.

## Related rendering surfaces

- `utils/date.ts` supplies the chart's time formatting: `formatLocalTime` renders epoch seconds as `YYYY-MM-DD HH:mm` and passes date strings through unchanged (and formats a `BusinessDay` object itself), while `formatLocalTickMark` returns `null` for non-numeric times and otherwise formats by `TickMarkType` (year / month / day / time / time-with-seconds). `getChartDateWindow` is the shared window helper for the initial load, every timeframe change and pagination.
- `sparkline.svelte` is a chart-library-free SVG sparkline: it derives values from numbers or `Candle.close`, builds a Catmull-Rom smoothed line plus an area path in a fixed `0 0 100 height` view box, colors by first-vs-last trend (or an explicit `isPositive`/`color`), and is used by the holdings views — it never touches `lightweight-charts`.

## Testing conventions

Chart tests are colocated with their subject and follow the repository rules in `frontend/AGENTS.md` and [Testing](../operations/testing.md). The binding constraint for this subsystem: **no test may perform a real network call or render a real chart.**

### The `security-chart.test.ts` harness

- `Path2D` and `ResizeObserver` are polyfilled onto `globalThis` at module scope *before* the component import, guarded by `typeof globalThis.X === 'undefined'`, so jsdom never sees an undefined constructor.
<!-- openwiki: broken internal link [{ from, to }] file "{ from, to }" does not exist. Fix the href or restore the target, then delete this comment. -->
- `lightweight-charts` is replaced by a `vi.mock` factory returning `createChart`, `CrosshairMode`, `CandlestickSeries`, `LineSeries`, `HistogramSeries` and `PriceScaleMode`. The `createChart` mock is stateful: it keeps a per-id `Map` of price-scale mocks (`applyOptions`, `width`, `getVisibleRange` / `setVisibleRange` backed by a closure variable, `setAutoScale`), records logical-range callbacks into a module-level `rangeCallbacks` array so a test can drive pagination by invoking `rangeCallbacks[0]({ from, to })`, and returns one chainable series object per `addSeries` call.
- `attachPrimitive` is itself a mock that invokes the primitive's `attached(...)` with a hand-built `SeriesAttachedParameter` (a fake chart element, `timeScale()` with `timeToCoordinate` / `coordinateToTime` / `height` / `width`, a `priceScale()` with `width` and `applyOptions`, `options()`, `applyOptions`, a series with `priceToCoordinate` / `coordinateToPrice`, and `requestUpdate`) — this is what lets real primitives (Elliott waves, Fibonacci, measure, lines, valuation band) run inside the mocked chart.
- Tests reach the component's exported imperative API by casting `rendered.component as unknown as SecurityChartInstance`, then stringify mock call arguments to assert `scaleMargins` per price-scale id (helpers such as `lastScaleMargins`, `bandHeight`).
- Render helpers stretch the container via `Object.defineProperty(container, 'clientWidth' / 'clientHeight', ...)` plus a stubbed `getBoundingClientRect`, which is what makes the price-scale strip (container width minus the price-scale width) computable in jsdom.

### The plugin harness

Plugin tests build a fake `CanvasRenderingTarget2D` whose `useBitmapCoordinateSpace` invokes the callback with a fake `BitmapCoordinatesRenderingScope` (a recording 2D context that logs every `moveTo` / `lineTo` / `arc` / `fill` / `stroke` / `fillText` call with its effective colour, plus `horizontalPixelRatio` / `verticalPixelRatio` and media/bitmap sizes), so renderer draw calls can be asserted. They build a chart/series pair by hand (`createMockChartAndSeries`: a chart element with a stubbed bounding rect, a `timeScale` with coordinate conversions, a `priceScale` with `width` / `applyOptions`) instead of using the `lightweight-charts` module at all.

### Page-level suites

Every API client the page touches is mocked at module scope (`marketService`, `userPreferencesService`, `alertsService`, `notesService`, `documentsService`, `accountService`, `valuationClient`, `snapshotsService`, `indicatorsService` via `importOriginal` so the real types survive), as are `$app/paths` and `$app/navigation`, and the chart component itself:

```ts
vi.mock('$lib/components/charts/security-chart.svelte', () => ({
	default: (...args: any[]) => {
		mockChartProps = args[1] ?? args[0];
		return { addIndicator: mockAddIndicator, removeIndicator: mockRemoveIndicator, setPaneHeights: mockSetPaneHeights };
	}
}));
```

The mock records the props the page passed so tests can assert `candles`, drive `onPaneHeightsChange` manually and observe the resulting `patchPreferences` call. Fixtures are registered per security via a `stubMarketFixtures(security, items)` helper, and each `beforeEach` re-implements `getSecurity` / `getPrices` off those maps — the page fetches on mount, so no test may depend on the previous test's state.

Suites include `Security Page - Asynchronous Indicator Integration`, `Security Page - Indicator Pane Heights`, `Security Page - Instant Shell with Async Chart Data`, `Security Page - Chart Settings Modal & Wave Settings Integration`, `Security Page - Wave Target Alert Reconcile`, `Security Page - Top Toolbar`, `Security Page - Viewport Containment & Scrolling Layout`, and the drawing-tool suites. `page.server.test.ts` asserts the load returns only `security_id` and never calls the market service. `indicator-pane-layout.test.ts` pins the pure math (legacy margins for 0/1/2/3 oscillators and the volume variants, custom-height normalization, min/max clamping, the water-filling allocator); `indicator-defaults.test.ts` pins the frozen table, key order and copy independence.

Run the chart suites with `./scripts/agent-test frontend/src/lib/components/charts/...` while iterating and `./scripts/agent-test frontend` before finishing.

## Invariants and safe-change notes

- **One writer for series data.** The `candles` `$effect` is the only place that calls `setData` on the candlestick series outside `updateData`; it no-ops on the same array reference, so the page must always replace the array (never mutate it) to signal a change.
- **Panes are price scales.** A new oscillator needs a price-scale id registered in `OSCILLATOR_PANE_IDS` (or an explicit entry in `orderedPaneIds`) *before* margins are applied, or its `scaleMargins` are silently skipped. Never let two panes claim overlapping bands — the default path and the custom path must both stay inside `[0, 1]`.
- **The default pane layout is legacy-exact by construction.** `computePaneScaleMargins` must keep delegating to `computeDefaultPaneScaleMargins` when no custom height applies, otherwise the default chart look changes for every user.
- **Custom pane heights are a whole-key preference.** PATCH replaces `indicator_pane_heights`, so always send the complete map (or `null`); restoring a stored layout must go through `setPaneHeights` (no callback) to avoid an echo write-back.
- **Stale-response guards are per indicator.** New indicator work must thread `sequenceCounter` / `indicatorSeq` (bulk) or the per-id sequence (single toggle), or a slow response can overwrite newer data or re-enable a disabled indicator.
- **Teardown order matters.** The teardown destroys the six drawing/alert primitives before `chartInstance.remove()`, and every listener added by mount is removed with the same options object (`{ capture: true }` for `wheel`) — mismatched options leak the listener across hot navigation.
- **Chart code is browser-only.** The component is dynamically imported after navigation; anything that assumes `window`, `ResizeObserver` or a DOM container must stay inside that import (and inside `onMount`) so SSR never executes it.
- **Preferences are additive.** New chart preferences belong in `UserPreferences` and must be persisted with a partial `patchPreferences` call; `mergeChartPreferences` exists specifically so a chart-style or timeframe patch cannot clobber the `indicators` key, and `buildIndicatorEntry` exists so flat modal fields survive as `settings`.
- **The compute contract lives elsewhere.** Changing the indicator request/response shape, the backend cache rule or the timeout mapping means updating [Market Data & Indicators](../workflows/market-data-and-indicators.md), not this page.
- **Drawings and rewind have their own page.** Anything about the series-primitive plugin contract, drawing persistence, `ChartDrawingsService`, snapshots or the rewind timeline belongs in [Chart Drawings, Plugins & Rewind](./chart-drawings-and-rewind.md) — do not duplicate it here.
