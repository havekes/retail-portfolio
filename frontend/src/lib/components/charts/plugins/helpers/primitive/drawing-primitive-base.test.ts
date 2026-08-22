import { describe, it, expect, vi, beforeEach } from 'vitest';
import type {
	IChartApi,
	IPrimitivePaneRenderer,
	ISeriesApi,
	SeriesType,
	Time
} from 'lightweight-charts';
import { Delegate } from '../delegate';
import {
	DrawingPrimitiveBase,
	type IDrawingMouseHandlers,
	type IDrawingToolState,
	type IUpdatablePaneView
} from './drawing-primitive-base';
import type { MousePosition } from '../mouse/mouse-position';
import type { Candle } from '$lib/utils/finance/candle';

interface TestTarget {
	id: string;
}

interface TestRendererData {
	renderedValue: string;
}

class TestToolState implements IDrawingToolState<TestTarget, TestTarget> {
	private _isDrawingMode: boolean = false;
	private _hovered: TestTarget | null = null;
	private _dragging: TestTarget | null = null;
	private _points: { time: Time; price: number }[] = [];

	private _drawingModeChanged = new Delegate<boolean>();
	public customStateDelegate = new Delegate<string>();

	public isDrawingMode(): boolean {
		return this._isDrawingMode;
	}

	public setDrawingMode(enabled: boolean): void {
		this._isDrawingMode = enabled;
		this._drawingModeChanged.fire(enabled);
	}

	public drawingModeChanged() {
		return this._drawingModeChanged;
	}

	public getHoveredPoint(): TestTarget | null {
		return this._hovered;
	}

	public setHoveredPoint(target: TestTarget | null): void {
		this._hovered = target;
	}

	public getDraggingPoint(): TestTarget | null {
		return this._dragging;
	}

	public setDraggingPoint(target: TestTarget | null): void {
		this._dragging = target;
	}

	public addPoint(point: { time: Time; price: number }) {
		this._points.push(point);
		return point;
	}

	public getPoints() {
		return this._points;
	}

	public destroy(): void {
		this._drawingModeChanged.destroy();
		this.customStateDelegate.destroy();
	}
}

class TestMouseHandlers implements IDrawingMouseHandlers<TestTarget, TestTarget> {
	public attachedCalled = false;
	public detachedCalled = false;
	public drawingMode: boolean = false;

	public _mouseMoved = new Delegate<MousePosition | null>();
	public _pointHovered = new Delegate<TestTarget | null>();
	public _dragStarted = new Delegate<TestTarget>();
	public _dragEnded = new Delegate<TestTarget>();
	public _chartClicked = new Delegate<{ time: Time; price: number; x: number; y: number }>();
	public customMouseDelegate = new Delegate<number>();

	public attached(): void {
		this.attachedCalled = true;
	}

	public detached(): void {
		this.detachedCalled = true;
	}

	public setDrawingMode(isDrawing: boolean): void {
		this.drawingMode = isDrawing;
	}

	public mouseMoved() {
		return this._mouseMoved;
	}

	public pointHovered() {
		return this._pointHovered;
	}

	public dragStarted() {
		return this._dragStarted;
	}

	public dragEnded() {
		return this._dragEnded;
	}

	public chartClicked() {
		return this._chartClicked;
	}
}

class TestPaneView implements IUpdatablePaneView<TestRendererData> {
	public lastUpdatedData: TestRendererData | null = null;

	public zOrder() {
		return 'top' as const;
	}

	public renderer(): IPrimitivePaneRenderer {
		return { draw: () => {} };
	}

	public update(data: TestRendererData | null): void {
		this.lastUpdatedData = data;
	}
}

class ConcreteDrawingPrimitive extends DrawingPrimitiveBase<
	TestRendererData,
	TestPaneView,
	TestToolState,
	TestMouseHandlers,
	TestTarget,
	TestTarget
> {
	public customDelegateCallbackCalls = 0;
	public customDelegateLastValue: string | null = null;
	public rendererValueToReturn: string | null = 'mock-render-data';

	constructor(state: TestToolState, mouseHandlers: TestMouseHandlers, paneView: TestPaneView) {
		super({
			externalId: 'test-primitive',
			state,
			mouseHandlers,
			paneView
		});
	}

	protected override _setupSubscriptions(): void {
		this._subscribe(this._state.customStateDelegate, (val) => {
			this.customDelegateCallbackCalls++;
			this.customDelegateLastValue = val;
		});
		this._subscribeToUpdate(this._mouseHandlers.customMouseDelegate);
	}

	protected override _calculateRendererData(): TestRendererData | null {
		if (!this.rendererValueToReturn) return null;
		return { renderedValue: this.rendererValueToReturn };
	}
}

function createMockChartAndSeries() {
	const mockChartElement = document.createElement('div');
	const timeScale = {
		coordinateToTime: vi.fn(),
		timeToCoordinate: vi.fn(),
		coordinateToLogical: vi.fn(),
		logicalToCoordinate: vi.fn(),
		height: vi.fn(() => 30),
		width: vi.fn(() => 750)
	};
	const priceScale = {
		width: vi.fn(() => 50),
		applyOptions: vi.fn()
	};
	const series = {
		coordinateToPrice: vi.fn(),
		priceToCoordinate: vi.fn(),
		priceScale: vi.fn(() => priceScale)
	} as unknown as ISeriesApi<SeriesType>;

	const chart = {
		chartElement: vi.fn(() => mockChartElement),
		timeScale: vi.fn(() => timeScale),
		options: vi.fn(() => ({})),
		applyOptions: vi.fn()
	} as unknown as IChartApi;

	return { chart, series };
}

describe('DrawingPrimitiveBase', () => {
	let state: TestToolState;
	let mouseHandlers: TestMouseHandlers;
	let paneView: TestPaneView;
	let primitive: ConcreteDrawingPrimitive;
	let mockChart: IChartApi;
	let mockSeries: ISeriesApi<SeriesType>;
	let requestUpdate: ReturnType<typeof vi.fn<() => void>>;

	beforeEach(() => {
		state = new TestToolState();
		mouseHandlers = new TestMouseHandlers();
		paneView = new TestPaneView();
		primitive = new ConcreteDrawingPrimitive(state, mouseHandlers, paneView);

		const mocks = createMockChartAndSeries();
		mockChart = mocks.chart;
		mockSeries = mocks.series;
		requestUpdate = vi.fn<() => void>();
	});

	it('exposes paneViews with configured paneView', () => {
		const views = primitive.paneViews();
		expect(views).toHaveLength(1);
		expect(views[0]).toBe(paneView);
	});

	it('attaches chart, series, timeProjector, and mouseHandlers on attached()', () => {
		primitive.attached({
			chart: mockChart,
			series: mockSeries,
			requestUpdate,
			horzScaleBehavior: {} as never
		});

		expect(mouseHandlers.attachedCalled).toBe(true);
		expect(requestUpdate).toHaveBeenCalled();
	});

	it('synchronizes drawing mode between state and mouse handlers on attach and state change', () => {
		state.setDrawingMode(true);
		primitive.attached({
			chart: mockChart,
			series: mockSeries,
			requestUpdate,
			horzScaleBehavior: {} as never
		});

		expect(mouseHandlers.drawingMode).toBe(true);

		state.setDrawingMode(false);
		expect(mouseHandlers.drawingMode).toBe(false);
		expect(primitive.isDrawingMode()).toBe(false);

		primitive.setDrawingMode(true);
		expect(state.isDrawingMode()).toBe(true);
		expect(mouseHandlers.drawingMode).toBe(true);
	});

	it('wires common mouse handler events to state and updates on attached()', () => {
		primitive.attached({
			chart: mockChart,
			series: mockSeries,
			requestUpdate,
			horzScaleBehavior: {} as never
		});
		requestUpdate.mockClear();

		// mouseMoved
		mouseHandlers._mouseMoved.fire(null);
		expect(requestUpdate).toHaveBeenCalledTimes(1);

		// pointHovered
		mouseHandlers._pointHovered.fire({ id: 'target-1' });
		expect(state.getHoveredPoint()).toEqual({ id: 'target-1' });
		expect(requestUpdate).toHaveBeenCalledTimes(2);

		// dragStarted
		mouseHandlers._dragStarted.fire({ id: 'drag-1' });
		expect(state.getDraggingPoint()).toEqual({ id: 'drag-1' });
		expect(requestUpdate).toHaveBeenCalledTimes(3);

		// dragEnded
		mouseHandlers._dragEnded.fire({ id: 'drag-1' });
		expect(state.getDraggingPoint()).toBeNull();
		expect(requestUpdate).toHaveBeenCalledTimes(4);

		// chartClicked when not in drawing mode -> no point added
		mouseHandlers._chartClicked.fire({ time: '2024-01-01' as Time, price: 100, x: 10, y: 20 });
		expect(state.getPoints()).toHaveLength(0);

		// chartClicked when in drawing mode -> adds point and requests update
		primitive.setDrawingMode(true);
		requestUpdate.mockClear();
		mouseHandlers._chartClicked.fire({ time: '2024-01-02' as Time, price: 150, x: 20, y: 30 });
		expect(state.getPoints()).toEqual([{ time: '2024-01-02', price: 150 }]);
		expect(requestUpdate).toHaveBeenCalled();
	});

	it('wires subclass custom subscriptions via _subscribe and _subscribeToUpdate', () => {
		primitive.attached({
			chart: mockChart,
			series: mockSeries,
			requestUpdate,
			horzScaleBehavior: {} as never
		});
		requestUpdate.mockClear();

		state.customStateDelegate.fire('hello');
		expect(primitive.customDelegateCallbackCalls).toBe(1);
		expect(primitive.customDelegateLastValue).toBe('hello');

		mouseHandlers.customMouseDelegate.fire(42);
		expect(requestUpdate).toHaveBeenCalledTimes(1);
	});

	it('unsubscribes all delegates and detaches mouse handlers on detached()', () => {
		primitive.attached({
			chart: mockChart,
			series: mockSeries,
			requestUpdate,
			horzScaleBehavior: {} as never
		});

		primitive.detached();
		expect(mouseHandlers.detachedCalled).toBe(true);

		requestUpdate.mockClear();
		state.customStateDelegate.fire('should-not-reach');
		expect(primitive.customDelegateLastValue).not.toBe('should-not-reach');

		mouseHandlers._mouseMoved.fire(null);
		mouseHandlers._pointHovered.fire({ id: 't' });
		mouseHandlers._dragStarted.fire({ id: 'd' });
		mouseHandlers._dragEnded.fire({ id: 'd' });
		mouseHandlers._chartClicked.fire({ time: '2024-01-01' as Time, price: 100, x: 0, y: 0 });
		mouseHandlers.customMouseDelegate.fire(99);

		expect(requestUpdate).not.toHaveBeenCalled();
	});

	it('destroys state on destroy() after detaching', () => {
		const stateDestroySpy = vi.spyOn(state, 'destroy');
		primitive.attached({
			chart: mockChart,
			series: mockSeries,
			requestUpdate,
			horzScaleBehavior: {} as never
		});

		primitive.destroy();
		expect(mouseHandlers.detachedCalled).toBe(true);
		expect(stateDestroySpy).toHaveBeenCalledTimes(1);
	});

	describe('Cursor resolution and hitTest', () => {
		beforeEach(() => {
			primitive.attached({
				chart: mockChart,
				series: mockSeries,
				requestUpdate,
				horzScaleBehavior: {} as never
			});
		});

		it('resolves null cursor and null hitTest when idle', () => {
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();
		});

		it('resolves grab cursor and hitTest when hovering a point', () => {
			state.setHoveredPoint({ id: 'hover-1' });
			primitive.updateAllViews();

			expect(primitive.hitTest()).toEqual({
				cursorStyle: 'grab',
				externalId: 'test-primitive',
				zOrder: 'top'
			});
		});

		it('resolves crosshair cursor and hitTest when in drawing mode', () => {
			state.setHoveredPoint({ id: 'hover-1' });
			state.setDrawingMode(true);
			primitive.updateAllViews();

			expect(primitive.hitTest()).toEqual({
				cursorStyle: 'crosshair',
				externalId: 'test-primitive',
				zOrder: 'top'
			});
		});

		it('resolves grabbing cursor and hitTest when dragging a point (top priority)', () => {
			state.setHoveredPoint({ id: 'hover-1' });
			state.setDrawingMode(true);
			state.setDraggingPoint({ id: 'drag-1' });
			primitive.updateAllViews();

			expect(primitive.hitTest()).toEqual({
				cursorStyle: 'grabbing',
				externalId: 'test-primitive',
				zOrder: 'top'
			});
		});
	});

	describe('updateAllViews', () => {
		it('passes null to paneView when chart/series is not attached', () => {
			primitive.updateAllViews();
			expect(paneView.lastUpdatedData).toBeNull();
		});

		it('passes calculated renderer data to paneView when attached', () => {
			primitive.attached({
				chart: mockChart,
				series: mockSeries,
				requestUpdate,
				horzScaleBehavior: {} as never
			});

			primitive.updateAllViews();
			expect(paneView.lastUpdatedData).toEqual({ renderedValue: 'mock-render-data' });
		});

		it('passes null to paneView when calculateRendererData returns null', () => {
			primitive.attached({
				chart: mockChart,
				series: mockSeries,
				requestUpdate,
				horzScaleBehavior: {} as never
			});

			primitive.rendererValueToReturn = null;
			primitive.updateAllViews();
			expect(paneView.lastUpdatedData).toBeNull();
		});
	});

	describe('setCandles', () => {
		it('updates time projector candles and requests update', () => {
			primitive.attached({
				chart: mockChart,
				series: mockSeries,
				requestUpdate,
				horzScaleBehavior: {} as never
			});
			requestUpdate.mockClear();

			const candles: Candle[] = [
				{
					time: '2024-01-01' as Time,
					open: 100,
					high: 105,
					low: 95,
					close: 102,
					volume: 1000
				}
			];

			primitive.setCandles(candles);
			expect(requestUpdate).toHaveBeenCalled();
		});
	});
});
