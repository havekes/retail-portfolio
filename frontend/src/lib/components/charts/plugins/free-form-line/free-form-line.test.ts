import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import type { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';
import {
	FreeFormLinePrimitive,
	LineToolState,
	LinePaneRenderer,
	LinePaneView,
	MouseHandlers,
	HIT_TEST_RADIUS,
	HANDLE_RADIUS,
	FREE_FORM_LINE_COLOR,
	DEFAULT_HANDLE_COLOR,
	type LinePointTarget,
	type LineRendererData,
	type ProjectedLinePointWithTarget
} from './index';
import type { Candle } from '$lib/utils/finance/candle';
import { TimeProjector } from '../helpers/time/time-projector';

/** Canonical epoch-seconds anchor for an ISO date. */
const anchor = (date: string): Time =>
	Math.floor(new Date(`${date}T00:00:00Z`).getTime() / 1000) as Time;

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
		coordinateToLogical: vi.fn((x: number) => (x < 0 || x > 1500 ? null : x / 25)),
		logicalToCoordinate: vi.fn((logical: number) => logical * 25),
		height: vi.fn(() => 30),
		width: vi.fn(() => 750)
	};

	const priceScale = { width: vi.fn(() => 50), applyOptions: vi.fn() };

	const series = {
		coordinateToPrice: vi.fn((y: number) => (y < 0 || y > 470 ? null : 200 - y * 0.2)),
		priceToCoordinate: vi.fn((price: number) =>
			price < 0 || price > 500 ? null : (200 - price) / 0.2
		),
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

interface DrawCall {
	type: string;
	args: unknown[];
	color?: string;
}

function createMockCanvasTarget() {
	const drawCalls: DrawCall[] = [];
	const styles = { strokeStyle: '', fillStyle: '' };

	const context = {
		save() {},
		restore() {},
		beginPath() {},
		moveTo(x: number, y: number) {
			drawCalls.push({ type: 'moveTo', args: [x, y] });
		},
		lineTo(x: number, y: number) {
			drawCalls.push({ type: 'lineTo', args: [x, y] });
		},
		arc(...args: unknown[]) {
			drawCalls.push({ type: 'arc', args });
		},
		fill() {
			drawCalls.push({ type: 'fill', args: [], color: styles.fillStyle });
		},
		stroke() {
			drawCalls.push({ type: 'stroke', args: [], color: styles.strokeStyle });
		},
		fillRect(...args: unknown[]) {
			drawCalls.push({ type: 'fillRect', args, color: styles.fillStyle });
		},
		fillText(text: string, x: number, y: number) {
			drawCalls.push({ type: 'fillText', args: [text, x, y] });
		},
		setLineDash(dash: number[]) {
			drawCalls.push({ type: 'setLineDash', args: [dash] });
		},
		get strokeStyle() {
			return styles.strokeStyle;
		},
		set strokeStyle(value: string) {
			styles.strokeStyle = value;
		},
		get fillStyle() {
			return styles.fillStyle;
		},
		set fillStyle(value: string) {
			styles.fillStyle = value;
		},
		lineWidth: 1,
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

function createState() {
	let counter = 0;
	return new LineToolState(() => `line-${++counter}`);
}

describe('Free-form Line Plugin', () => {
	describe('Constants', () => {
		it('defines expected visual constants', () => {
			expect(HIT_TEST_RADIUS).toBe(14);
			expect(HANDLE_RADIUS).toBe(5);
			expect(FREE_FORM_LINE_COLOR).toBe('#2962FF');
			expect(DEFAULT_HANDLE_COLOR).toBe('#2962FF');
		});
	});

	describe('LineToolState', () => {
		let state: LineToolState;

		beforeEach(() => {
			state = createState();
		});

		it('initializes with no lines, no pending points and drawing mode off', () => {
			expect(state.getLines()).toEqual([]);
			expect(state.getPendingPoints()).toEqual([]);
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getSelectedId()).toBeNull();
		});

		it('setLines normalizes anchors to epoch seconds and assigns ids', () => {
			state.setLines([
				{
					id: undefined,
					p1: { time: '2024-01-01' as Time, price: 100 },
					p2: { time: '2024-01-02' as Time, price: 120 }
				}
			]);

			const lines = state.getLines();
			expect(lines).toHaveLength(1);
			expect(lines[0].id).toBe('line-1');
			expect(lines[0].p1.time).toBe(anchor('2024-01-01'));
			expect(lines[0].p2.time).toBe(anchor('2024-01-02'));
		});

		it('preserves existing ids across setLines and clears stale selection', () => {
			state.setLines([
				{
					id: 'keep-me',
					p1: { time: anchor('2024-01-01'), price: 100 },
					p2: { time: anchor('2024-01-02'), price: 110 }
				}
			]);
			state.select('keep-me');
			expect(state.getSelectedId()).toBe('keep-me');

			state.setLines([]);
			expect(state.getSelectedId()).toBeNull();
		});

		it('completes a two-click drawing with a generated id and exits drawing mode', () => {
			const drawingsHandler = vi.fn();
			const modeHandler = vi.fn();
			state.drawingsChanged().subscribe(drawingsHandler);
			state.drawingModeChanged().subscribe(modeHandler);

			state.setDrawingMode(true);
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			expect(state.getPendingPoints()).toHaveLength(1);
			expect(state.getLines()).toHaveLength(0);

			state.addPoint({ time: '2024-01-10' as Time, price: 180 });

			expect(state.isDrawingMode()).toBe(false);
			expect(state.getPendingPoints()).toHaveLength(0);
			expect(modeHandler).toHaveBeenCalledWith(false);
			const lines = state.getLines();
			expect(lines).toHaveLength(1);
			expect(lines[0].id).toBe('line-1');
			expect(lines[0].p1).toEqual({ time: anchor('2024-01-01'), price: 100 });
			expect(lines[0].p2).toEqual({ time: anchor('2024-01-10'), price: 180 });
			expect(drawingsHandler).toHaveBeenCalled();
		});

		it('keeps multiple lines coexisting with unique ids', () => {
			state.setDrawingMode(true);
			state.addPoint({ time: anchor('2024-01-01'), price: 100 });
			state.addPoint({ time: anchor('2024-01-05'), price: 120 });
			state.setDrawingMode(true);
			state.addPoint({ time: anchor('2024-01-06'), price: 130 });
			state.addPoint({ time: anchor('2024-01-09'), price: 110 });

			const lines = state.getLines();
			expect(lines).toHaveLength(2);
			expect(lines[0].id).not.toBe(lines[1].id);
		});

		it('updatePoint repositions either endpoint in time and price', () => {
			state.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-01'), price: 100 },
					p2: { time: anchor('2024-01-02'), price: 110 }
				}
			]);

			expect(state.updatePoint('l1', 1, { time: '2024-01-03' as Time, price: 130 })).toBe(true);
			let line = state.getLines()[0];
			expect(line.p1.price).toBe(100);
			expect(line.p2.price).toBe(130);
			expect(line.p2.time).toBe(anchor('2024-01-03'));

			expect(state.updatePoint('l1', 0, { time: '2024-01-04' as Time, price: 90 })).toBe(true);
			line = state.getLines()[0];
			expect(line.p1.price).toBe(90);
			expect(line.p1.time).toBe(anchor('2024-01-04'));

			expect(state.updatePoint('missing', 0, { price: 1 })).toBe(false);
		});

		it('removeDrawing deletes by id and clears selection, drag and hover targets', () => {
			state.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-01'), price: 100 },
					p2: { time: anchor('2024-01-02'), price: 110 }
				},
				{
					id: 'l2',
					p1: { time: anchor('2024-01-03'), price: 120 },
					p2: { time: anchor('2024-01-04'), price: 130 }
				}
			]);
			state.select('l1');
			state.setDraggingPoint({ id: 'l1', pointIndex: 0 });
			state.setHoveredPoint({ id: 'l1', pointIndex: 1 });

			expect(state.removeDrawing('l1')).toBe(true);
			expect(state.getLines()).toHaveLength(1);
			expect(state.getLines()[0].id).toBe('l2');
			expect(state.getSelectedId()).toBeNull();
			expect(state.getDraggingPoint()).toBeNull();
			expect(state.getHoveredPoint()).toBeNull();
			expect(state.removeDrawing('l1')).toBe(false);
		});

		it('selects only known ids and fires selectionChanged once per change', () => {
			const selectionHandler = vi.fn();
			state.selectionChanged().subscribe(selectionHandler);
			state.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-01'), price: 100 },
					p2: { time: anchor('2024-01-02'), price: 110 }
				}
			]);

			state.select('unknown');
			expect(selectionHandler).not.toHaveBeenCalled();

			state.select('l1');
			expect(state.getSelectedId()).toBe('l1');
			expect(selectionHandler).toHaveBeenCalledWith('l1');

			selectionHandler.mockClear();
			state.select('l1');
			expect(selectionHandler).not.toHaveBeenCalled();

			state.select(null);
			expect(selectionHandler).toHaveBeenCalledWith(null);
		});

		it('entering drawing mode clears the current selection', () => {
			state.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-01'), price: 100 },
					p2: { time: anchor('2024-01-02'), price: 110 }
				}
			]);
			state.select('l1');
			state.setDrawingMode(true);
			expect(state.getSelectedId()).toBeNull();
		});

		it('cancelDrawing discards pending points and exits drawing mode', () => {
			state.setDrawingMode(true);
			state.addPoint({ time: anchor('2024-01-01'), price: 100 });
			state.cancelDrawing();
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getPendingPoints()).toHaveLength(0);
			expect(state.getLines()).toHaveLength(0);
		});

		it('tracks hover and drag targets with delegate notifications', () => {
			const hoverHandler = vi.fn();
			const dragHandler = vi.fn();
			state.hoverChanged().subscribe(hoverHandler);
			state.dragChanged().subscribe(dragHandler);

			const target: LinePointTarget = { id: 'l1', pointIndex: 1 };
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

		beforeEach(() => {
			mouse = new MouseHandlers();
			mockData = createMockChartAndSeries();
			const timeProjector = new TimeProjector();
			timeProjector.attach(mockData.chart);
			timeProjector.updateCandles(createDailyCandles(30));
			mouse.attached(mockData.chart, mockData.series, timeProjector);
		});

		it('hit tests endpoints by drawing id and point index', () => {
			const points: ProjectedLinePointWithTarget[] = [
				{
					id: 'l1',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: anchor('2024-01-05'), price: 160 }
				},
				{
					id: 'l2',
					pointIndex: 1,
					x: 300,
					y: 150,
					originalPoint: { time: anchor('2024-01-13'), price: 170 }
				}
			];
			mouse.setProjectedPoints(points);

			expect(mouse.hitTestPoint(105, 203)?.id).toBe('l1');
			expect(mouse.hitTestPoint(305, 153)?.pointIndex).toBe(1);
			expect(mouse.hitTestPoint(105, 203 + HIT_TEST_RADIUS + 1)).toBeNull();
		});

		it('hit tests line segments within HIT_TEST_RADIUS', () => {
			mouse.setProjectedLines([
				{
					id: 'l1',
					p1: { x: 100, y: 200 },
					p2: { x: 300, y: 200 }
				}
			]);

			// Midpoint of segment at y=200
			expect(mouse.hitTestLine(200, 200)).toEqual({ id: 'l1', pointIndex: 0 });
			// Within HIT_TEST_RADIUS
			expect(mouse.hitTestLine(200, 200 + HIT_TEST_RADIUS - 1)).toEqual({
				id: 'l1',
				pointIndex: 0
			});
			// Outside HIT_TEST_RADIUS
			expect(mouse.hitTestLine(200, 200 + HIT_TEST_RADIUS + 2)).toBeNull();
		});

		it('fires hover, drag and click delegates with id-keyed targets', () => {
			const hoverHandler = vi.fn();
			const dragStartHandler = vi.fn();
			const pointDraggedHandler = vi.fn();
			const dragEndHandler = vi.fn();
			const pointClickHandler = vi.fn();

			mouse.pointHovered().subscribe(hoverHandler);
			mouse.dragStarted().subscribe(dragStartHandler);
			mouse.pointDragged().subscribe(pointDraggedHandler);
			mouse.dragEnded().subscribe(dragEndHandler);
			mouse.pointClicked().subscribe(pointClickHandler);

			mouse.setProjectedPoints([
				{
					id: 'l1',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: anchor('2024-01-05'), price: 160 }
				}
			]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);
			expect(hoverHandler).toHaveBeenCalledWith({ id: 'l1', pointIndex: 0 });

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(pointClickHandler).toHaveBeenCalledWith({
				id: 'l1',
				pointIndex: 0,
				point: { time: anchor('2024-01-05'), price: 160 }
			});

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			expect(mouse.isDragging()).toBe(true);
			expect(dragStartHandler).toHaveBeenCalledWith({ id: 'l1', pointIndex: 0 });

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);
			expect(pointDraggedHandler).toHaveBeenCalledWith(
				expect.objectContaining({ id: 'l1', pointIndex: 0, x: 150, y: 250 })
			);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			expect(mouse.isDragging()).toBe(false);
			expect(dragEndHandler).toHaveBeenCalledWith({ id: 'l1', pointIndex: 0 });
		});

		it('fires chartClicked in drawing mode instead of pointClicked', () => {
			const chartClickHandler = vi.fn();
			const pointClickHandler = vi.fn();
			mouse.chartClicked().subscribe(chartClickHandler);
			mouse.pointClicked().subscribe(pointClickHandler);
			mouse.setProjectedPoints([
				{
					id: 'l1',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: anchor('2024-01-05'), price: 160 }
				}
			]);

			mouse.setDrawingMode(true);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 200, clientY: 200 })
			);

			expect(chartClickHandler).toHaveBeenCalled();
			expect(pointClickHandler).not.toHaveBeenCalled();
		});

		it('cleans up projected points on detach', () => {
			mouse.setProjectedPoints([
				{
					id: 'l1',
					pointIndex: 0,
					x: 100,
					y: 200,
					originalPoint: { time: anchor('2024-01-05'), price: 160 }
				}
			]);
			mouse.detached();
			expect(mouse.hitTestPoint(100, 200)).toBeNull();
		});
	});

	describe('LinePaneRenderer', () => {
		let renderer: LinePaneRenderer;
		let mockCanvas: ReturnType<typeof createMockCanvasTarget>;

		beforeEach(() => {
			renderer = new LinePaneRenderer();
			mockCanvas = createMockCanvasTarget();
		});

		function renderData(
			options: { isSelected?: boolean; isHovered?: boolean } = {}
		): LineRendererData {
			return {
				lines: [
					{
						id: 'l1',
						p1: { pointIndex: 0, x: 100, y: 300, time: anchor('2024-01-01'), price: 100 },
						p2: { pointIndex: 1, x: 250, y: 100, time: anchor('2024-01-10'), price: 120 },
						isSelected: options.isSelected,
						isHovered: options.isHovered
					}
				],
				preview: null
			};
		}

		it('draws the straight segment and omits endpoint handles on resting lines', () => {
			renderer.update(renderData());
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).toHaveBeenCalled();
			const strokes = mockCanvas.drawCalls.filter((c) => c.type === 'stroke');
			expect(strokes.some((c) => c.color === FREE_FORM_LINE_COLOR)).toBe(true);
			// 0 arcs for resting line
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(0);
			const moves = mockCanvas.drawCalls.filter((c) => c.type === 'moveTo');
			expect(moves).toHaveLength(1);
		});

		it('skips invisible lines', () => {
			const data = renderData();
			data.lines[0].visible = false;
			renderer.update(data);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls.filter((c) => c.type === 'stroke')).toHaveLength(0);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(0);
		});

		it('draws hover and drag rings exclusively on the active endpoint handles', () => {
			const data = renderData();
			data.lines[0].p1.isHovered = true;
			data.lines[0].p2.isDragging = true;
			renderer.update(data);
			renderer.draw(mockCanvas.target);

			// 2 handles + 2 rings = 4 arcs
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(4);

			// When only p1 is hovered, only p1 gets a ring: 2 handles + 1 ring = 3 arcs
			const dataOneHover = renderData();
			dataOneHover.lines[0].p1.isHovered = true;
			mockCanvas = createMockCanvasTarget();
			renderer.update(dataOneHover);
			renderer.draw(mockCanvas.target);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(3);
		});

		it('draws both endpoint handles without rings when line is hovered (2 arcs)', () => {
			renderer.update(renderData({ isHovered: true }));
			renderer.draw(mockCanvas.target);

			// 2 handles, 0 rings = 2 arcs
			const arcs = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			expect(arcs).toHaveLength(2);
			expect(mockCanvas.context.fillStyle).toBe('#2962FF');
		});

		it('draws both endpoint handles with blue fill, white border, radius 5 without rings when selected', () => {
			renderer.update(renderData({ isSelected: true }));
			renderer.draw(mockCanvas.target);

			const arcs = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			// 2 handles, 0 rings
			expect(arcs).toHaveLength(2);
			expect(arcs[0].args[2]).toBe(HANDLE_RADIUS * 2);
			expect(arcs[1].args[2]).toBe(HANDLE_RADIUS * 2);
			expect(mockCanvas.context.fillStyle).toBe('#2962FF');
			expect(mockCanvas.context.strokeStyle).toBe('#ffffff');
		});

		it('draws a dashed live preview segment and ghost handle between the placed point and the cursor', () => {
			const data: LineRendererData = {
				lines: [],
				preview: {
					placedPoints: [{ pointIndex: 0, x: 100, y: 300, time: anchor('2024-01-01'), price: 100 }],
					currentMouse: { x: 250, y: 100, time: anchor('2024-01-10'), price: 120 }
				}
			};
			renderer.update(data);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash')).toHaveLength(1);
			// Placed handle + ghost cursor handle.
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(2);
		});

		it('draws only the placed handle when the preview has no cursor position yet', () => {
			const data: LineRendererData = {
				lines: [],
				preview: {
					placedPoints: [{ pointIndex: 0, x: 100, y: 300, time: anchor('2024-01-01'), price: 100 }],
					currentMouse: null
				}
			};
			renderer.update(data);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(1);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash')).toHaveLength(0);
		});

		it('draws nothing when data is null', () => {
			renderer.update(null);
			renderer.draw(mockCanvas.target);
			expect(mockCanvas.drawCalls).toHaveLength(0);
		});
	});

	describe('FreeFormLinePrimitive Integration', () => {
		let primitive: FreeFormLinePrimitive;
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let mockRequestUpdate: () => void;

		beforeEach(() => {
			primitive = new FreeFormLinePrimitive();
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

		it('conforms to ISeriesPrimitive and exposes a top z-order pane view', () => {
			const views = primitive.paneViews();
			expect(views).toHaveLength(1);
			expect(views[0]?.zOrder?.()).toBe('top');
			expect(views[0]).toBeInstanceOf(LinePaneView);
		});

		it('initializes lines, drawing mode and selection from the constructor', () => {
			const seeded = new FreeFormLinePrimitive({
				lines: [
					{
						id: 'l1',
						p1: { time: anchor('2024-01-01'), price: 100 },
						p2: { time: anchor('2024-01-02'), price: 110 }
					}
				],
				isDrawingMode: true,
				selectedId: 'l1'
			});

			expect(seeded.getLines()).toHaveLength(1);
			expect(seeded.isDrawingMode()).toBe(true);
			expect(seeded.getSelectedId()).toBe('l1');
		});

		it('supports interactive two-click drawing via chart clicks', () => {
			primitive.setDrawingMode(true);
			primitive.updateAllViews();

			// Click day 5 at price 160
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(primitive.isDrawingMode()).toBe(true);
			expect(primitive.getLines()).toHaveLength(0);

			// Click day 13 at price 180 completes the line
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 300, clientY: 100 })
			);
			expect(primitive.isDrawingMode()).toBe(false);

			const lines = primitive.getLines();
			expect(lines).toHaveLength(1);
			expect(lines[0].p1).toEqual({ time: anchor('2024-01-05'), price: 160 });
			expect(lines[0].p2).toEqual({ time: anchor('2024-01-13'), price: 180 });
			expect(lines[0].id).toBeTruthy();
		});

		it('renders a live preview following the cursor while the first point is pending', () => {
			primitive.setDrawingMode(true);
			primitive.updateAllViews();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 300, clientY: 100 })
			);
			primitive.updateAllViews();

			const renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: LineRendererData;
			};
			expect(renderer._data.preview?.placedPoints).toHaveLength(1);
			expect(renderer._data.preview?.currentMouse?.x).toBe(300);
			expect(renderer._data.preview?.currentMouse?.y).toBe(100);
		});

		it('selects a line when an endpoint is clicked and deselects on empty area', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			primitive.updateAllViews();
			expect(primitive.getSelectedId()).toBeNull();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(primitive.getSelectedId()).toBe('l1');

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 400, clientY: 300 })
			);
			expect(primitive.getSelectedId()).toBeNull();
		});

		it('selects a line when clicked directly on its connecting segment', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			primitive.updateAllViews();
			expect(primitive.getSelectedId()).toBeNull();

			// Click near midpoint of segment (x: 200, y: 150)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 200, clientY: 150 })
			);
			expect(primitive.getSelectedId()).toBe('l1');
		});

		it('updates the line live while dragging either endpoint in time and price', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			primitive.updateAllViews();

			// Drag the first endpoint.
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			let line = primitive.getLines()[0];
			expect(line.p1.time).toBe(anchor('2024-01-07'));
			expect(line.p1.price).toBe(150);
			expect(line.p2.time).toBe(anchor('2024-01-13'));

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			expect(primitive.getDraggingPoint()).toBeNull();

			// Drag the second endpoint back the other way.
			primitive.updateAllViews();
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 300, clientY: 100 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 325, clientY: 50 })
			);
			line = primitive.getLines()[0];
			expect(line.p2.time).toBe(anchor('2024-01-14'));
			expect(line.p2.price).toBe(190);
		});

		it('clips lines whose endpoints project outside the plot area', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 600 }
				},
				{
					id: 'l2',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			primitive.updateAllViews();

			const renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: LineRendererData;
			};
			expect(renderer._data.lines).toHaveLength(1);
			expect(renderer._data.lines[0].id).toBe('l2');
		});

		it('removes a line and clears its selection', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			primitive.select('l1');

			expect(primitive.removeDrawing('l1')).toBe(true);
			expect(primitive.getLines()).toHaveLength(0);
			expect(primitive.getSelectedId()).toBeNull();
		});

		it('fires selectionChanged and drawingsChanged subscriptions', () => {
			const selectionHandler = vi.fn();
			const drawingsHandler = vi.fn();
			primitive.selectionChanged().subscribe(selectionHandler);
			primitive.drawingsChanged().subscribe(drawingsHandler);

			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			expect(drawingsHandler).toHaveBeenCalled();

			primitive.select('l1');
			expect(selectionHandler).toHaveBeenCalledWith('l1');
		});

		it('discards pending points and exits drawing mode on Escape', () => {
			primitive.setDrawingMode(true);
			primitive.updateAllViews();
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(primitive.isDrawingMode()).toBe(true);

			window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }));

			expect(primitive.isDrawingMode()).toBe(false);
			expect(primitive.getLines()).toHaveLength(0);
		});

		it('updates the cursor and hit-test contract based on mode and hover', () => {
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();

			primitive.setDrawingMode(true);
			primitive.updateAllViews();
			expect(primitive.hitTest()).toEqual({
				cursorStyle: 'crosshair',
				externalId: 'free-form-line-primitive',
				zOrder: 'top'
			});

			primitive.setDrawingMode(false);
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-13'), price: 180 }
				}
			]);
			primitive.updateAllViews();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);
			expect(primitive.getHoveredPoint()).toEqual({ id: 'l1', pointIndex: 0 });
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('default');
		});

		it('shows handles without highlight rings when hovering line, and highlights point when hovering endpoint', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-05'), price: 160 },
					p2: { time: anchor('2024-01-10'), price: 140 }
				}
			]);
			primitive.updateAllViews();

			// Hover midpoint of segment (x=(100+225)/2=163, y=(200+300)/2=250)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 163, clientY: 250 })
			);
			primitive.updateAllViews();

			expect(primitive.getHoveredLine()).toEqual({ id: 'l1', pointIndex: 0 });
			expect(primitive.getHoveredPoint()).toBeNull();

			let renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: LineRendererData;
			};
			expect(renderer._data.lines[0].isHovered).toBe(true);
			expect(renderer._data.lines[0].p1.isHovered).toBe(false);
			expect(renderer._data.lines[0].p2.isHovered).toBe(false);

			// Hover endpoint p1 at x=100, y=200
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);
			primitive.updateAllViews();

			expect(primitive.getHoveredPoint()).toEqual({ id: 'l1', pointIndex: 0 });
			renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: LineRendererData;
			};
			expect(renderer._data.lines[0].p1.isHovered).toBe(true);
			expect(renderer._data.lines[0].p2.isHovered).toBe(false);
		});

		it('projects lines across timeframes and future whitespace via the time projector', () => {
			primitive.setLines([
				{
					id: 'l1',
					p1: { time: anchor('2024-01-10'), price: 160 },
					p2: { time: anchor('2024-01-20'), price: 180 }
				}
			]);
			primitive.updateAllViews();

			const renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: LineRendererData;
			};
			expect(renderer._data.lines).toHaveLength(1);
			expect(renderer._data.lines[0].p1.x).toBe(225);
			expect(renderer._data.lines[0].p2.x).toBe(475);
		});

		it('cleans up handlers and subscriptions on detach and destroy', () => {
			primitive.detached();
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();
			primitive.destroy();
		});
	});
});
