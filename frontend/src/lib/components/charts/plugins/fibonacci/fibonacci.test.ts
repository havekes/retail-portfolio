import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import type { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';
import {
	FibonacciPrimitive,
	FibonacciToolState,
	FibonacciPaneRenderer,
	FibonacciPaneView,
	MouseHandlers,
	HIT_TEST_RADIUS,
	HANDLE_RADIUS,
	PREVIEW_ALPHA,
	DEFAULT_HANDLE_COLOR,
	DEFAULT_TRENDLINE_COLOR,
	type FibPointTarget,
	type ProjectedFibPointWithTarget,
	type FibonacciRendererData
} from './index';
import type { Candle } from '$lib/utils/finance/candle';
import { TimeProjector } from '../elliott-wave/time-projector';

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
					]
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
					]
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

			// Click point 1 (day 5 -> x=100, y=200 -> price=160)
			const click1 = new MouseEvent('click', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(click1);
			expect(primitive.isDrawingMode()).toBe(true);

			// Click point 2 (day 13 -> x=300, y=100 -> price=180)
			const click2 = new MouseEvent('click', { clientX: 300, clientY: 100 });
			mockData.mockChartElement.dispatchEvent(click2);

			expect(primitive.isDrawingMode()).toBe(false);
			const retracement = primitive.getRetracement();
			expect(retracement).not.toBeNull();
			expect(retracement?.p1.price).toBe(160);
			expect(retracement?.p2.price).toBe(180);
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

			// Drag P1 to x=150 (day 7), y=250 (price=150)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			expect(primitive.getRetracement()?.p1.price).toBe(150);
			expect(primitive.getRetracement()?.p1.time).toBe('2024-01-07');

			// Mouseup
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			expect(primitive.getDraggingPoint()).toBeNull();
		});

		it('cleans up handlers and subscriptions on detached and destroy', () => {
			primitive.detached();
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();

			primitive.destroy();
		});
	});
});
