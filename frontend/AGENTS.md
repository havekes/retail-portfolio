Coding Agent Guide: retail-portfolio (Frontend)

## Project Overview

`retail-portfolio` is a portfolio tracker designed for the retail investor.

**Frontend Tech Stack**:

- Svelte 5 / SvelteKit
- TypeScript
- TailwindCSS v4
- Vite
- npm package manager

## Infrastructure

- Docker Compose for dev environment

## Development Workflow

**ALWAYS**: Execute frontend commands in the frontend service (`docker compose exec frontend`).

**Frontend Workflow**:

1. Install dependencies: `npm install`
2. Lint and format code: `npm run lint`
3. Run type checks: `npm run check`
4. Run tests (vitest): `npm run test:run`
5. Format code: `npm run format`

**MANDATORY**: When writing or editing code, **ALWAYS** run linting, type checks, tests and format before submitting.

## Testing

**MANDATORY**: **ALWAYS** mock **ALL** API calls in frontend tests. Tests must never hit a real backend or perform real network requests.

Rationale: CI runs without a backend, so any unmocked fetch fails with `ECONNREFUSED` and makes the suite flaky (e.g. `Failed to fetch account totals [TypeError: fetch failed]`).

- Mock every API client module the component under test depends on, and stub **every** method it calls:

  ```typescript
  vi.mock('$lib/api/accountClient', () => ({
  	accountClient: { getAccountTotals: vi.fn() }
  }));

  import { accountClient } from '$lib/api/accountClient';

  beforeEach(() => {
  	vi.mocked(accountClient.getAccountTotals).mockResolvedValue({
  		value: { value: '100', units: 100, nanos: 0, currencyCode: 'CAD' },
  		cost: { value: '50', units: 50, nanos: 0, currencyCode: 'CAD' }
  	});
  });
  ```

- Also mock framework and third-party modules that make network or browser calls (`$app/forms`, `$app/paths`, `lightweight-charts`, etc.).
- A test that performs a real `fetch()`/XHR is broken by definition: it fails on CI and depends on a running backend locally. If you see a real network call from a test, mock it — do not "fix" it by expecting the backend to be up.

## Architecture Guidelines

### 1. Layer 1: The UI Layer (`.svelte` files)

**Concept**: Keep `.svelte` files focused on markup, styling, and simple component-level view state. Push complex logic out to the service layer.

**Code Example:**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import type { DataService } from '$lib/services/DataService.svelte';

	// Retrieve the service instance from context
	const dataService = getContext<DataService>('dataService');
</script>

{#if dataService.isLoading}
	<p>Loading...</p>
{:else}
	<button onclick={() => dataService.fetchItems()}> Load Items </button>
	<ul>
		{#each dataService.items as item}
			<li>{item.name}</li>
		{/each}
	</ul>
{/if}
```

#### 🚨 Gotcha 1: Never Destructure Primitives

When consuming a reactive class or object, do not destructure its primitive properties. Destructuring severs the proxy connection, instantly breaking reactivity. Always access them directly on the object instance (e.g., use `dataService.isLoading` instead of `let { isLoading } = dataService`).

#### 🚨 Gotcha 2: Misusing Effects

Use `$effect` exclusively for side effects like syncing to `localStorage`, manipulating the DOM, or setting up event listeners. Do not use `$effect` to synchronize state or trigger data fetches. Use `$derived` for computed state, or update state directly in event handlers.

### 2. Layer 2: The State & Service Layer (`.svelte.ts` files)

**Concept**: Extract complex state, business logic, and API orchestration into standard TypeScript files utilizing Svelte 5 Runes. Always default to ES6 Classes instead of returning objects with manual getters/setters or using legacy `svelte/store`.

**Code Example:**

```typescript
import { apiClient } from '$lib/api/apiClient';

export class DataService {
	// State properties (no getters needed)
	items = $state<Array<{ id: number; name: string }>>([]);
	isLoading = $state(false);
	errorMessage = $state<string | null>(null);

	// Derived state
	hasItems = $derived(this.items.length > 0);

	// Orchestration method
	async fetchItems() {
		this.isLoading = true;
		this.errorMessage = null;
		try {
			this.items = await apiClient.getItems();
		} catch (error) {
			this.errorMessage = error instanceof Error ? error.message : 'Unknown error';
		} finally {
			this.isLoading = false;
		}
	}
}
```

#### 🚨 Gotcha 3: SSR Data Bleed (No Global Instances)

Never export an instantiated class or a raw `$state` variable directly from a `.svelte.ts` module. In a Server-Side Rendering environment, this causes state to bleed across different users' requests. Always instantiate the class inside a component or layout (`+layout.svelte`) and pass it down via `setContext` and `getContext`.

#### 🚨 Gotcha 4: Reassigning Objects vs. Mutating

Svelte 5 deeply proxies objects and arrays declared with `$state`. You can freely mutate inner properties or push to arrays (`this.items.push(newItem)`), and the UI will update. However, if you reassign the entire array or object reference (`this.items = newArray`), the class property itself must be declared with `$state` to maintain reactivity.

### 3. Layer 3: The API & Backend Communication Layer (`.ts` files)

**Concept**: Separate raw backend communication from your reactive Svelte state. Create stateless API clients in pure `.ts` files. Their only job is to handle HTTP requests, headers, and raw data parsing.

**Code Example:**

```typescript
export const apiClient = {
	async getItems() {
		const response = await fetch('/api/items');

		if (!response.ok) {
			throw new Error(`Failed to fetch items: ${response.statusText}`);
		}

		return response.json();
	}
};
```

#### 🚨 Gotcha 5: Error State Granularity

When handling backend calls in your service class, do not use a generic boolean error state. Always catch and store the actual error message strings or objects so the UI layer can provide actionable feedback to the user.

#### 🚨 Gotcha 6: Avoid Waterfall Fetching in Components

Do not trigger sequential API calls directly inside a `.svelte` file. If step B depends on step A, orchestrate that multi-step flow entirely inside a single async method in your Service class (Layer 2). The UI component should only ever call `service.performAction()` and react to the state.

### 4. Layer 4: Chart Plugins Architecture (`src/lib/components/charts/plugins/`)

**Concept**: Chart drawing tools and visual indicators extend Lightweight Charts via Series Primitives (`ISeriesPrimitive<Time>`). To keep plugins modular, maintainable, and leak-free, plugins adhere to a strict layered structure, consume reusable abstractions from `plugins/helpers/`, and delegate pure financial calculations to `$lib/utils/finance/`.

#### Per-Plugin Directory Layout

Each drawing tool lives in its own directory `frontend/src/lib/components/charts/plugins/<plugin-name>/` with standardized module responsibilities:

- `state.ts`: Manages tool state, point arrays, active mode, selection, hover/drag targets, and emits change events via `Delegate`. Operates purely on domain data — never touches DOM elements or chart coordinates.
- `mouse.ts`: Thin plugin-specific adapter extending `ChartMouseHandlers` (from `helpers/mouse/chart-mouse-handlers`). Configures `hitTestRadius`, target mappings (`toTarget`), and optional coordinate snapping (`adjustPosition`).
- `pane-renderer.ts`: Implements `IPrimitivePaneRenderer`. Handles canvas drawing (shapes, handles, dashed lines, text labels, preview lines) using bitmap coordinate spaces (`useBitmapCoordinateSpace` / `BitmapCoordinatesRenderingScope`) to ensure crisp rendering across pixel ratios.
- `pane-view.ts`: Implements `IPrimitivePaneView` / `IUpdatablePaneView<TRendererData>`. Stores calculated renderer data and returns the pane renderer instance with appropriate `zOrder` (`'bottom'` | `'normal'` | `'top'`).
- `constants.ts`: Defines visual constants, handle radii, hit-test radii, line styles/widths, colors, opacity values, and degree configurations.
- `index.ts`: Barrel file exporting the primitive class, state, renderer, view, mouse adapter, and public constants/types.
- **Rule**: Strictly no cross-plugin imports (e.g., `fibonacci` must never import from `elliott-wave`). Shared functionality must reside in `plugins/helpers/` or `$lib/utils/finance/`.

#### Shared Helpers Area (`plugins/helpers/`)

Common primitive plumbing is centralized under `frontend/src/lib/components/charts/plugins/helpers/`:

- `helpers/delegate.ts`: `Delegate<T>` class and `ISubscription<T>` interface for type-safe, decoupled event publisher/subscriber pattern with `subscribe`, `unsubscribe`, `unsubscribeAll(linkedObject)`, `fire`, `hasListeners`, and `destroy`.
- `helpers/dimensions/`: `positionsLine` and `positionsBox` (`dimensions/positions.ts`) with `BitmapPositionLength` (`dimensions/common.ts`) for crisp pixel-aligned coordinate math and pixel ratio scaling across standard and high-DPI displays.
- `helpers/time/`: `TimeProjector` (`time/time-projector.ts`) for projecting coordinates <-> time across historical data and future/extrapolated bars beyond the last candle, along with time arithmetic helpers in `time/time.ts` (`addIntervalToTime`, `barsBetweenTimes`, `computeIntervalSeconds`, `epochSecondsToTime`, `timeToEpochSeconds`).
- `helpers/mouse/`: `ChartMouseHandlers<TPoint, TTarget, TOriginal>` (`mouse/chart-mouse-handlers.ts`) handling DOM listener lifecycle (including window mouseup/mousemove), plot area clipping, hit testing with inclusive radius tie-breaking, dragging lifecycle with click suppression, chart-scroll disabling during drags (`pressedMouseMove: false`), and delegates (`mouseMoved`, `chartClicked`, `pointClicked`, `emptyAreaClicked`, `pointHovered`, `dragStarted`, `pointDragged`, `dragEnded`).
- `helpers/primitive/`: `DrawingPrimitiveBase<TRendererData, TPaneView, TState, TMouseHandlers, THoverTarget, TDragTarget>` (`primitive/drawing-primitive-base.ts`) abstract base class implementing `ISeriesPrimitive<Time>`. Encapsulates `attached()` / `detached()` lifecycle, subscription tracking with automatic cleanup via `unsubscribeAll(this)`, cursor resolution (`'grabbing'` | `'crosshair'` | `'grab'` | `null`), `hitTest()`, `paneViews()`, and `updateAllViews()`.

#### Primitive Lifecycle Contract

All drawing primitives extending `DrawingPrimitiveBase` follow a strict lifecycle:

1. `attached({ chart, series, requestUpdate })`:
   - Stores chart, series, and `requestUpdate` callbacks.
   - Binds `TimeProjector` and `ChartMouseHandlers` to the chart/series.
   - Sets up standard delegate subscriptions (`drawingModeChanged`, `mouseMoved`, `pointHovered`, `dragStarted`, `dragEnded`, `chartClicked`) and custom subscriptions via `_setupSubscriptions()`.
   - Tracks all subscriptions in `_trackedSubscriptions` via `_subscribe()` / `_subscribeToUpdate()`.
   - Requests initial chart redraw via `requestUpdate()`.
2. `updateAllViews()`:
   - Invoked by Lightweight Charts on viewport/scroll changes or when `_requestUpdate()` is called.
   - Early-returns `paneView.update(null)` if detached or references are missing.
   - Calculates renderer data via abstract `_calculateRendererData()`.
   - Updates cursor state via `_updateCursor()`.
   - Passes data to the pane view via `paneView.update(rendererData)`.
3. `detached()`:
   - Cleans up all tracked subscriptions via `sub.unsubscribeAll(this)`.
   - Cleans up mouse event listeners via `_mouseHandlers.detached()`.
   - Unsets chart, series, and `requestUpdate` references.
4. `destroy()`:
   - Calls `this.detached()`.
   - Destroys state delegates via `this._state.destroy()`.

#### Rule of Thumb: Pure Finance Math Boundaries

- Pure domain calculations and mathematical models (e.g., Fibonacci ratios/retracement levels, Elliott Wave pattern validation and wave degree rules, Bollinger Bands formulas, SMA/EMA, RSI, MACD, OBV) belong in `frontend/src/lib/utils/finance/` with dedicated unit tests.
- Chart plugins only handle visualization, coordinate projection, canvas rendering, and user interaction. Never embed finance formulas or pattern validation rules inside plugin renderers, views, or mouse adapters.

#### Testing Conventions

- **Suite Colocation**:
  - Every plugin must have a colocated test suite (`<plugin-name>.test.ts`, e.g., `fibonacci.test.ts`, `elliott-wave.test.ts`).
  - Shared helpers have their own colocated unit test suites (`chart-mouse-handlers.test.ts`, `drawing-primitive-base.test.ts`, etc.).
- **Mocks**:
  - Mock Lightweight Charts APIs (`IChartApi`, `ISeriesApi`, `timeScale`, `priceScale`).
  - Mock canvas rendering targets (`CanvasRenderingTarget2D`, `BitmapCoordinatesRenderingScope`, `CanvasRenderingContext2D`).
- **Required Test Depth**:
  1. **State unit tests**: Verify state transitions, point additions/updates/clears, active tool/degree selection, and delegate firing.
  2. **Mouse adapter tests**: Verify coordinate-to-target mapping, hit-testing radius, snapping hooks (`adjustPosition`), dragging lifecycle, and click vs. drag disambiguation.
  3. **Renderer / Canvas tests**: Verify geometry calculations, coordinate scaling with pixel ratios, and canvas draw calls (`moveTo`, `lineTo`, `arc`, `fill`, `stroke`, `fillText`, `setLineDash`).
  4. **Primitive integration tests**: Verify complete lifecycle (`attached`, `detached`, `destroy`), delegate-to-state reactions, `updateAllViews` calculations, cursor resolution via `hitTest()`, and future point projection via `TimeProjector`.

#### 🚨 Gotcha 7: Cross-Plugin Imports

Plugins must be completely decoupled from one another. Never import code or types from a sibling plugin directory (e.g. `import from '../fibonacci'`). If code or types need to be shared across multiple plugins, place them in `frontend/src/lib/components/charts/plugins/helpers/` or `frontend/src/lib/utils/finance/`.

#### 🚨 Gotcha 8: Memory Leaks in Lifecycle

Failing to unsubscribe delegates when a series or primitive is removed causes memory leaks and stale event firing. Always use `_subscribe()` / `_subscribeToUpdate()` within `DrawingPrimitiveBase` or call `unsubscribeAll(this)` and `mouseHandlers.detached()` inside `detached()`.

#### 🚨 Gotcha 9: High-DPI Canvas Rendering

Never draw to the canvas using raw media coordinates without accounting for device pixel ratios. Always use `positionsLine()` and `positionsBox()` from `helpers/dimensions/positions` along with `BitmapCoordinatesRenderingScope` to ensure 1px lines and handles remain crisp on Retina/high-DPI displays.
