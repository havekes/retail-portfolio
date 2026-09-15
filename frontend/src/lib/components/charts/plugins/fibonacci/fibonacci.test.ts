import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import type { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';
import {
	FibonacciPrimitive,
	FibonacciToolState,
	FibonacciPaneRenderer,
	FibonacciPaneView,
	MouseHandlers,
	calculateRetracementLineBounds,
	calculateExtensionLineBounds,
	HIT_TEST_RADIUS,
	HANDLE_RADIUS,
	PREVIEW_ALPHA,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_TRENDLINE_COLOR,
	type FibPointTarget,
	type ProjectedFibPointWithTarget,
	type ProjectedFibLine,
	type FibonacciRendererData
} from './index';
import type { Candle } from '$lib/utils/finance/candle';
import { TimeProjector } from '../helpers/time/time-projector';

function createDailyCandles(count = 30): Candle[] {
	return Array.from({ length: count }, (_, i) => {
		const day = i + 1;
		return {
			time: `2024-01-${String(day).padStart(2, '0')}` as Time,
			open: 100 + i,
			high: 110 + i,
			low: 95 + i,
			close: 105 + i
		};
	});
}

function createMockChartAndSeries() {
	const mockChartElement = document.createElement('div');
	Object.defineProperty(mockChartElement, 'clientWidth', { value: 800, configurable: true });
	Object.defineProperty(mockChartElement, 'clientHeight', { value: 500, configurable: true });
	mockChartElement.getBoundingClientRect = () => ({
		left: 0,
		top: 0,
		right: 800,
		bottom: 500,
		width: 800,
		height: 500,
		x: 0,
		y: 0,
		toJSON: () => {}
	});

	const timeScale = {
		coordinateToTime: vi.fn((x: number) => {
			if (x < 0 || x > 725) return null;
			const day = Math.floor(x / 25) + 1;
			return `2024-01-${String(Math.min(30, Math.max(1, day))).padStart(2, '0')}` as Time;
		}),
		timeToCoordinate: vi.fn((time: Time) => {
			if (typeof time === 'string' && time.startsWith('2024-01-')) {
				const day = parseInt(time.replace('2024-01-', ''), 10);
				return (day - 1) * 25;
			}
			return null;
		}),
		coordinateToLogical: vi.fn((x: number) => {
			if (x < 0 || x > 1500) return null;
			return x / 25;
		}),
		logicalToCoordinate: vi.fn((logical: number) => logical * 25),
		height: vi.fn(() => 30),
		width: vi.fn(() => 750)
	};

	const priceScale = {
		width: vi.fn(() => 50),
		applyOptions: vi.fn()
	};

	const series = {
		coordinateToPrice: vi.fn((y: number) => {
			if (y < 0 || y > 470) return null;
			return 200 - y * 0.2;
		}),
		priceToCoordinate: vi.fn((price: number) => {
			if (price < 0 || price > 500) return null;
			return (200 - price) / 0.2;
		}),
		priceScale: vi.fn(() => priceScale)
	} as unknown as ISeriesApi<SeriesType>;

	const chart = {
		chartElement: vi.fn(() => mockChartElement),
		timeScale: vi.fn(() => timeScale),
		options: vi.fn(() => ({ handleScroll: { pressedMouseMove: true } })),
		applyOptions: vi.fn()
	} as unknown as IChartApi;

	return { chart, series, mockChartElement, timeScale, priceScale };
}

function createMockCanvasTarget() {
	const drawCalls: { type: string; args: unknown[] }[] = [];
	const context = {
		save: vi.fn(() => drawCalls.push({ type: 'save', args: [] })),
		restore: vi.fn(() => drawCalls.push({ type: 'restore', args: [] })),
		beginPath: vi.fn(() => drawCalls.push({ type: 'beginPath', args: [] })),
		moveTo: vi.fn((x: number, y: number) => drawCalls.push({ type: 'moveTo', args: [x, y] })),
		lineTo: vi.fn((x: number, y: number) => drawCalls.push({ type: 'lineTo', args: [x, y] })),
		arc: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'arc', args })),
		fill: vi.fn(() => drawCalls.push({ type: 'fill', args: [] })),
		stroke: vi.fn(() => drawCalls.push({ type: 'stroke', args: [] })),
		fillText: vi.fn((text: string, x: number, y: number) =>
			drawCalls.push({ type: 'fillText', args: [text, x, y] })
		),
		setLineDash: vi.fn((dash: number[]) => drawCalls.push({ type: 'setLineDash', args: [dash] })),
		strokeStyle: '',
		fillStyle: '',
		lineWidth: 1,
		lineCap: 'butt',
		lineJoin: 'miter',
		font: '',
		textAlign: 'start',
		textBaseline: 'alphabetic',
		globalAlpha: 1
	} as unknown as CanvasRenderingContext2D;

	const scope: BitmapCoordinatesRenderingScope = {
		context,
		horizontalPixelRatio: 2,
		verticalPixelRatio: 2,
		mediaSize: {
			width: 800,
			height: 500
		} as unknown as BitmapCoordinatesRenderingScope['mediaSize'],
		bitmapSize: {
			width: 1600,
			height: 1000
		} as unknown as BitmapCoordinatesRenderingScope['bitmapSize']
	};

	const target: CanvasRenderingTarget2D = {
		useBitmapCoordinateSpace: vi.fn((callback: (s: BitmapCoordinatesRenderingScope) => void) => {
			callback(scope);
		})
	} as unknown as CanvasRenderingTarget2D;

	return { target, context, scope, drawCalls };
}

describe('Fibonacci Chart Primitive Plugin', () => {
	describe('Constants', () => {
		it('defines expected visual constants', () => {
			expect(HIT_TEST_RADIUS).toBe(14);
			expect(HANDLE_RADIUS).toBe(5);
			expect(PREVIEW_ALPHA).toBe(0.65);
			expect(DEFAULT_HANDLE_COLOR).toBe('#2962FF');
			expect(DEFAULT_TRENDLINE_COLOR).toBe('#787B86');
		});
	});

	describe('Line Bounds Calculations', () => {
		describe('calculateRetracementLineBounds', () => {
			it('starts from Math.max(p1x, p2x) and extends rightward by 1x distance for left-to-right swing', () => {
				const bounds = calculateRetracementLineBounds(100, 250);
				// dist = 150 -> xStart = 250, xEnd = 250 + 150 = 400
				expect(bounds.xStart).toBe(250);
				expect(bounds.xEnd).toBe(400);
			});

			it('starts from Math.max(p1x, p2x) and extends rightward by 1x distance for right-to-left swing', () => {
				const bounds = calculateRetracementLineBounds(250, 100);
				// dist = 150 -> xStart = 250, xEnd = 250 + 150 = 400
				expect(bounds.xStart).toBe(250);
				expect(bounds.xEnd).toBe(400);
			});

			it('falls back to minimum width delta of 50px when distance is less than 30px', () => {
				const boundsSmall = calculateRetracementLineBounds(100, 110);
				// dist = 10 < 30 -> widthDelta = 50 -> xStart = 110, xEnd = 160
				expect(boundsSmall.xStart).toBe(110);
				expect(boundsSmall.xEnd).toBe(160);

				const boundsZero = calculateRetracementLineBounds(100, 100);
				// dist = 0 < 30 -> widthDelta = 50 -> xStart = 100, xEnd = 150
				expect(boundsZero.xStart).toBe(100);
				expect(boundsZero.xEnd).toBe(150);
			});

			it('extends to fullWidth when extendLines is true and fullWidth is provided', () => {
				const bounds = calculateRetracementLineBounds(100, 250, 800, true);
				expect(bounds.xStart).toBe(250);
				expect(bounds.xEnd).toBe(800);
			});

			it('ignores extendLines when fullWidth is undefined', () => {
				const bounds = calculateRetracementLineBounds(100, 250, undefined, true);
				expect(bounds.xStart).toBe(250);
				expect(bounds.xEnd).toBe(400);
			});
		});

		describe('calculateExtensionLineBounds', () => {
			it('starts from p3x and extends rightward by 2x distance between p1 and p3 for left-to-right points', () => {
				const bounds = calculateExtensionLineBounds(100, 200, 250);
				// dist = |250 - 100| = 150 -> widthDelta = 2 * 150 = 300 -> xStart = 250, xEnd = 550
				expect(bounds.xStart).toBe(250);
				expect(bounds.xEnd).toBe(550);
			});

			it('starts from p3x and extends rightward by 2x distance when p3 is to the left of p1', () => {
				const bounds = calculateExtensionLineBounds(300, 200, 150);
				// dist = |150 - 300| = 150 -> widthDelta = 2 * 150 = 300 -> xStart = 150, xEnd = 450
				expect(bounds.xStart).toBe(150);
				expect(bounds.xEnd).toBe(450);
			});

			it('falls back to minimum width delta of 50px when distance between p1 and p3 is less than 30px', () => {
				const bounds = calculateExtensionLineBounds(100, 200, 110);
				// dist = |110 - 100| = 10 < 30 -> widthDelta = 50 -> xStart = 110, xEnd = 160
				expect(bounds.xStart).toBe(110);
				expect(bounds.xEnd).toBe(160);
			});

			it('extends to fullWidth when extendLines is true and fullWidth is provided', () => {
				const bounds = calculateExtensionLineBounds(100, 200, 250, 1000, true);
				expect(bounds.xStart).toBe(250);
				expect(bounds.xEnd).toBe(1000);
			});
		});
	});

	describe('FibonacciToolState', () => {
		let state: FibonacciToolState;

		beforeEach(() => {
			state = new FibonacciToolState();
		});

		it('initializes with default tool and no placed drawings', () => {
			expect(state.getActiveTool()).toBe('retracement');
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getRetracement()).toBeNull();
			expect(state.getExtension()).toBeNull();
			expect(state.getPendingPoints()).toEqual([]);
		});

		it('allows switching active tool and notifies subscribers', () => {
			const toolHandler = vi.fn();
			state.toolChanged().subscribe(toolHandler);

			state.setActiveTool('extension');
			expect(state.getActiveTool()).toBe('extension');
			expect(toolHandler).toHaveBeenCalledWith('extension');

			state.setActiveTool('retracement');
			expect(state.getActiveTool()).toBe('retracement');
			expect(toolHandler).toHaveBeenCalledWith('retracement');
		});

		it('toggles drawing mode and resets pending points on exit', () => {
			const modeHandler = vi.fn();
			state.drawingModeChanged().subscribe(modeHandler);

			state.setDrawingMode(true);
			expect(state.isDrawingMode()).toBe(true);
			expect(modeHandler).toHaveBeenCalledWith(true);

			state.addPoint({ time: '2024-01-05' as Time, price: 150 });
			expect(state.getPendingPoints()).toHaveLength(1);

			state.setDrawingMode(false);
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getPendingPoints()).toHaveLength(0);
			expect(modeHandler).toHaveBeenCalledWith(false);
		});

		it('handles 2-point retracement drawing sequence and automatically exits drawing mode', () => {
			const drawingsHandler = vi.fn();
			const modeHandler = vi.fn();
			state.drawingsChanged().subscribe(drawingsHandler);
			state.drawingModeChanged().subscribe(modeHandler);

			state.setActiveTool('retracement');
			state.setDrawingMode(true);

			// Point 1
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			expect(state.isDrawingMode()).toBe(true);
			expect(state.getRetracement()).toBeNull();
			expect(state.getPendingPoints()).toHaveLength(1);

			// Point 2 completes the drawing
			state.addPoint({ time: '2024-01-10' as Time, price: 180 });
			expect(state.isDrawingMode()).toBe(false);
			expect(modeHandler).toHaveBeenCalledWith(false);
			expect(state.getPendingPoints()).toHaveLength(0);

			const retracement = state.getRetracement();
			expect(retracement).not.toBeNull();
			expect(retracement?.p1).toEqual({ time: '2024-01-01', price: 100 });
			expect(retracement?.p2).toEqual({ time: '2024-01-10', price: 180 });
			expect(drawingsHandler).toHaveBeenCalled();
		});

		it('handles 3-point extension drawing sequence and automatically exits drawing mode', () => {
			const drawingsHandler = vi.fn();
			const modeHandler = vi.fn();
			state.drawingsChanged().subscribe(drawingsHandler);
			state.drawingModeChanged().subscribe(modeHandler);

			state.setActiveTool('extension');
			state.setDrawingMode(true);

			// Point 1
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			expect(state.isDrawingMode()).toBe(true);
			expect(state.getExtension()).toBeNull();
			expect(state.getPendingPoints()).toHaveLength(1);

			// Point 2
			state.addPoint({ time: '2024-01-10' as Time, price: 150 });
			expect(state.isDrawingMode()).toBe(true);
			expect(state.getExtension()).toBeNull();
			expect(state.getPendingPoints()).toHaveLength(2);

			// Point 3 completes extension drawing
			state.addPoint({ time: '2024-01-15' as Time, price: 120 });
			expect(state.isDrawingMode()).toBe(false);
			expect(modeHandler).toHaveBeenCalledWith(false);
			expect(state.getPendingPoints()).toHaveLength(0);

			const extension = state.getExtension();
			expect(extension).not.toBeNull();
			expect(extension?.p1).toEqual({ time: '2024-01-01', price: 100 });
			expect(extension?.p2).toEqual({ time: '2024-01-10', price: 150 });
			expect(extension?.p3).toEqual({ time: '2024-01-15', price: 120 });
		});

		it('updates placed anchor points for retracement and extension', () => {
			state.setActiveTool('retracement');
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			state.addPoint({ time: '2024-01-10' as Time, price: 180 });

			// Update retracement P1
			const p1Updated = state.updatePoint('retracement', 0, { price: 110 });
			expect(p1Updated).toBe(true);
			expect(state.getRetracement()?.p1.price).toBe(110);
			expect(state.getRetracement()?.p1.time).toBe('2024-01-01');

			// Update retracement P2
			const p2Updated = state.updatePoint('retracement', 1, {
				time: '2024-01-12' as Time,
				price: 190
			});
			expect(p2Updated).toBe(true);
			expect(state.getRetracement()?.p2.price).toBe(190);
			expect(state.getRetracement()?.p2.time).toBe('2024-01-12');

			// Invalid index
			expect(state.updatePoint('retracement', 2, { price: 200 })).toBe(false);

			// Extension updating
			state.setActiveTool('extension');
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			state.addPoint({ time: '2024-01-10' as Time, price: 150 });
			state.addPoint({ time: '2024-01-15' as Time, price: 120 });

			expect(state.updatePoint('extension', 2, { price: 125 })).toBe(true);
			expect(state.getExtension()?.p3.price).toBe(125);
		});

		it('clears drawings specifically or all', () => {
			state.setActiveTool('retracement');
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			state.addPoint({ time: '2024-01-10' as Time, price: 180 });

			state.setActiveTool('extension');
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			state.addPoint({ time: '2024-01-10' as Time, price: 150 });
			state.addPoint({ time: '2024-01-15' as Time, price: 120 });

			expect(state.getRetracement()).not.toBeNull();
			expect(state.getExtension()).not.toBeNull();

			// Clear only retracement
			state.clear('retracement');
			expect(state.getRetracement()).toBeNull();
			expect(state.getExtension()).not.toBeNull();

			// Clear all
			state.clear();
			expect(state.getExtension()).toBeNull();
		});

		it('manages hover and drag targets and notifies subscribers', () => {
			const hoverHandler = vi.fn();
			const dragHandler = vi.fn();
			state.hoverChanged().subscribe(hoverHandler);
			state.dragChanged().subscribe(dragHandler);

			const target: FibPointTarget = { tool: 'retracement', pointIndex: 0 };
			state.setHoveredPoint(target);
			expect(state.getHoveredPoint()).toEqual(target);
			expect(hoverHandler).toHaveBeenCalledWith(target);

			state.setDraggingPoint(target);
			expect(state.getDraggingPoint()).toEqual(target);
			expect(dragHandler).toHaveBeenCalledWith(target);

			state.setDraggingPoint(null);
			expect(state.getDraggingPoint()).toBeNull();
		});

		it('tracks selected tool, fires selectionChanged delegate, and auto-clears on clear, drawing mode, or drawing reset', () => {
			const selectionHandler = vi.fn();
			state.selectionChanged().subscribe(selectionHandler);

			expect(state.getSelectedTool()).toBeNull();

			// Select retracement
			state.setSelectedTool('retracement');
			expect(state.getSelectedTool()).toBe('retracement');
			expect(selectionHandler).toHaveBeenCalledWith('retracement');

			// Re-selecting same tool does not re-fire
			selectionHandler.mockClear();
			state.setSelectedTool('retracement');
			expect(selectionHandler).not.toHaveBeenCalled();

			// Select extension
			state.setSelectedTool('extension');
			expect(state.getSelectedTool()).toBe('extension');
			expect(selectionHandler).toHaveBeenCalledWith('extension');

			// Entering drawing mode auto-clears selection
			state.setDrawingMode(true);
			expect(state.getSelectedTool()).toBeNull();
			expect(selectionHandler).toHaveBeenCalledWith(null);

			// Clearing selected drawing auto-clears selection
			state.setDrawingMode(false);
			state.setSelectedTool('retracement');
			expect(state.getSelectedTool()).toBe('retracement');
			state.clear('retracement');
			expect(state.getSelectedTool()).toBeNull();

			state.setSelectedTool('extension');
			expect(state.getSelectedTool()).toBe('extension');
			state.clear();
			expect(state.getSelectedTool()).toBeNull();

			// Setting null drawing directly auto-clears selection
			state.setSelectedTool('retracement');
			state.setRetracement(null);
			expect(state.getSelectedTool()).toBeNull();

			state.setSelectedTool('extension');
			state.setExtension(null);
			expect(state.getSelectedTool()).toBeNull();

			state.setSelectedTool('retracement');
			state.setDrawings({ retracement: null, extension: null });
			expect(state.getSelectedTool()).toBeNull();
		});
	});

	describe('MouseHandlers', () => {
		let mouse: MouseHandlers;
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let timeProjector: TimeProjector;

		beforeEach(() => {
			mouse = new MouseHandlers();
			mockData = createMockChartAndSeries();
			timeProjector = new TimeProjector();
			timeProjector.attach(mockData.chart);
			timeProjector.updateCandles(createDailyCandles(30));
			mouse.attached(mockData.chart, mockData.series, timeProjector);
		});

		it('attaches DOM listeners and performs hit testing on projected points', () => {
			const pts: ProjectedFibPointWithTarget[] = [
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				},
				{
					tool: 'retracement',
					pointIndex: 1,
					x: 300,
					y: 150,
					originalPoint: { time: '2024-01-13' as Time, price: 170 }
				}
			];
			mouse.setProjectedPoints(pts);

			// Within HIT_TEST_RADIUS (14)
			const hit = mouse.hitTestPoint(105, 203);
			expect(hit).not.toBeNull();
			expect(hit?.tool).toBe('retracement');
			expect(hit?.pointIndex).toBe(0);

			// Out of radius
			const miss = mouse.hitTestPoint(500, 500);
			expect(miss).toBeNull();
		});

		it('retracement wins over extension when anchors share the same pixel position', () => {
			// Retracement P1 and extension P1 at the exact same coordinates — a common
			// real-world pattern where both tools are drawn over the same swing.
			mouse.setProjectedPoints([
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				},
				{
					tool: 'extension',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				}
			]);

			const hit = mouse.hitTestPoint(100, 200);
			expect(hit).not.toBeNull();
			// Retracement is first in the array; strict-< means first match wins
			expect(hit?.tool).toBe('retracement');
		});

		it('dispatches hover events on mouse move when not in drawing mode', () => {
			const hoverHandler = vi.fn();
			mouse.pointHovered().subscribe(hoverHandler);

			mouse.setProjectedPoints([
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				}
			]);

			// Move over handle
			const moveEvent = new MouseEvent('mousemove', {
				clientX: 100,
				clientY: 200
			});
			mockData.mockChartElement.dispatchEvent(moveEvent);

			expect(hoverHandler).toHaveBeenCalledWith({
				tool: 'retracement',
				pointIndex: 0
			});

			// Move away
			const moveAwayEvent = new MouseEvent('mousemove', {
				clientX: 400,
				clientY: 400
			});
			mockData.mockChartElement.dispatchEvent(moveAwayEvent);

			expect(hoverHandler).toHaveBeenCalledWith(null);
		});

		it('locks chart scrolling on anchor drag start and restores on drag end', () => {
			const dragStartHandler = vi.fn();
			const pointDraggedHandler = vi.fn();
			const dragEndHandler = vi.fn();

			mouse.dragStarted().subscribe(dragStartHandler);
			mouse.pointDragged().subscribe(pointDraggedHandler);
			mouse.dragEnded().subscribe(dragEndHandler);

			mouse.setProjectedPoints([
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				}
			]);

			// Mouse down on point
			const downEvent = new MouseEvent('mousedown', {
				clientX: 100,
				clientY: 200
			});
			mockData.mockChartElement.dispatchEvent(downEvent);

			expect(mouse.isDragging()).toBe(true);
			expect(dragStartHandler).toHaveBeenCalledWith({
				tool: 'retracement',
				pointIndex: 0
			});
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: false }
			});

			// Drag move
			const dragMoveEvent = new MouseEvent('mousemove', {
				clientX: 150,
				clientY: 250
			});
			mockData.mockChartElement.dispatchEvent(dragMoveEvent);

			expect(pointDraggedHandler).toHaveBeenCalledWith(
				expect.objectContaining({
					tool: 'retracement',
					pointIndex: 0,
					x: 150,
					y: 250
				})
			);

			// Mouse up
			const upEvent = new MouseEvent('mouseup', {
				clientX: 150,
				clientY: 250
			});
			mockData.mockChartElement.dispatchEvent(upEvent);

			expect(mouse.isDragging()).toBe(false);
			expect(dragEndHandler).toHaveBeenCalledWith({
				tool: 'retracement',
				pointIndex: 0
			});
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: true }
			});
		});

		it('dispatches chartClicked in drawing mode and pointClicked outside drawing mode', () => {
			const chartClickHandler = vi.fn();
			const pointClickHandler = vi.fn();

			mouse.chartClicked().subscribe(chartClickHandler);
			mouse.pointClicked().subscribe(pointClickHandler);

			mouse.setProjectedPoints([
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				}
			]);

			// 1. Drawing mode click
			mouse.setDrawingMode(true);
			const drawClick = new MouseEvent('click', { clientX: 200, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(drawClick);
			expect(chartClickHandler).toHaveBeenCalled();
			expect(pointClickHandler).not.toHaveBeenCalled();

			// 2. Normal mode click on anchor handle
			mouse.setDrawingMode(false);
			chartClickHandler.mockClear();
			const handleNodeClick = new MouseEvent('click', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(handleNodeClick);
			expect(pointClickHandler).toHaveBeenCalledWith({
				tool: 'retracement',
				pointIndex: 0,
				point: { time: '2024-01-05', price: 160 }
			});
			expect(chartClickHandler).not.toHaveBeenCalled();
		});

		it('dispatches emptyAreaClicked on plot area click outside anchor handles', () => {
			const emptyAreaHandler = vi.fn();
			const pointClickHandler = vi.fn();

			mouse.emptyAreaClicked().subscribe(emptyAreaHandler);
			mouse.pointClicked().subscribe(pointClickHandler);

			mouse.setProjectedPoints([
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				}
			]);

			// Click on empty space (x: 400, y: 300)
			const emptyClick = new MouseEvent('click', { clientX: 400, clientY: 300 });
			mockData.mockChartElement.dispatchEvent(emptyClick);

			expect(emptyAreaHandler).toHaveBeenCalledTimes(1);
			expect(pointClickHandler).not.toHaveBeenCalled();
		});

		it('suppresses click firing when a drag gesture occurred', () => {
			const pointClickHandler = vi.fn();
			const emptyAreaHandler = vi.fn();

			mouse.pointClicked().subscribe(pointClickHandler);
			mouse.emptyAreaClicked().subscribe(emptyAreaHandler);

			mouse.setProjectedPoints([
				{
					tool: 'retracement',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: '2024-01-05' as Time, price: 160 }
				}
			]);

			// Mouse down
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			// Drag move
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);
			// Mouse up
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			// Subsequent click event from browser
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 150, clientY: 250 })
			);

			expect(pointClickHandler).not.toHaveBeenCalled();
			expect(emptyAreaHandler).not.toHaveBeenCalled();
		});

		describe('hitTestLine', () => {
			it('registers a hit inside [xStart, xEnd] within HIT_TEST_RADIUS', () => {
				const lines: ProjectedFibLine[] = [{ tool: 'retracement', xStart: 100, xEnd: 300, y: 200 }];
				mouse.setProjectedLines(lines);

				// Exactly on the line
				expect(mouse.hitTestLine(200, 200)?.tool).toBe('retracement');
				// Within HIT_TEST_RADIUS vertically
				expect(mouse.hitTestLine(200, 200 + HIT_TEST_RADIUS)?.tool).toBe('retracement');
				expect(mouse.hitTestLine(200, 200 - HIT_TEST_RADIUS)?.tool).toBe('retracement');
				// At start and end boundary
				expect(mouse.hitTestLine(100, 200)?.tool).toBe('retracement');
				expect(mouse.hitTestLine(300, 200)?.tool).toBe('retracement');
				// Near endpoints within HIT_TEST_RADIUS
				expect(mouse.hitTestLine(95, 200)?.tool).toBe('retracement');
				expect(mouse.hitTestLine(305, 200)?.tool).toBe('retracement');
			});

			it('misses beyond vertical HIT_TEST_RADIUS or horizontal ends', () => {
				const lines: ProjectedFibLine[] = [{ tool: 'retracement', xStart: 100, xEnd: 300, y: 200 }];
				mouse.setProjectedLines(lines);

				// Beyond vertical radius
				expect(mouse.hitTestLine(200, 200 + HIT_TEST_RADIUS + 1)).toBeNull();
				expect(mouse.hitTestLine(200, 200 - HIT_TEST_RADIUS - 1)).toBeNull();
				// Far beyond horizontal ends
				expect(mouse.hitTestLine(70, 200)).toBeNull();
				expect(mouse.hitTestLine(330, 200)).toBeNull();
			});

			it('distinguishes between retracement and extension lines and resolves closest line', () => {
				const lines: ProjectedFibLine[] = [
					{ tool: 'retracement', xStart: 100, xEnd: 300, y: 150 },
					{ tool: 'extension', xStart: 200, xEnd: 400, y: 250 }
				];
				mouse.setProjectedLines(lines);

				// Query near retracement line
				const hitRetracement = mouse.hitTestLine(150, 153);
				expect(hitRetracement).not.toBeNull();
				expect(hitRetracement?.tool).toBe('retracement');

				// Query near extension line
				const hitExtension = mouse.hitTestLine(250, 248);
				expect(hitExtension).not.toBeNull();
				expect(hitExtension?.tool).toBe('extension');
			});
		});
	});

	describe('FibonacciPaneRenderer', () => {
		let renderer: FibonacciPaneRenderer;
		let mockCanvas: ReturnType<typeof createMockCanvasTarget>;

		beforeEach(() => {
			renderer = new FibonacciPaneRenderer();
			mockCanvas = createMockCanvasTarget();
		});

		it('renders connecting trendlines, horizontal level lines, labels, and handles for Retracement', () => {
			const renderData: FibonacciRendererData = {
				retracement: {
					p1: { pointIndex: 0, x: 100, y: 300, time: '2024-01-05' as Time, price: 140 },
					p2: { pointIndex: 1, x: 250, y: 100, time: '2024-01-11' as Time, price: 180 },
					levels: [
						{ ratio: 0.0, price: 180, y: 100, formattedPrice: '180.00', label: '0.0 (180.00)' },
						{ ratio: 0.5, price: 160, y: 200, formattedPrice: '160.00', label: '0.5 (160.00)' },
						{ ratio: 1.0, price: 140, y: 300, formattedPrice: '140.00', label: '1.0 (140.00)' }
					],
					isSelected: true
				},
				extension: null,
				preview: null
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).toHaveBeenCalled();

			// Check canvas calls
			const lineToCalls = mockCanvas.drawCalls.filter((c) => c.type === 'lineTo');
			expect(lineToCalls.length).toBeGreaterThanOrEqual(4); // Trendline + horizontal level lines

			const fillTextCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(fillTextCalls.length).toBe(3); // 3 level labels
			expect(fillTextCalls[0].args[0]).toBe('0.0 (180.00)');

			const arcCalls = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBe(2); // 2 anchor handles (P1, P2)
		});

		it('renders connecting trendlines, level lines, labels, and handles for Extension', () => {
			const renderData: FibonacciRendererData = {
				retracement: null,
				extension: {
					p1: { pointIndex: 0, x: 100, y: 300, time: '2024-01-05' as Time, price: 140 },
					p2: { pointIndex: 1, x: 250, y: 100, time: '2024-01-11' as Time, price: 180 },
					p3: { pointIndex: 2, x: 350, y: 200, time: '2024-01-15' as Time, price: 160 },
					levels: [
						{ ratio: 0.0, price: 160, y: 200, formattedPrice: '160.00', label: '0.0 (160.00)' },
						{ ratio: 1.0, price: 200, y: 0, formattedPrice: '200.00', label: '1.0 (200.00)' }
					],
					isSelected: true
				},
				preview: null
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			const fillTextCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(fillTextCalls.length).toBe(2);

			const arcCalls = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBe(3); // 3 anchor handles (P1, P2, P3)
		});

		it('renders drawing preview ghost lines, ghost levels, and ghost badge', () => {
			const renderData: FibonacciRendererData = {
				retracement: null,
				extension: null,
				preview: {
					tool: 'retracement',
					placedPoints: [{ pointIndex: 0, x: 100, y: 300, time: '2024-01-05' as Time, price: 140 }],
					currentMouse: { x: 200, y: 150, time: '2024-01-09' as Time, price: 170 },
					previewLevels: [
						{ ratio: 0.5, price: 155, y: 225, formattedPrice: '155.00', label: '0.5 (155.00)' }
					]
				}
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			const arcCalls = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			// Placed P1 handle + Ghost cursor handle
			expect(arcCalls.length).toBe(2);

			const fillTextCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(fillTextCalls.length).toBe(1);
			expect(fillTextCalls[0].args[0]).toBe('0.5 (155.00)');
		});

		it('renders full-width horizontal dashed crosshair guide line when drawing preview currentMouse is present', () => {
			const renderData: FibonacciRendererData = {
				retracement: null,
				extension: null,
				preview: {
					tool: 'retracement',
					placedPoints: [],
					currentMouse: { x: 200, y: 150, time: '2024-01-09' as Time, price: 170 },
					previewLevels: []
				}
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			const dashCalls = mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash');
			expect(dashCalls.length).toBeGreaterThanOrEqual(1);

			const vpr = mockCanvas.scope.verticalPixelRatio;
			const moveToCalls = mockCanvas.drawCalls.filter(
				(c) => c.type === 'moveTo' && c.args[0] === 0 && c.args[1] === 150 * vpr
			);
			const lineToCalls = mockCanvas.drawCalls.filter(
				(c) =>
					c.type === 'lineTo' &&
					c.args[0] === mockCanvas.scope.bitmapSize.width &&
					c.args[1] === 150 * vpr
			);
			expect(moveToCalls).toHaveLength(1);
			expect(lineToCalls).toHaveLength(1);
		});

		it('renders hover and drag rings on active anchor handles', () => {
			const renderData: FibonacciRendererData = {
				retracement: {
					p1: {
						pointIndex: 0,
						x: 100,
						y: 300,
						time: '2024-01-05' as Time,
						price: 140,
						isHovered: true
					},
					p2: {
						pointIndex: 1,
						x: 250,
						y: 100,
						time: '2024-01-11' as Time,
						price: 180,
						isDragging: true
					},
					levels: []
				},
				extension: null,
				preview: null
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			const arcCalls = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			// Each handle with hover/drag gets 1 ring + 1 circle = 4 arc calls
			expect(arcCalls.length).toBe(4);
		});

		it('renders selection ring around anchor handles when drawing is selected', () => {
			const renderData: FibonacciRendererData = {
				retracement: {
					p1: {
						pointIndex: 0,
						x: 100,
						y: 300,
						time: '2024-01-05' as Time,
						price: 140,
						isSelected: true
					},
					p2: {
						pointIndex: 1,
						x: 250,
						y: 100,
						time: '2024-01-11' as Time,
						price: 180,
						isSelected: true
					},
					levels: [],
					isSelected: true
				},
				extension: null,
				preview: null
			};

			renderer.update(renderData);
			renderer.draw(mockCanvas.target);

			const arcCalls = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			// Each selected handle gets 1 selection ring + 1 circle = 4 arc calls
			expect(arcCalls.length).toBe(4);
		});
	});

	describe('FibonacciPrimitive Integration', () => {
		let primitive: FibonacciPrimitive;
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let mockRequestUpdate: () => void;

		beforeEach(() => {
			primitive = new FibonacciPrimitive();
			mockData = createMockChartAndSeries();
			mockRequestUpdate = vi.fn();
			primitive.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: mockRequestUpdate,
				horzScaleBehavior: {} as never
			});
			primitive.setCandles(createDailyCandles(30));
		});

		it('conforms to ISeriesPrimitive and exposes paneViews with top z-order', () => {
			const views = primitive.paneViews();
			expect(views).toHaveLength(1);
			expect(views[0]?.zOrder?.()).toBe('top');
			expect(views[0]).toBeInstanceOf(FibonacciPaneView);
		});

		it('initializes selectedTool from constructor and updates via setSelectedTool', () => {
			const defaultPrimitive = new FibonacciPrimitive();
			expect(defaultPrimitive.getSelectedTool()).toBeNull();

			const selectedPrimitive = new FibonacciPrimitive({ selectedTool: 'extension' });
			expect(selectedPrimitive.getSelectedTool()).toBe('extension');

			selectedPrimitive.setSelectedTool('retracement');
			expect(selectedPrimitive.getSelectedTool()).toBe('retracement');

			selectedPrimitive.setSelectedTool(null);
			expect(selectedPrimitive.getSelectedTool()).toBeNull();
		});

		it('selects tool on point click and deselects on empty space click', () => {
			primitive.setRetracement({
				p1: { time: '2024-01-05' as Time, price: 160 },
				p2: { time: '2024-01-13' as Time, price: 170 }
			});
			primitive.updateAllViews();

			expect(primitive.getSelectedTool()).toBeNull();

			// Click on retracement P1 (x: 100, y: 200)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(primitive.getSelectedTool()).toBe('retracement');

			// Click on empty space (x: 400, y: 300)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 400, clientY: 300 })
			);
			expect(primitive.getSelectedTool()).toBeNull();
		});

		it('fires selectionChanged subscription when selected tool changes', () => {
			const onSelectionChanged = vi.fn();
			primitive.selectionChanged().subscribe(onSelectionChanged);

			primitive.setSelectedTool('retracement');
			expect(onSelectionChanged).toHaveBeenCalledWith('retracement');

			primitive.setSelectedTool(null);
			expect(onSelectionChanged).toHaveBeenCalledWith(null);
		});

		it('updates cursor styling and hitTest based on mode and interaction state', () => {
			// Default: no cursor override
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();

			// Drawing mode: crosshair
			primitive.setDrawingMode(true);
			primitive.updateAllViews();
			expect(primitive.hitTest()).toEqual({
				cursorStyle: 'crosshair',
				externalId: 'fibonacci-primitive',
				zOrder: 'top'
			});

			primitive.setDrawingMode(false);

			// Add a drawing so we have anchor points
			primitive.setRetracement({
				p1: { time: '2024-01-05' as Time, price: 160 },
				p2: { time: '2024-01-13' as Time, price: 170 }
			});
			primitive.updateAllViews();

			// Hover anchor P1 at x=100, y=200
			const hoverMove = new MouseEvent('mousemove', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(hoverMove);
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('grab');

			// Drag anchor P1
			const downEvent = new MouseEvent('mousedown', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(downEvent);
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('grabbing');

			// Release
			const upEvent = new MouseEvent('mouseup', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(upEvent);
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('grab');
		});

		it('supports interactive 2-point drawing via chart clicks', () => {
			primitive.setActiveTool('retracement');
			primitive.setDrawingMode(true);

			// Click point 1 (day 5 -> x=100, y=200 -> price=160, snaps to high=114)
			const click1 = new MouseEvent('click', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(click1);
			expect(primitive.isDrawingMode()).toBe(true);

			// Click point 2 (day 13 -> x=300, y=100 -> price=180, snaps to high=122)
			const click2 = new MouseEvent('click', { clientX: 300, clientY: 100 });
			mockData.mockChartElement.dispatchEvent(click2);

			expect(primitive.isDrawingMode()).toBe(false);
			const retracement = primitive.getRetracement();
			expect(retracement).not.toBeNull();
			expect(retracement?.p1.price).toBe(114);
			expect(retracement?.p2.price).toBe(122);
		});

		it('supports dragging anchor handles to reposition drawing in real time', () => {
			primitive.setRetracement({
				p1: { time: '2024-01-05' as Time, price: 160 },
				p2: { time: '2024-01-13' as Time, price: 170 }
			});
			primitive.updateAllViews();

			// Mousedown on P1 (x=100, y=200)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);

			// Drag P1 to x=150 (day 7), y=250 (price=150, snaps to high=116)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			expect(primitive.getRetracement()?.p1.price).toBe(116);
			expect(primitive.getRetracement()?.p1.time).toBe('2024-01-07');

			// Mouseup
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			expect(primitive.getDraggingPoint()).toBeNull();
		});

		it('discards pending retracement points and exits drawing mode on Escape', () => {
			primitive.setActiveTool('retracement');
			primitive.setDrawingMode(true);

			// Click 1 point
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(primitive.getPendingPoints()).toHaveLength(1);
			expect(primitive.isDrawingMode()).toBe(true);

			// Press Escape
			window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }));

			expect(primitive.isDrawingMode()).toBe(false);
			expect(primitive.getPendingPoints()).toHaveLength(0);
			expect(primitive.getRetracement()).toBeNull();
		});

		it('discards pending extension points and exits drawing mode on right-click (contextmenu)', () => {
			primitive.setActiveTool('extension');
			primitive.setDrawingMode(true);

			// Click 2 points
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 150, clientY: 250 })
			);
			expect(primitive.getPendingPoints()).toHaveLength(2);
			expect(primitive.isDrawingMode()).toBe(true);

			// Right-click
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('contextmenu', {
					clientX: 200,
					clientY: 200,
					cancelable: true,
					bubbles: true
				})
			);

			expect(primitive.isDrawingMode()).toBe(false);
			expect(primitive.getPendingPoints()).toHaveLength(0);
			expect(primitive.getExtension()).toBeNull();
		});

		it('snaps drawing preview mouse position to candle wick and toggles crosshair in drawing mode', () => {
			primitive.setDrawingMode(true);

			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				crosshair: { horzLine: { visible: false, labelVisible: false } }
			});

			// Mousemove over day 5 (clientX: 100, clientY: 200 -> snaps to high 114)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);

			primitive.updateAllViews();
			const paneView = primitive.paneViews()[0];
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			const rendererData = (paneView.renderer() as any)._data;
			expect(rendererData.preview.currentMouse.y).toBe(mockData.series.priceToCoordinate(114));

			primitive.setDrawingMode(false);
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				crosshair: { horzLine: { visible: true, labelVisible: true } }
			});
		});

		it('cleans up handlers and subscriptions on detached and destroy', () => {
			primitive.detached();
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();

			primitive.destroy();
		});

		it('selects retracement tool when clicking along a horizontal level line', () => {
			primitive.setRetracement({
				p1: { time: '2024-01-05' as Time, price: 160 }, // x: 100, y: 200
				p2: { time: '2024-01-13' as Time, price: 170 } // x: 300, y: 150
			});
			primitive.updateAllViews();

			expect(primitive.getSelectedTool()).toBeNull();

			// Level 0.5 is at price 165 (y: 175)
			// Retracement level line extends from xStart = Math.max(100, 300) = 300 to xEnd = 300 + 200 = 500
			// Click at x: 400, y: 175 (along the line, away from anchor handles at 100,200 and 300,150)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 400, clientY: 175 })
			);

			expect(primitive.getSelectedTool()).toBe('retracement');
		});

		it('selects extension tool when clicking along a horizontal level line and deselects on empty area', () => {
			primitive.setExtension({
				p1: { time: '2024-01-05' as Time, price: 180 }, // x: 100, y: 100
				p2: { time: '2024-01-09' as Time, price: 160 }, // x: 200, y: 200 (move = -20)
				p3: { time: '2024-01-13' as Time, price: 170 } // x: 300, y: 150
			});
			primitive.updateAllViews();

			expect(primitive.getSelectedTool()).toBeNull();

			// Level 2.0 is enabled by default: price = 170 + 2.0 * (-20) = 130 (y: (200 - 130) / 0.2 = 350)
			// Extension level line starts at p3.x = 300, extends rightward by 2 * |300 - 100| = 400 to xEnd = 700
			// Click at x: 450, y: 350 (along the level 2.0 line)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 450, clientY: 350 })
			);

			expect(primitive.getSelectedTool()).toBe('extension');

			// Click on empty space (x: 50, y: 50) deselects
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 50, clientY: 50 })
			);

			expect(primitive.getSelectedTool()).toBeNull();
		});

		it('gives anchor handle interaction precedence over level line selection', () => {
			primitive.setRetracement({
				p1: { time: '2024-01-05' as Time, price: 160 },
				p2: { time: '2024-01-13' as Time, price: 170 }
			});
			primitive.updateAllViews();

			// Click directly on P2 anchor handle (x: 300, y: 150)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 300, clientY: 150 })
			);

			// Selected tool should still be retracement (via pointClicked)
			expect(primitive.getSelectedTool()).toBe('retracement');
		});

		it('renders only 3 level lines and 3 labels (1.618, 2.0, 2.618) by default for newly created extension drawings', () => {
			const mockCanvas = createMockCanvasTarget();
			primitive.setExtension({
				p1: { time: '2024-01-05' as Time, price: 180 },
				p2: { time: '2024-01-09' as Time, price: 160 },
				p3: { time: '2024-01-13' as Time, price: 170 }
			});
			primitive.updateAllViews();

			const views = primitive.paneViews();
			const renderer = views[0]?.renderer();
			expect(renderer).toBeDefined();

			renderer?.draw(mockCanvas.target);

			// Labels rendered via fillText
			const fillTextCalls = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(fillTextCalls).toHaveLength(3);

			const labelTexts = fillTextCalls.map((c) => c.args[0] as string);
			expect(labelTexts.some((t) => t.startsWith('1.618'))).toBe(true);
			expect(labelTexts.some((t) => t.startsWith('2.0') || t.startsWith('2 ('))).toBe(true);
			expect(labelTexts.some((t) => t.startsWith('2.618'))).toBe(true);

			// Disabled default levels (0, 0.382, 0.5, 0.618, 1.0, 1.272, 3.618, 4.236) must not be rendered
			expect(labelTexts.some((t) => t.startsWith('0.382'))).toBe(false);
			expect(labelTexts.some((t) => t.startsWith('0.5'))).toBe(false);
			expect(labelTexts.some((t) => t.startsWith('0.618'))).toBe(false);
			expect(labelTexts.some((t) => t.startsWith('1.0') || t.startsWith('1 ('))).toBe(false);
		});

		it('renders level lines and labels and supports hit testing when projecting into future coordinates past the last candle', () => {
			// Provide 20 historical candles (day 1 to 20; day 20 is at x = 19 * 25 = 475)
			primitive.setCandles(createDailyCandles(20));

			// Place retracement: P1 at day 10 (x: 225, price: 160 -> y: 200), P2 at day 20 (x: 475, price: 180 -> y: 100)
			// Level lines start at xStart = 475 (the last candle) and project rightward by 1x (250px) to xEnd = 725
			// The span [475, 725] is completely in future coordinate space!
			primitive.setRetracement({
				p1: { time: '2024-01-10' as Time, price: 160 },
				p2: { time: '2024-01-20' as Time, price: 180 }
			});
			primitive.updateAllViews();

			expect(primitive.getSelectedTool()).toBeNull();

			// Level 0.5 is at price 170 (y: 150)
			// Click at x: 600 (well past the last candle at x: 475), y: 150
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 600, clientY: 150 })
			);

			expect(primitive.getSelectedTool()).toBe('retracement');

			// Also verify canvas drawing receives future bounds
			const mockCanvas = createMockCanvasTarget();
			const views = primitive.paneViews();
			const renderer = views[0]?.renderer();
			renderer?.draw(mockCanvas.target);

			const hpr = mockCanvas.scope.horizontalPixelRatio;
			// Check that lineTo / moveTo coordinates project past 475 * hpr up to 725 * hpr
			const lineToCalls = mockCanvas.drawCalls.filter((c) => c.type === 'lineTo');
			const reachesFutureEnd = lineToCalls.some((c) => c.args[0] === 725 * hpr);
			expect(reachesFutureEnd).toBe(true);
		});
	});
});
