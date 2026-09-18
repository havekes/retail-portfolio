---
type: "Reference"
title: "Charting, Drawing Tools & Rewind"
description: "The security-chart subsystem: lightweight-charts wrapper data flow and pane layout, chart preferences and intervals, indicator overlays, the drawing-tool series-primitive plugin architecture, the finance-math boundary, and the chart snapshot plus rewind-timeline pipeline."
tags: [charting, lightweight-charts, drawing-tools, chart-plugins, series-primitives, snapshots, rewind, finance, svelte]
verified:
  - by: openwiki/0.5.2
    at: 2026-09-18T20:16:58.058Z
sources:
  - id: openwiki-source-e483fd3285d99d05c7b265cf
    resource: repo://frontend/AGENTS.md
  - id: openwiki-source-b3e4be2ad686e33030d95480
    resource: repo://frontend/src/lib/api/snapshotsService.ts
  - id: openwiki-source-fd6bc3ef355365f09e91de6e
    resource: repo://frontend/src/lib/chart-preferences.ts
  - id: openwiki-source-31c8f2b5a9dd5358a3f2d5e4
    resource: repo://frontend/src/lib/chart/indicator-defaults.ts
  - id: openwiki-source-fb99e8c672ac1be25256c5d6
    resource: repo://frontend/src/lib/components/charts/drawing-toolbar.svelte
  - id: openwiki-source-a9460eb617e8b683c329d161
    resource: repo://frontend/src/lib/components/charts/plugins/bands-indicator.ts
  - id: openwiki-source-0899a375901b4e4ae6956de0
    resource: repo://frontend/src/lib/components/charts/plugins/elliott-wave/constants.ts
  - id: openwiki-source-a6e37881d41ceff28b8379d1
    resource: repo://frontend/src/lib/components/charts/plugins/elliott-wave/elliott-wave.test.ts
  - id: openwiki-source-0bcb330ed032dd88be0b8007
    resource: repo://frontend/src/lib/components/charts/plugins/elliott-wave/mouse.ts
  - id: openwiki-source-f0cbb81531a713f349eea905
    resource: repo://frontend/src/lib/components/charts/plugins/elliott-wave/pane-renderer.ts
  - id: openwiki-source-5ef2aaeaa542e5165e410203
    resource: repo://frontend/src/lib/components/charts/plugins/elliott-wave/state.ts
  - id: openwiki-source-2327399d14649ed7bc761322
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/constants.ts
  - id: openwiki-source-7f6a7e419b780bc85a32e460
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/fibonacci-primitive.ts
  - id: openwiki-source-e03b7d6203bf399f13c8a612
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/fibonacci.test.ts
  - id: openwiki-source-2db6a21f5aac13379d4b785e
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/index.ts
  - id: openwiki-source-1bcc6defb0be49eac92b3731
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/mouse.ts
  - id: openwiki-source-5585c043841faff27604fade
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/pane-renderer.ts
  - id: openwiki-source-67e8f9c5ad57cc2ffebb9aa8
    resource: repo://frontend/src/lib/components/charts/plugins/fibonacci/state.ts
  - id: openwiki-source-d50bca22da3c710b52d395f3
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/delegate.ts
  - id: openwiki-source-898733aeba4f6b31c6e70ce6
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/dimensions/positions.ts
  - id: openwiki-source-39ade351e56c45d62c2cd57b
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/mouse/chart-mouse-handlers.ts
  - id: openwiki-source-a7fb218c7e744c08bb27f67e
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/mouse/snap.ts
  - id: openwiki-source-edc6819abc64151890aee8b3
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/primitive/drawing-primitive-base.ts
  - id: openwiki-source-9f9c8c586edc33d1fc16d42a
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/time/time-projector.ts
  - id: openwiki-source-c19a08eca0dccf2c925cc86a
    resource: repo://frontend/src/lib/components/charts/plugins/helpers/time/time.ts
  - id: openwiki-source-7d36a2f693a30c914e86e954
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/mouse.ts
  - id: openwiki-source-941653498d1b63aac1733626
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/pane-renderer.ts
  - id: openwiki-source-af5ee747460de5273d8c5d4a
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/state.ts
  - id: openwiki-source-d4f0cd24cd75b5cc0da82f96
    resource: repo://frontend/src/lib/components/charts/plugins/user-price-alerts/user-price-alerts.ts
  - id: openwiki-source-3228ff446bd4627bdd629dbc
    resource: repo://frontend/src/lib/components/charts/rewind-timeline.svelte
  - id: openwiki-source-f3f1cc2c4a00583ef3f09eae
    resource: repo://frontend/src/lib/components/charts/rewind-timeline.test.ts
  - id: openwiki-source-e1b2cd5ba1ffb9b4e60e9356
    resource: repo://frontend/src/lib/components/charts/rewind-timeline.ts
  - id: openwiki-source-277415f21fdc20b26619d18d
    resource: repo://frontend/src/lib/components/charts/security-chart.svelte
  - id: openwiki-source-c3b7cc10403cbc15934d0991
    resource: repo://frontend/src/lib/components/charts/security-chart.test.ts
  - id: openwiki-source-f97400306b886f7bcb3e07b4
    resource: repo://frontend/src/lib/utils/date.ts
  - id: openwiki-source-adea4aefcddb6aff88b5b377
    resource: repo://frontend/src/lib/utils/finance/average-cost.ts
  - id: openwiki-source-1ddc32372d0074f90bb96a09
    resource: repo://frontend/src/lib/utils/finance/bollinger-bands.ts
  - id: openwiki-source-f461c05693245b4eec87e699
    resource: repo://frontend/src/lib/utils/finance/candle.ts
  - id: openwiki-source-83a11d11099dd45809d0d35d
    resource: repo://frontend/src/lib/utils/finance/elliott-wave.ts
  - id: openwiki-source-726f90f130768013f18fb009
    resource: repo://frontend/src/lib/utils/finance/fibonacci.ts
  - id: openwiki-source-6ed5be08ea41afe82aa62fc4
    resource: repo://frontend/src/lib/utils/finance/holdings-metrics.ts
  - id: openwiki-source-6b10e5341303c34ffb1e7780
    resource: repo://frontend/src/lib/utils/finance/macd.ts
  - id: openwiki-source-e1676bc35619fba3d5703392
    resource: repo://frontend/src/lib/utils/finance/moving-average.ts
  - id: openwiki-source-0f99dde4b6e4f924abd310c3
    resource: repo://frontend/src/lib/utils/finance/obv.ts
  - id: openwiki-source-b3dcb90c7222d4a70af36cd4
    resource: repo://frontend/src/lib/utils/finance/rewind.ts
  - id: openwiki-source-0d27f731257e9dca10e9bdd5
    resource: repo://frontend/src/lib/utils/finance/rsi.ts
  - id: openwiki-source-6eb7daa700f1b21e5dc1b9aa
    resource: repo://frontend/src/lib/utils/finance/wave-alerts.ts
  - id: openwiki-source-33c886f28072e35f81eadfae
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/%2Bpage.server.ts
  - id: openwiki-source-67b769eb99d4518b98fe1ca7
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/%2Bpage.svelte
  - id: openwiki-source-ddd6d556671e35d3baea7163
    resource: repo://frontend/src/routes/security/%5Bsecurity_id%5D/page.svelte.test.ts
  - id: openwiki-source-115309495c76af76d0a6a997
    resource: repo://migrations/versions/bea77d72aaf1_add_market_chart_snapshots.py
  - id: openwiki-source-336c8d4ea788e2c5f7cddd73
    resource: repo://src/market/__init__.py
  - id: openwiki-source-cc33fb93093886e62b166a26
    resource: repo://src/market/model.py
  - id: openwiki-source-8ba9c7034638e16be9336256
    resource: repo://src/market/repository_sqlalchemy.py
  - id: openwiki-source-47b0223ca650e12504aa1417
    resource: repo://src/market/repository.py
  - id: openwiki-source-d8383d22d61483b00080a280
    resource: repo://src/market/router.py
  - id: openwiki-source-ef56252cb773f63950e8458e
    resource: repo://src/market/schema.py
generated: { by: "openwiki/0.5.2", at: "2026-09-18T20:16:58.058Z" }
---

# Charting, Drawing Tools & Rewind

Charting is the largest frontend subsystem. It is built on `lightweight-charts` and split into three layers that must not bleed into each other:

1. **Rendering & interaction** — `security-chart.svelte` owns the chart instance, series, panes and primitives.
2. **Drawing tools** — self-contained plugins under `frontend/src/lib/components/charts/plugins/<plugin>/`, each a series primitive with its own state, mouse adapter, pane view and canvas renderer.
3. **Financial math** — pure, unit-tested formulas in `frontend/src/lib/utils/finance/`.

Chart snapshots and the rewind timeline sit on top: they persist drawings + the displayed data window to the backend and let the user replay the chart as it looked at a past moment.

See [Frontend Architecture](./frontend.md) for the app-wide layering and [Testing](../operations/testing.md) for the repository-wide test policy.

## Entry points

| Concern | Location |
|---|---|
| Chart component (renders the chart, owns primitives) | `frontend/src/lib/components/charts/security-chart.svelte` |
| Security page (data loading, preferences, rewind orchestration) | `frontend/src/routes/security/[security_id]/+page.svelte` (+ `+page.server.ts`) |
| Drawing toolbar (wave/fib tools, Save snapshot, timeline toggle) | `frontend/src/lib/components/charts/drawing-toolbar.svelte` |
| Chart settings modal (fib levels/width, wave settings, hide labels) | `frontend/src/lib/components/charts/chart-settings-modal.svelte` |
| Drawing-tool plugins | `frontend/src/lib/components/charts/plugins/` |
| Shared plugin plumbing | `frontend/src/lib/components/charts/plugins/helpers/` |
| Finance math | `frontend/src/lib/utils/finance/` |
| Indicator defaults | `frontend/src/lib/chart/indicator-defaults.ts` |
| Preference helpers | `frontend/src/lib/chart-preferences.ts` |
| Snapshot API client | `frontend/src/lib/api/snapshotsService.ts` |

`+page.server.ts` loads the security and always fetches a **1d** price window (via `getChartDateWindow(new Date(), '1d')`); the page then reconciles the displayed timeframe with the user's saved preference and force-refetches when they differ. The chart component is dynamically imported inside the page's load effect (`await import('$lib/components/charts/security-chart.svelte')`), so the chart bundle is only ever fetched in the browser rather than during SSR.

## security-chart.svelte data flow

### Props and ownership

The component receives candles and drawing model state as props and reports user intent back through callbacks:

- Core: `candles`, `containerId`, `hasMoreData`, `isLoadingMore` (bindable), `onLoadMoreData`, `hideLabels`, `averagePrice`/`showAveragePrice`, `futureBars`.
- Alerts: `alerts`, `onAddAlert(price, condition)`, `onRemoveAlert(id)`.
- Elliott Wave: `elliottWaves`, `activeDegree`, `activeWaveType`, `isDrawingWave`, `selectedWaveDegree` (bindable), `snapToWicks`, `onWaveChange`, `onDrawingModeChange`, `onDegreeChange`, `onWaveTypeChange`, `onWaveSelect`.
- Fibonacci: `fibonacciTools`, `activeFibTool`, `isDrawingFib`, `selectedFibTool` (bindable), `onFibChange`, `onFibDrawingModeChange`, `onFibToolChange`, `onFibSelect`, `onFibDoubleClick`.

The component owns none of this persistently: it converts props into primitive calls and emits changes upward, where the page persists them to user preferences. Prop→primitive syncing happens in **guarded `$effect`s** that first compare the primitive's current value (e.g. `areSecurityElliottWavesEqual`, `areFibonacciToolsEqual`) so no update loop forms between prop and primitive.

### Mount, series and primitive wiring

`onMount` creates the chart with `CrosshairMode.Normal`, transparent layout, `formatLocalTime` as the time formatter, `formatLocalTickMark` as the tick-mark formatter, `ignoreWhitespaceIndices: false`, a hidden left price scale and a right price scale with `minimumWidth: 75`. It then:

1. Adds the main `CandlestickSeries`.
2. Subscribes `timeScale().subscribeVisibleLogicalRangeChange` for two duties: pagination (`range.from <= 10 && hasMoreData && !isLoadingMore` → `isLoadingMore = true` + `onLoadMoreData()`) and future-whitespace expansion.
3. Attaches three primitives to the candlestick series: `UserPriceAlerts`, `ElliottWavesPrimitive`, `FibonacciPrimitive`.
4. Subscribes each primitive's delegates and re-emits them as page callbacks (`wavePointsChanged`, `drawingModeChanged`, `degreeChanged`, `waveTypeChanged`, `selectionChanged`, `drawingsChanged`, `toolChanged`, `doubleClicked`).
5. Installs a capture-phase `wheel` listener that zooms the **price scale** (not the time scale) by 1.025/0.975 around its mid-point when the pointer is over the price-scale strip, and a `ResizeObserver` that resizes the chart to the container.

The `onMount` teardown destroys the primitives and removes the chart:

```ts
return () => {
    container.removeEventListener('wheel', handleWheel, { capture: true });
    resizeObserver.disconnect();
    userAlertsPrimitive?.destroy();
    elliottWavesPrimitive?.destroy();
    fibonacciPrimitive?.destroy();
    chartInstance?.remove();
};
```

Drawing mode disables chart panning globally: an `$effect` sets `handleScroll.pressedMouseMove = false` while `isDrawingWave || isDrawingFib`, and each primitive restores it when its drawing mode ends. This is the component-level counterpart of the scroll lock that `ChartMouseHandlers` applies during point drags.

### Candle updates, prepending and future whitespace

The candles `$effect` is the single writer for series data:

- Same array reference → no-op (the page replaces the array when data changes, which is the change signal).
- Empty candles → clear series and both primitives, reset whitespace count to `futureBars`, reset `isLoadingMore`.
- **Prepending** (first candle older than the previously-seen first candle, e.g. infinite-scroll history) → set data, then shift the visible logical range by the number of prepended candles so the viewport does not jump.
- **First load** → size `currentWhitespaceCount` from `futureBars` and container width, then show the last 250 bars.

Future whitespace is what makes it possible to draw *ahead* of the last candle. `generateFutureWhitespace(candles, count)` derives the bar interval from the median spacing of the most recent candles (`computeIntervalSeconds`) and appends `count` whitespace points one interval apart, preserving the reference candle's `Time` shape (epoch seconds vs. `YYYY-MM-DD` vs. `BusinessDay`). `checkAndExpandWhitespace` grows the count when the visible logical range approaches the right edge, or when the container is wide enough to need more bars than currently allocated, and re-applies the saved logical range so the expansion is invisible to the user.

### Two-pane layout (oscillator panes)

Oscillators do not get separate lightweight-charts panes; they get separate **price scale ids** on the same pane, and the vertical space is carved out with `scaleMargins` in `updatePanes()`:

- `OSCILLATOR_ORDER = ['rsi', 'macd', 'obv']` fixes both the presence check and the top-to-bottom stacking order.
- Pane height per oscillator: `0.25` (one), `0.18` (two), `0.14` (three), with a `0.02` gap; the main area keeps at least `0.3`.
- When `volume` is enabled it is allocated the bottom 25% of the main area; the candlestick price scale is squeezed accordingly.
- With no oscillators, the chart uses symmetric or volume-aware margins.

`bb` (Bollinger Bands) is an *overlay*, not an oscillator: it is drawn on the main price scale and never calls `updatePanes()`.

### Imperative surface

The component exports functions consumed through `bind:this` from the page:

| Export | Purpose |
|---|---|
| `updateData(candles)` | Replace series data and reset the visible window |
| `addIndicator` / `updateIndicatorData` / `removeIndicator` | Add, refresh or drop an indicator series group |
| `clearWave`, `getSelectedWaveDegree`, `setSelectedWaveDegree`, `getSelectedWaveId`, `setSelectedWaveId`, `getAllWaves`, `getElliottWavesPrimitive` | Elliott Wave proxy API |
| `clearFibonacci`, `getSelectedFibTool`, `setSelectedFibTool`, `getFibonacciPrimitive` | Fibonacci proxy API |

## Chart preferences and interval handling

`frontend/src/lib/chart-preferences.ts` holds the pure helpers the security page uses; they are unit-tested by the page's own test suite:

- `mergeChartPreferences(prefs, partial)` — read-merge-write that **preserves the `indicators` key** so a chart-style or timeframe patch cannot clobber indicator settings.
- `displayCandlesFor(style, raw, ha)` — `heikin_ashi` → Heikin-Ashi candles, otherwise raw candles.
- `shouldForceRefetch(selectedInterval, interval, force)` — `true` when `force` is set or the interval differs.
- `parseCandleTime(time)` — normalizes number (epoch seconds), `YYYY-MM-DD`, ISO string and `BusinessDay` to a `Date`.
- `mergeCandles(existing, incoming)` — dedupes by `String(time)` and prepends the new candles so the array stays oldest→newest.
- `shouldFetchMoreData(isLoadingMore, hasMoreData, securityId, candleCount)` — pagination guard.

Intervals supported by the toolbar are `1h`, `4h`, `1d`, `1w`, `1m`. `getChartDateWindow(endDate, interval)` returns a 30-day window for intraday intervals and a 2-year window otherwise; intraday points are mapped to `UTCTimestamp` epoch seconds and daily/weekly/monthly points keep their date string. `changeTimeframe` fetches through `MarketService.getPrices`, maps/sorts candles, recomputes Heikin-Ashi candles and refreshes indicators; the preference patch is deliberately performed **outside** the fetch `try/catch` so a failed preference save cannot mask a fetch error.

Preferences are stored via `UserPreferencesService` (`timeframe`, `chart_style`, `indicators`, `chart_hide_labels`, `wave_settings`, `elliott_waves`, `fibonacci_tools`) and applied on load by `onPreferencesLoaded`, which sets the chart style, applies the saved timeframe without re-persisting it, and re-enables indicators via a `setTimeout(…, 100)` so the chart ref is bound first.

## Indicators and overlays

`frontend/src/lib/chart/indicator-defaults.ts` is the single source of truth for indicator defaults (`INDICATOR_DEFAULTS`, key order = sidebar render order), deep-frozen so accidental mutation throws. `createIndicatorConfigs()` returns a fully independent copy (including nested `settings`) for the page to mutate.

`addIndicator(indicator)` switches on `indicator.type` and builds the right series shape:

| Type | Series composition | Price scale |
|---|---|---|
| `volume` | one `HistogramSeries`, `priceFormat: { type: 'volume' }` | `volume` |
| `rsi` | one `LineSeries` | `rsi` |
| `macd` | `HistogramSeries` + MACD `LineSeries` + signal `LineSeries`, histogram colored per sign | `macd` |
| `obv` | one `LineSeries` with a custom `M/1M` price formatter | `obv` |
| `bb` | three `LineSeries` (upper/middle/lower) + a `BandsIndicator` primitive attached to `middle` | main |
| everything else (`ma50`, `ma200`, `ma50w`, `ma200w`, …) | one `LineSeries` overlay | main |

`removeIndicator` removes all series of the group and, for `bb`, detaches the bands primitive first. `updateIndicatorData` either updates `setData` for the affected series or falls back to `addIndicator` when the group does not exist yet.

Actual indicator values are computed server-side by `IndicatorsService.computeIndicators` (`{ interval, chart_style, indicators: IndicatorSpec[], candles? }`). The page keeps a monotonic `sequenceCounter` plus a per-indicator `indicatorSeq` map and discards responses whose sequence is stale — the standard guard against out-of-order responses when the user toggles indicators quickly or changes timeframe mid-flight. `volume` is the exception: it is rendered locally from the displayed candles. `avgPrice` is not an indicator series at all — it is a dashed price line created/removed from `averagePrice` + `showAveragePrice`, fed by `blendedAverageCost(holdings)`.

`hideLabels` is a display mode that drives `lastValueVisible`/`priceLineVisible`/`title` across every series group (including the three MACD series and the three BB series) through a single `$effect`.

## The drawing-tool plugin architecture

### Per-plugin layout

Each drawing tool lives in `frontend/src/lib/components/charts/plugins/<plugin-name>/` with a fixed responsibility split:

| File | Responsibility |
|---|---|
| `state.ts` | Tool state, point arrays, active mode, selection, hover/drag targets; fires `Delegate` events. Pure domain data — never touches DOM or chart coordinates. |
| `mouse.ts` | Thin adapter extending `ChartMouseHandlers`; supplies `hitTestRadius`, `toTarget`, optional `adjustPosition` snapping and `hitTestLine`. |
| `pane-renderer.ts` | Implements `IPrimitivePaneRenderer`; draws shapes, handles, dashed previews and labels into bitmap coordinate space. |
| `pane-view.ts` | Implements `IUpdatablePaneView<TRendererData>`; stores renderer data and returns the renderer with a `zOrder`. |
| `constants.ts` | Visual constants: radii, hit-test radii, line widths/dashes, colors, opacity, degree configuration. |
| `index.ts` | Barrel exporting the primitive, state, renderer, view, mouse adapter and public types/constants. |

Two rules make the structure hold:

- **No cross-plugin imports.** `fibonacci` must never import from `elliott-wave` or vice versa. Anything shared moves to `plugins/helpers/` or `$lib/utils/finance/`. The elliott-wave barrel, for example, re-exports `TimeProjector`, the time helpers and the snap helpers from `../helpers/...` — never from a sibling plugin.
- **Finance math and pattern validation live in `$lib/utils/finance/`.** Plugins import formulas (`calculateRetracementLevels`, `selectDegreeWave`, `snapPriceToWick` call sites, …) but never embed them in renderers, views or mouse adapters.

```mermaid
flowchart LR
    SEC["security-chart.svelte"] --> PRIM["Primitive extends DrawingPrimitiveBase"]
    PRIM --> STATE["state.ts holds points, mode, selection, hover and drag"]
    PRIM --> MOUSE["mouse.ts adapter over ChartMouseHandlers"]
    PRIM --> VIEW["pane-view.ts stores renderer data and zOrder"]
    VIEW --> RENDER["pane-renderer.ts draws into bitmap coordinate space"]
    STATE -->|"delegate events"| PRIM
    MOUSE -->|"hit test, click, drag, cancel"| PRIM
    PRIM -->|"setProjectedPoints and setProjectedLines"| MOUSE
    FIN["utils/finance formulas and validation"] --> PRIM
```

The plugin layer split: a primitive owns state, a mouse adapter, a pane view and a renderer; shared plumbing comes from `helpers/` and all math from `utils/finance`.

### Fibonacci

`FibonacciToolState` manages a `retracement` (2 anchors) and an `extension` (3 anchors) drawing plus `_pendingPoints`. `addPoint` implements the click progression: two clicks complete a retracement, three complete an extension; on completion it stores the drawing, clears pending points and exits drawing mode. `updatePoint` supports per-index drag updates, `clear(tool?)` clears one or both tools, and every mutation fires `drawingsChanged` with a defensively copied `SecurityFibonacciTools`. Selection (`setSelectedTool`) is cleared automatically when the selected tool's drawing is removed or hidden.

The plugin's `MouseHandlers` extends `ChartMouseHandlers` with `hitTestRadius: HIT_TEST_RADIUS` (14 px), maps hits to `{ tool, pointIndex }`, adds line hit-testing against projected level lines (distance to the clamped x-range), and snaps placed points to candle wicks via `adjustPosition` when a candle lookup exists. `FibonacciPrimitive` wires the shared delegates in `_setupSubscriptions`, computes projected points/levels in `_calculateRendererData` using `TimeProjector` + `series.priceToCoordinate`, and exposes `doubleClicked()` which the page turns into the fib width modal. Line bounds come from pure functions (`calculateRetracementLineBounds`, `calculateExtensionLineBounds`) with a minimum width delta so short drawings stay clickable.

### Elliott Wave

`ElliottWaveState` holds degree (`cycle` | `primary` | `intermediate`), wave type (`impulse` | `corrective`), the `DegreeWaveCount[]` collection, the in-progress wave id, selection and hover/drag targets. Highlights:

- `addPoint` creates a new wave with a `generateUUID()` id when needed, assigns the next wave label (`0..5` for impulse, `[0, 'A', 'B', 'C']` for corrective), records `wave3Target`/`wave5Target` when points 3 and 5 are placed, and exits drawing mode once `MAX_IMPULSE_POINTS` (6) or `MAX_CORRECTIVE_POINTS` (4) is reached.
- `updatePoint` locates the wave by id → selected wave → degree, mutates an immutable copy, and keeps `wave3Target`/`wave5Target` in sync when point 3 or 5 moves.
- `clearWave(waveIdOrDegree?)` removes the selected wave, the wave with that id, the latest wave of a degree, or the last wave overall.
- Changes fire `wavePointsChanged`, which the chart re-emits so the page persists `elliott_waves[securityId]` and reconciles wave target alerts.

The plugin's `constants.ts` defines per-degree visual configuration (`CYCLE_STYLE`, `PRIMARY_STYLE`, `INTERMEDIATE_STYLE`, `DEGREE_STYLES`) including the Roman-numeral / circled-number / parenthesised label conventions, node radii and ring colors. The mouse adapter snaps through `resolveAdjustedPosition`: it builds a candle-wick candidate (only when `snapToWicks` is on) and a Fibonacci-level candidate (only when the nearest active level is within `FIB_SNAP_TOLERANCE_PX` = 8 px, independent of `snapToWicks`), then returns the closer one with pixel-space ties going to the wick.

### Cross-plugin coupling goes through the finance layer

Elliott wave points snap to active Fibonacci levels, but the elliott plugin cannot import the fibonacci plugin. The page computes the level prices from the pure finance helper and pushes them in:

```ts
const fibSnapPrices = $derived(getActiveFibLevelPrices(fibonacciTools));
// …in a content-signature-guarded $effect:
elliottWavesPrimitive.setFibLevelPrices(fibSnapPrices);
```

`getActiveFibLevelPrices` returns the deduplicated prices of every enabled level of the currently drawn, visible retracement and extension tools. The signature guard (`"${length}:${values}"`) exists because the derived array is fresh on every tools change.

## Shared plumbing in `plugins/helpers/`

### `helpers/delegate.ts`

`Delegate<T1>` + `ISubscription<T1>` implement a type-safe publisher/subscriber surface used by every state class and the mouse handlers: `subscribe(callback, linkedObject?, singleshot?)`, `unsubscribe(callback)`, `unsubscribeAll(linkedObject)`, `fire(param)`, `hasListeners()` and `destroy()`. Two semantics matter:

- `linkedObject` is the ownership handle: primitives pass `this` and later call `unsubscribeAll(this)`, which is what makes cleanup exhaustive instead of best-effort.
- `single-shot` listeners are removed before the callback runs, and `fire` iterates a snapshot of the listener list so a callback that subscribes or unsubscribes during dispatch cannot corrupt the loop.

### `helpers/dimensions/`

`positionsLine(positionMedia, pixelRatio, desiredWidthMedia, widthIsBitmap?)` returns `{ position, length }` in bitmap pixels, rounding the scaled position and centering the line width on it. `positionsBox(position1Media, position2Media, pixelRatio)` returns the box start and a length of `abs(delta) + 1` (the +1 keeps a 1 px box visible). These are the shared primitives for crisp, pixel-aligned drawing; the `user-price-alerts` renderers use `positionsLine` for alert lines, the centre label, its divider and the price-scale label. `fibonacci` and `elliott-wave` renderers also draw inside the bitmap scope and scale media coordinates by the scope's `horizontalPixelRatio`/`verticalPixelRatio` themselves. `BitmapPositionLength` comes from `dimensions/common.ts`.

**Rule for new canvas code**: never draw with raw media coordinates — work inside `target.useBitmapCoordinateSpace(...)` and derive pixel-snapped geometry with `positionsLine`/`positionsBox` so 1 px lines and handles stay crisp on high-DPI displays.

### `helpers/time/`

- `time.ts`: `DEFAULT_FUTURE_BARS = 100`, `timeToEpochSeconds` / `epochSecondsToTime` (shape-preserving round trip), `addIntervalToTime`, `barsBetweenTimes`, `computeIntervalSeconds`, `generateFutureWhitespace`.
- `time-projector.ts`: `TimeProjector` binds to the chart (`attach`) and to the data (`updateCandles`), then projects coordinates ↔ time. Inside the historical range it delegates to `timeScale().timeToCoordinate` / `coordinateToTime`; beyond the last candle it extrapolates from the last time plus whole bar intervals and maps them via logical bar indices. This is what lets wave points and fib anchors live in the future whitespace.

### `helpers/mouse/`

`ChartMouseHandlers<TPoint, TTarget, TOriginal>` is the shared interaction engine:

- **Config**: `hitTestRadius`, `toTarget(point)`, optional `adjustPosition(pos, series)` and `hitTestLine(x, y)`.
- **DOM lifecycle**: mousemove/mousedown/mouseup/click/dblclick/mouseleave/contextmenu on the chart element, plus window-level `mouseup` and `keydown`, all unsubscribed in `detached()`.
- **Plot-area clipping**: `_determineMousePosition` subtracts the price-scale width and time-scale height, so points outside the plot area carry `time: null` / `price: null` and are never turned into placements.
- **Hit-testing contract**: distance ≤ `hitTestRadius` is a hit (boundary inclusive) and exact-distance ties resolve first-wins by array order, so overlapping anchors are deterministic.
- **Drag lifecycle**: mousedown on a hit starts a drag, disables `pressedMouseMove` scroll and fires `dragStarted`; moves fire `pointDragged` with the adjusted position; any drag move sets `_dragHappened`, which suppresses the trailing `click` and `dblclick` so a drag never also places or selects a point; mouseup (chart **or** window) restores scroll and fires `dragEnded`.
- **Drawing mode**: `setDrawingMode(true)` disables pressed-move scroll and hides the horizontal crosshair line; clicks inside the plot area fire `chartClicked` with the (optionally snapped) time/price/x/y.
- **Cancellation**: right-click (`contextmenu`) and `Escape` fire `cancelRequested` while in drawing mode.

`helpers/mouse/snap.ts` provides the pure snapping helpers: `snapPriceToWick(price, candle)` (ties resolve to `high`), `findNearestLevel(price, levelPrices)` (finite-value filtering; pixel tolerance stays the caller's job), `buildCandleLookup(candles)` and `findCandleByTime(lookup, time)` (O(1) lookup keyed by normalized epoch seconds).

### `helpers/primitive/drawing-primitive-base.ts`

`DrawingPrimitiveBase<TRendererData, TPaneView, TState, TMouseHandlers, THoverTarget, TDragTarget>` is the abstract base that implements `ISeriesPrimitive<Time>`. It defines three contract interfaces plugins must satisfy (`IDrawingToolState`, `IUpdatablePaneView`, `IDrawingMouseHandlers`) and centralizes lifecycle, subscription tracking, cursor resolution and pane-view updates. Subclasses supply `_calculateRendererData()` and optionally extend `_setupSubscriptions()`.

Cursor resolution precedence in `_updateCursor()`: dragging → `'default'`, drawing mode → `'crosshair'`, hovering a point → `'default'`, otherwise `null`. `hitTest()` returns `null` for a `null` cursor, otherwise `{ cursorStyle, externalId, zOrder: 'top' }` — the `externalId` is what lightweight-charts reports back to the page's own hit testing.

```mermaid
stateDiagram-v2
    [*] --> Constructed
    Constructed --> Attached: attached with chart, series and requestUpdate
    Attached --> Attached: updateAllViews calculates renderer data and updates cursor
    Attached --> Attached: delegate events call requestUpdate
    Attached --> Detached: detached unsubscribes tracked subscriptions
    Detached --> Detached: updateAllViews passes null to the pane view
    Attached --> Destroyed: destroy detaches then destroys state
    Detached --> Destroyed: destroy detaches then destroys state
    Destroyed --> [*]
```

Drawing primitive lifecycle: `attached` binds the projector and mouse handlers and tracks subscriptions; `detached` releases everything; `destroy` runs `detached()` and then destroys the state delegates. `updateAllViews` is safe to call in any state.

`attached({ chart, series, requestUpdate })` stores the references, attaches the `TimeProjector` and `ChartMouseHandlers`, pushes the current drawing mode into the mouse handlers, then wires the standard delegates:

| Delegate | Reaction |
|---|---|
| `state.drawingModeChanged()` | push mode into mouse handlers + request update |
| `mouseHandlers.mouseMoved()` | request update (drives previews) |
| `mouseHandlers.pointHovered()` | `state.setHoveredPoint(...)` + update |
| `mouseHandlers.dragStarted()` / `dragEnded()` | set/clear `state.setDraggingPoint(...)` + update |
| `mouseHandlers.chartClicked()` | in drawing mode, `state.addPoint({ time, price })` + update |
| `mouseHandlers.cancelRequested()` | `cancelDrawing()` (state hook, or clear the mode) |

Every subscription goes through `_subscribe()` / `_subscribeToUpdate()` and is recorded in `_trackedSubscriptions`; `detached()` iterates that set calling `sub.unsubscribeAll(this)`, then calls `mouseHandlers.detached()` and clears `_chart` / `_series` / `_requestUpdate`. `updateAllViews()` early-returns into `paneView.update(null)` when the primitive is detached or references are missing, otherwise it computes renderer data, updates the cursor and pushes data into the pane view. `setCandles(candles)` updates the `TimeProjector` and requests an update; primitives that also snap (`FibonacciPrimitive`) override it to forward candles to their mouse adapter too.

## The finance-math boundary

All formulas and pattern validation live in `frontend/src/lib/utils/finance/` with colocated unit tests. Plugins consume them; they never re-implement them.

| Module | Contents |
|---|---|
| `fibonacci.ts` | `FibToolType`/`FibPoint`/`FibRetracementDrawing`/`FibExtensionDrawing`/`SecurityFibonacciTools` types, `DEFAULT_FIB_RETRACEMENT_LEVELS` / `DEFAULT_FIB_EXTENSION_LEVELS`, `FIB_WIDTH_STOPS`, `getClosestFibWidthIndex`, `formatFibLevelLabel`, `calculateRetracementLevels`, `calculateExtensionLevels`, `getActiveFibLevelPrices`, `updateSecurityFibonacciTools`, `getSecurityFibonacciTools`, structural-equality helpers |
| `elliott-wave.ts` | `WaveDegree`, `WaveType`, `WavePointId`, `WavePoint`, `DegreeWaveCount`, `SecurityElliottWaves`, `WaveSettings`/`WaveAlertPercents`, `DEFAULT_WAVE_SETTINGS`, `getWaveTargetPrice`, `calculateUpsidePercentage`, `selectDegreeWave`, `getSecurityDegreeWaveCount`, `getLatestWaveCount`, `updateSecurityElliottWaves`, `normalizeWaveIds`, `getWaveAlertPercent`, equality helpers |
| `wave-alerts.ts` | `roundTo8dp`, `computeWaveAlertLevels`, `reconcileWaveAlerts` |
| `bollinger-bands.ts`, `moving-average.ts`, `rsi.ts`, `macd.ts`, `obv.ts` | Indicator config types + defaults (`defaultBBConfig` 20/2, `defaultRSIConfig` 14, `defaultMACDConfig` 12/26/9, `defaultOBVConfig`) and value/series types |
| `holdings-metrics.ts` | `parseCandleTimeToDate`, `getPeriodCutoffDate`, `getBenchmarkPrice`, `calculateHoldingGain`, `filterCandlesForPeriod` |
| `average-cost.ts` | `blendedAverageCost` (quantity-weighted, 0 for empty/zero-quantity holdings) |
| `candle.ts` | `Candle` type + `convertToHeikinAshi` |
| `rewind.ts` | Snapshot model + persistence helpers (see below) |

Wave alert math is a good illustration of why this boundary exists: `computeWaveAlertLevels` iterates degree × target wave deterministically, skips a degree whose percent is `null`, rounds to 8 decimals to match the backend `DECIMAL(16,8)` column so create→read-back comparisons are exact, and skips levels equal to the current price. `reconcileWaveAlerts` then diffs desired levels against existing alerts by `(condition, level)` and returns exactly which alerts to create and which wave-source alerts to delete — manual alerts (`source !== 'wave'`) are never returned for deletion, and a second run over fully-applied state returns empty sets.

Two practical notes for this boundary:

- `generateUUID()` (used for wave ids and client-side snapshot ids) lives in `finance/rewind.ts` and is imported by the elliott-wave plugin. It falls back from `crypto.randomUUID` to `crypto.getRandomValues` to `Math.random`, because non-secure HTTP contexts lack `randomUUID`.
- The dependency direction is one-way: `$lib/utils/finance/` is the lowest layer and must not import from `plugins/helpers/`. That is why `elliott-wave.ts` duplicates the epoch-seconds conversion privately (`waveTimeToEpochSeconds`) instead of importing the plugin helper — do not "fix" that duplication by adding the import.
- The page reconciles wave alerts through a **serialized promise chain** (`waveAlertsReconcileSeq`), because `onWaveChange` fires once per placed point and concurrent reconciles reading stale `alerts` state would double-create. A failed reconcile only logs — the next reconcile self-heals.

## Chart snapshots and the rewind timeline

A chart snapshot captures the drawings plus the data window at a moment in time; the rewind timeline lets the user scrub back to that moment and see the chart as it was. The pipeline spans backend storage, a finance helper module, an API client, a timeline helper module, the timeline component and the security page.

### Backend persistence

`ChartSnapshotModel` (`src/market/model.py`) maps to `market_chart_snapshots`:

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` PK | server-generated (`uuid4`) |
| `security_id` | `UUID` FK → `market_securities.id` | `ON DELETE CASCADE` |
| `user_id` | `UUID` | ownership scope for every query |
| `drawings` | `JSON` | elliott waves + fibonacci tools payload |
| `data_window` | `JSON` | `{ first, last }` displayed candle times |
| `captured_at` | `DateTime(timezone=True)` | client-supplied or `now(UTC)` |
| `created_at` | `DateTime(timezone=True)` | server default |

A composite index `ix_market_chart_snapshots_security_user_captured` on `(security_id, user_id, captured_at)` backs the read path. The table is created by migration `bea77d72aaf1_add_market_chart_snapshots`.

`ChartSnapshotRepository` (abstract, `src/market/repository.py`) exposes `get_by_security_and_user`, `create` and `delete`; `SqlAlchemyChartSnapshotRepository` implements them:

- Read: `SELECT … WHERE security_id = ? AND user_id = ? ORDER BY captured_at ASC` → `list[ChartSnapshotRead]`. **Ascending order is part of the contract** — the frontend timeline treats `snapshots[0]` as the oldest.
- Create: normalizes `captured_at` to UTC (attaching UTC when naive), inserts, refreshes and returns `ChartSnapshotRead`.
- Delete: `DELETE … WHERE id = ? AND user_id = ?` — a snapshot can only be deleted by its owner.

The repository is registered as a `svcs` factory (`ChartSnapshotRepository` → `sqlalchemy_chart_snapshot_repository_factory` in `src/market/__init__.py`) and exposed by `src/market/router.py`:

| Method | Path (router prefix `/market`, mounted under `/api/v1`) | Response |
|---|---|---|
| `GET` | `/market/securities/{security_id}/snapshots` | `list[ChartSnapshotRead]` for the current user |
| `POST` | `/market/securities/{security_id}/snapshots` | `201` + created `ChartSnapshotRead` |
| `DELETE` | `/market/securities/{security_id}/snapshots/{snapshot_id}` | `204` |

`ChartSnapshotCreate` accepts `drawings`, `data_window` and optional `captured_at`; `ChartSnapshotRead` adds `id`, `security_id`, `user_id`, `captured_at` and `created_at`. All three routes depend on `current_user`, and the `user_id` scope is applied in the repository rather than in the handler.

### Frontend snapshot helpers and API client

`frontend/src/lib/utils/finance/rewind.ts` defines the wire model and the pure snapshot algebra:

- `RewindSnapshot` = `{ id, captured_at, drawings, data_window, security_id?, user_id?, created_at? }`; `RewindDrawings` = `{ elliott_waves?, fibonacci_tools? }`; `RewindDataWindow` = `{ first, last }` holding `getTimeValue`-normalized candle times.
- `captureSnapshot(drawings, dataWindow, now = new Date())` builds a client-side id (`generateUUID()`) and an ISO-8601 UTC `captured_at`.
- `appendSnapshot(store, securityId, snapshot)` immutably appends to a per-security map (returns a new record, tolerates `null`/missing keys). Kept for map-shaped stores; the security page currently holds a flat per-security array and spreads instead.
- `getSnapshots(store, securityId)` returns an ascending-by-`captured_at` copy.
- `findSnapshotAtOrBefore(snapshots | store, time)` returns the latest snapshot at or before `time`, or `null` when `time` precedes the first snapshot; it is overloaded for a flat array (2-arg) and for the map + security id (3-arg) forms. The page uses the 2-arg array form.
- `areSnapshotsEqual(a, b)` compares `data_window` plus drawings structurally and **intentionally ignores `id` and `captured_at`** — that is what gives save-dedupe semantics. Normalization treats "no fibonacci tools" and "empty fibonacci tools" as equal.

`frontend/src/lib/api/snapshotsService.ts` is a thin `ApiClient` subclass with `getSnapshots(securityId, token?)`, `createSnapshot(securityId, { drawings, data_window, captured_at? }, token?)` and `deleteSnapshot(securityId, snapshotId, token?)`, plus the conventional factory (`getSnapshotsService(customFetch?)`) and singleton (`snapshotsService`). Requests hit `/api/v1/market/securities/{id}/snapshots` with `credentials: 'include'` and throw `ApiError` on non-OK responses.

`deleteSnapshot` and the backend `DELETE` route are implemented and unit-tested, but the security page does not call them yet — deleting snapshots is an existing extension point, not a missing endpoint.

### Timeline helpers and component

`frontend/src/lib/components/charts/rewind-timeline.ts` (the pure module next to the component, not `$lib/utils/finance/rewind.ts`) holds the timeline geometry:

- `sliceCandlesBefore(candles, cutoff)` filters candles to `time <= cutoff` using `parseCandleTime`, and **returns the original array** when the cutoff is `null` or invalid (so "not rewound" is a no-op).
- `snapshotTimelineDomain(snapshots, now)` returns `{ first, last }` in epoch ms: `first` = `Date.parse(snapshots[0].captured_at)` (falling back to `now`), `last` = `now`, with `last = first + 1` when `last <= first` or `now` is invalid — so a single snapshot (or "now" at the same instant) still yields a non-degenerate domain.
- `timeToFraction(t, first, last)` and `fractionToTime(f, first, last)` map between time and a clamped `[0, 1]` fraction; a degenerate domain yields fraction `0`.

`rewind-timeline.svelte` renders the track, one marker button per snapshot (positioned by `timeToFraction(Date.parse(snapshot.captured_at), …)`), the playhead (`timeToFraction(position ?? now)`) and the "Back to now" / "Now" affordances, or a "No rewind snapshots yet" empty state. Scrubbing uses pointer events with `setPointerCapture`; `updatePositionFromPointer` computes a clamped fraction from the track rect and **sets `position = null` when the fraction is ≥ 0.995**, which is how dragging to the right edge returns to live data. A window-level `pointerup`/`pointercancel` handler ends a drag that finishes outside the track. `position` is `$bindable`, and `onScrub` is an optional callback the security page does not currently use.

### Page orchestration and rewind semantics

The page owns the rewind state and derives everything else from it:

```ts
let timelinePosition = $state<Date | null>(null);
let isRewound = $derived(timelinePosition !== null);
let displayCandles = $derived(
    isRewound ? sliceCandlesBefore(allDisplayCandles, timelinePosition) : allDisplayCandles
);
let activeSnapshot = $derived(
    isRewound && security?.id && timelinePosition
        ? findSnapshotAtOrBefore(securitySnapshots, timelinePosition)
        : null
);
let effectiveElliottWaves = $derived(
    isRewound ? (activeSnapshot?.drawings?.elliott_waves ?? { waves: [] }) : securityElliottWaves
);
let effectiveFibonacciTools = $derived(
    isRewound ? (activeSnapshot?.drawings?.fibonacci_tools ?? {}) : securityFibonacciTools
);
```

Rewind is a strictly read-only mode. While `isRewound`:

- `isDrawingWave` / `isDrawingFib` are passed to the chart as `false`, so drawing modes are off.
- Every mutation handler early-returns: `handleWaveChange`, `handleClearWave`, `handleFibChange`, `handleClearFib`, `handleFibLevelsChange`, `handleFibWidthSave`, `handleSaveSnapshot`, `handleLoadMoreData` and `scheduleWaveAlertsReconcile`.
- The chart gets `hasMoreData={!isRewound && hasMoreData}` so no history is fetched.
- Indicators are recomputed against the sliced candles: `getRewoundCandlesPayload()` builds an `IndicatorCandle[]` from `sliceCandlesBefore(rawCandles, timelinePosition)` and passes it to `IndicatorsService.computeIndicators`, so an oscillator shows the values it would have had at that instant.
- The chart's drawings are driven by `effectiveElliottWaves` / `effectiveFibonacciTools`, i.e. the snapshot's drawings, not the live preferences.

`timelineNow` is the timestamp of the last **displayed** candle (`parseCandleTime(allDisplayCandles.at(-1).time)`), not wall-clock time, so the "Now" end of the track lines up with the newest bar. The timeline is hidden behind `isTimelineVisible` (toolbar toggle) and is revealed automatically when snapshots exist or a new one is saved.

### Saving a snapshot

`handleSaveSnapshot` (toolbar "Save snapshot" button, or Cmd/Ctrl+S):

1. Bail out when rewound, without a security id, or without displayed candles.
2. Build `drawings` from the live `securityElliottWaves` + `securityFibonacciTools`, and skip the save silently unless there is at least one wave point or one fib tool.
3. Build `data_window` from the first/last displayed candle times (`normalizeCandleTime` converts a `Time` to a string/number).
4. `captureSnapshot(...)`, then compare with the newest stored snapshot via `areSnapshotsEqual` — if equal, show "Chart snapshot already up to date" (`toast.info`) and do not POST. `showSaveFeedback()` flips the toolbar icon to a check mark for 1.5 s.
5. Otherwise `snapshotsService.createSnapshot(security.id, { drawings, data_window, captured_at })`, append the **server-returned** snapshot to `securitySnapshots`, reveal the timeline and show "Chart snapshot saved". Failures log and show an error toast without touching the timeline.

`loadSnapshots()` runs on page load alongside alerts and holdings, and sets `isTimelineVisible = true` when the security already has snapshots.

```mermaid
flowchart TD
    LOAD["Page load calls loadSnapshots"] --> STORE["securitySnapshots populated, timeline revealed when non-empty"]
    SAVE["Toolbar Save snapshot or Cmd plus S"] --> GUARD{"rewound, missing candles or no drawings"}
    GUARD -- "yes" --> SKIP["Save skipped"]
    GUARD -- "no" --> CAP["captureSnapshot builds id, captured_at, drawings, data_window"]
    CAP --> DEDUPE{"areSnapshotsEqual with newest stored snapshot"}
    DEDUPE -- "equal" --> INFO["toast already up to date, no POST"]
    DEDUPE -- "different" --> POST["snapshotsService.createSnapshot POST"]
    POST --> APPEND["Append server snapshot and show the timeline"]
    STORE --> TIMELINE["RewindTimeline renders markers from snapshotTimelineDomain"]
    APPEND --> TIMELINE
    TIMELINE --> SCRUB["User drags the playhead or clicks a marker"]
    SCRUB --> POSITION["position becomes a Date, or null near the right edge"]
    POSITION --> SLICE["displayCandles sliced with sliceCandlesBefore"]
    SLICE --> DRAWINGS["activeSnapshot drawings drive the primitives"]
    SLICE --> INDICATORS["Indicators recomputed from the sliced candles"]
    POSITION --> RESET["position null restores live candles, live drawings and pagination"]
```

Snapshot → rewind flow: saving persists drawings plus the data window, and scrubbing the timeline re-derives candles, drawings and indicators from the snapshot at or before the playhead. A `position` of `null` means live data.

## Price alerts on the chart

### Chart primitives

`frontend/src/lib/components/charts/plugins/user-price-alerts/` renders price alerts as a series primitive. It is deliberately **not** built on `DrawingPrimitiveBase`: it has its own `MouseHandlers` (it needs pointer positions over the price scale, which the shared handler clips away) and both pane views and **price-axis pane views**.

- `UserPriceAlerts.attached` creates one pane view and one price-axis pane view, attaches the mouse handlers and subscribes `alertsChanged` / `mouseMoved` / `clicked` to request updates. A click above the price scale (`xPositionRelativeToPriceScale` within the button width) adds an alert at `series.coordinateToPrice(y)`; a click on a hovered alert's remove button removes it.
- `updateAllViews` computes renderer data once for both renderers, finds the alert closest to the pointer within `showCentreLabelDistance`, and sets `_hoveringID` / `_currentCursor = 'pointer'` when the pointer is over the add button or a remove button. `hitTest()` reports `externalId: 'user-alerts-primitive'`.
- `UserAlertsState` stores alerts in a `Map`, exposes `alertAdded` / `alertRemoved` / `alertChanged` / `alertsChanged` delegates, and keeps a price-descending array view (`_updateAlertsArray`). New alert ids are random 6-digit strings, regenerated on collision.
- Rendering uses `positionsLine` for the alert line, the centre label, its divider and the price-scale label.

The chart component bridges the primitive to the backend: an `$effect` pushes `alerts` into `setAlerts([{ id: String(a.id), price: a.target_price }])`; `alertAdded` derives the condition from the last candle close (`price > close ? 'above' : 'below'`) and calls `onAddAlert`; `alertRemoved` parses the id back to a number and calls `onRemoveAlert`. The page then creates/deletes through `AlertsService` and reloads the alert list.

### Wave-derived alerts

Wave targets produce real price alerts with `source: 'wave'`. `handleWaveChange` and `handleWaveSettingsChange` call `scheduleWaveAlertsReconcile`, which chains `reconcileWaveAlertsForSecurity` onto a single promise; that function reads `wave_settings` (defaulting to `DEFAULT_WAVE_SETTINGS`), computes desired levels with `computeWaveAlertLevels(settings, securityElliottWaves, lastClose)`, diffs them with `reconcileWaveAlerts(alerts, desired)` and applies the deletes/creates in parallel. The initial page load also reconciles, but only after preferences have loaded — a failed preference fetch must never mass-delete wave alerts. On success with any change, `loadAlerts()` refreshes the primitive.

## Testing conventions

Charting tests follow the repository rules in `frontend/AGENTS.md` and [Testing](../operations/testing.md), plus chart-specific requirements:

- **Colocation**: every plugin has a colocated suite (`fibonacci/fibonacci.test.ts`, `elliott-wave/elliott-wave.test.ts`, `user-price-alerts/user-price-alerts.test.ts`, `plugins/bands-indicator.test.ts`), and every shared helper has its own (`helpers/mouse/chart-mouse-handlers.test.ts`, `helpers/primitive/drawing-primitive-base.test.ts`, `helpers/mouse/snap.test.ts`, `helpers/time/time.test.ts`). Components and pure modules for the chart live together too (`security-chart.test.ts`, `rewind-timeline.test.ts`, `drawing-toolbar.test.ts`, `chart-settings-modal.test.ts`, `fib-width-modal.test.ts`), as does the page suite (`routes/security/[security_id]/page.svelte.test.ts`).
- **Mocking is mandatory** — no test may touch a real network or a real chart:
  - `lightweight-charts` is replaced with a `vi.mock` factory exposing `createChart`, `CrosshairMode`, `CandlestickSeries`, `LineSeries`, `HistogramSeries` and chainable `timeScale`/`priceScale`/`addSeries`/`attachPrimitive` mocks (`security-chart.test.ts` also stubs `Path2D` and `ResizeObserver` before importing).
  - Canvas targets are faked: `useBitmapCoordinateSpace` invokes the callback with a fake `BitmapCoordinatesRenderingScope` (context, media/bitmap sizes, `horizontalPixelRatio`/`verticalPixelRatio`), and the 2D context is a recording double of `moveTo`/`lineTo`/`arc`/`fill`/`stroke`/`fillText`/`setLineDash`.
  - API services (`userPreferencesService`, `snapshotsService`, `alertsService`, `indicatorsService`, `marketService`, `accountService`, …) are mocked with every method the subject calls.
- **Required depth per plugin** (the four layers are all exercised):
  1. **State**: transitions, point add/update/clear, active tool/degree selection, delegate firing.
  2. **Mouse adapter**: coordinate→target mapping, hit-test radius (including the inclusive boundary), snapping hooks, drag lifecycle, click-vs-drag disambiguation.
  3. **Renderer / canvas**: geometry calculations (e.g. retracement/extension line bounds), pixel-ratio scaling, and the actual draw calls.
  4. **Primitive integration**: `attached` / `detached` / `destroy`, delegate-to-state reactions, `updateAllViews` renderer data, cursor resolution through `hitTest()`, and future-point projection via `TimeProjector`.
- **Rewind coverage** spans three levels: pure helpers (`finance/rewind.test.ts` for `captureSnapshot`/`generateUUID`/`appendSnapshot`/`getSnapshots`/`findSnapshotAtOrBefore`/`areSnapshotsEqual`; `rewind-timeline.test.ts` for `snapshotTimelineDomain`/`timeToFraction`/`fractionToTime`/`sliceCandlesBefore`), the component (scrub, markers, "Back to now", empty state), and the page ("Rewind Save Snapshot" for POST payload/dedupe/Cmd+S/error toasts, "Rewind Scrub and Drawing Restore" for sliced candles, snapshot drawings and indicator recomputation).

Run the frontend suites with `./scripts/agent-test frontend/src/lib/components/charts/...` while iterating and `./scripts/agent-test frontend` before finishing.

## Invariants and safe-change notes

- **Plugins are peers, not dependencies.** Sharing goes to `plugins/helpers/` or `$lib/utils/finance/` — never to a sibling plugin directory. The Fibonacci→Elliott snap feature is the reference example of doing this correctly (via `getActiveFibLevelPrices`).
- **Every subscription is tracked and released.** Primitives must register delegates through `_subscribe`/`_subscribeToUpdate` and mouse handlers must be detached in `detached()`; the chart's teardown destroys primitives before `chart.remove()`. Forgetting either leaks listeners that keep firing after the primitive is gone.
- **`updateAllViews()` must tolerate detachment** (it is called on viewport changes), which is why the base class passes `null` renderer data when chart/series references are missing.
- **Canvas geometry is bitmap space.** Draw inside `useBitmapCoordinateSpace` and derive pixel-aligned geometry from `positionsLine`/`positionsBox`; raw media coordinates produce blurry 1 px lines on high-DPI displays.
- **Snapshot equality ignores identity.** `areSnapshotsEqual` compares drawings + data window only; changing it to compare `id`/`captured_at` would break save-dedupe. The server's ascending `captured_at` ordering and the page's append-only array keep `snapshots[0]` the oldest, which `snapshotTimelineDomain` depends on.
- **Rewind is read-only.** Any new chart mutation (a new tool, a new preference write, a new fetch) must add its own `isRewound` guard, or it will write live state while the user is looking at a past snapshot.
- **Stale-response guards are per indicator.** New indicator work must thread the page's `sequenceCounter` / `indicatorSeq` so a slow response cannot overwrite newer data or re-enable a disabled indicator.
