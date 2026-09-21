import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import type { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';
import {
	HorizontalLinePrimitive,
	HorizontalLineToolState,
	HorizontalLinePaneRenderer,
	HorizontalLinePaneView,
	MouseHandlers,
	HIT_TEST_RADIUS,
	HANDLE_RADIUS,
	HORIZONTAL_LINE_COLOR,
	DEFAULT_HANDLE_COLOR,
	type HorizontalLineTarget,
	type HorizontalRendererData,
	type ProjectedHorizontalLinePointWithTarget
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
		priceFormatter: vi.fn(() => ({ format: (price: number) => price.toFixed(2) })),
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
	return new HorizontalLineToolState(() => `hline-${++counter}`);
}

describe('Horizontal Line Plugin', () => {
	describe('Constants', () => {
		it('defines expected visual constants', () => {
			expect(HIT_TEST_RADIUS).toBe(14);
			expect(HANDLE_RADIUS).toBe(5);
			expect(DEFAULT_HANDLE_COLOR).toBe('#2962FF');
			expect(HORIZONTAL_LINE_COLOR).toBe('#2962FF');
		});
	});

	describe('HorizontalLineToolState', () => {
		let state: HorizontalLineToolState;

		beforeEach(() => {
			state = createState();
		});

		it('initializes with no lines and drawing mode off', () => {
			expect(state.getHorizontalLines()).toEqual([]);
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getSelectedId()).toBeNull();
		});

		it('setHorizontalLines normalizes anchors to epoch seconds and assigns ids', () => {
			state.setHorizontalLines([
				{
					id: undefined,
					p1: { time: '2024-01-01' as Time, price: 100 }
				}
			]);

			const lines = state.getHorizontalLines();
			expect(lines).toHaveLength(1);
			expect(lines[0].id).toBe('hline-1');
			expect(lines[0].p1.time).toBe(anchor('2024-01-01'));
			expect(lines[0].p1.price).toBe(100);
		});

		it('preserves existing ids across setHorizontalLines and clears stale selection', () => {
			state.setHorizontalLines([{ id: 'keep-me', p1: { time: anchor('2024-01-01'), price: 100 } }]);
			state.select('keep-me');
			expect(state.getSelectedId()).toBe('keep-me');

			state.setHorizontalLines([]);
			expect(state.getSelectedId()).toBeNull();
		});

		it('completes a one-click drawing, exits drawing mode and fires delegates', () => {
			const drawingsHandler = vi.fn();
			const modeHandler = vi.fn();
			state.drawingsChanged().subscribe(drawingsHandler);
			state.drawingModeChanged().subscribe(modeHandler);

			state.setDrawingMode(true);
			const point = state.addPoint({ time: '2024-01-10' as Time, price: 180 });

			expect(point).toEqual({ time: anchor('2024-01-10'), price: 180 });
			expect(state.isDrawingMode()).toBe(false);
			expect(modeHandler).toHaveBeenCalledWith(false);
			expect(drawingsHandler).toHaveBeenCalled();

			const lines = state.getHorizontalLines();
			expect(lines).toHaveLength(1);
			expect(lines[0].p1).toEqual({ time: anchor('2024-01-10'), price: 180 });
			expect(lines[0].id).toBe('hline-1');
		});

		it('keeps multiple lines coexisting with unique ids', () => {
			state.addPoint({ time: anchor('2024-01-01'), price: 100 });
			state.addPoint({ time: anchor('2024-01-06'), price: 130 });

			const lines = state.getHorizontalLines();
			expect(lines).toHaveLength(2);
			expect(lines[0].id).not.toBe(lines[1].id);
		});

		it('updatePoint changes the price only and leaves the anchor time untouched', () => {
			state.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-01'), price: 100 } }]);

			expect(state.updatePoint('hl1', { price: 140 })).toBe(true);
			const line = state.getHorizontalLines()[0];
			expect(line.p1.price).toBe(140);
			expect(line.p1.time).toBe(anchor('2024-01-01'));

			// Repeated price-only updates never move the anchor (stays horizontal).
			expect(state.updatePoint('hl1', { price: 150 })).toBe(true);
			expect(state.getHorizontalLines()[0].p1.time).toBe(anchor('2024-01-01'));
			expect(state.getHorizontalLines()[0].p1.price).toBe(150);

			expect(state.updatePoint('missing', { price: 1 })).toBe(false);
		});

		it('removeDrawing deletes by id and clears selection, drag and hover targets', () => {
			state.setHorizontalLines([
				{ id: 'hl1', p1: { time: anchor('2024-01-01'), price: 100 } },
				{ id: 'hl2', p1: { time: anchor('2024-01-03'), price: 120 } }
			]);
			state.select('hl1');
			state.setDraggingPoint({ id: 'hl1' });
			state.setHoveredPoint({ id: 'hl1' });

			expect(state.removeDrawing('hl1')).toBe(true);
			expect(state.getHorizontalLines()).toHaveLength(1);
			expect(state.getHorizontalLines()[0].id).toBe('hl2');
			expect(state.getSelectedId()).toBeNull();
			expect(state.getDraggingPoint()).toBeNull();
			expect(state.getHoveredPoint()).toBeNull();
			expect(state.removeDrawing('hl1')).toBe(false);
		});

		it('selects only known ids and fires selectionChanged once per change', () => {
			const selectionHandler = vi.fn();
			state.selectionChanged().subscribe(selectionHandler);
			state.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-01'), price: 100 } }]);

			state.select('unknown');
			expect(selectionHandler).not.toHaveBeenCalled();

			state.select('hl1');
			expect(state.getSelectedId()).toBe('hl1');
			expect(selectionHandler).toHaveBeenCalledWith('hl1');

			selectionHandler.mockClear();
			state.select('hl1');
			expect(selectionHandler).not.toHaveBeenCalled();

			state.select(null);
			expect(selectionHandler).toHaveBeenCalledWith(null);
		});

		it('entering drawing mode clears the current selection', () => {
			state.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-01'), price: 100 } }]);
			state.select('hl1');
			state.setDrawingMode(true);
			expect(state.getSelectedId()).toBeNull();
		});

		it('cancelDrawing exits drawing mode without creating a line', () => {
			state.setDrawingMode(true);
			state.cancelDrawing();
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getHorizontalLines()).toHaveLength(0);
		});

		it('tracks hover and drag targets with delegate notifications', () => {
			const hoverHandler = vi.fn();
			const dragHandler = vi.fn();
			state.hoverChanged().subscribe(hoverHandler);
			state.dragChanged().subscribe(dragHandler);

			const target: HorizontalLineTarget = { id: 'hl1' };
			state.setHoveredPoint(target);
			expect(state.getHoveredPoint()).toEqual(target);
			expect(hoverHandler).toHaveBeenCalledWith(target);

			state.setDraggingPoint(target);
			expect(state.getDraggingPoint()).toEqual(target);
			expect(dragHandler).toHaveBeenCalledWith(target);

			state.setDraggingPoint(null);
			expect(state.getDraggingPoint()).toBeNull();
		});

		it('does not trigger drawingsChanged when setHorizontalLines is invoked with unchanged drawings', () => {
			const initialLines = [{ id: 'hl1', p1: { time: anchor('2024-01-01'), price: 100 } }];
			state.setHorizontalLines(initialLines);

			const drawingsHandler = vi.fn();
			state.drawingsChanged().subscribe(drawingsHandler);

			state.setHorizontalLines(initialLines);
			expect(drawingsHandler).not.toHaveBeenCalled();

			state.setHorizontalLines([{ id: 'hl1', p1: { time: '2024-01-01' as Time, price: 100 } }]);
			expect(drawingsHandler).not.toHaveBeenCalled();
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

		it('hit tests the single handle by drawing id within the radius', () => {
			const points: ProjectedHorizontalLinePointWithTarget[] = [
				{ id: 'hl1', x: 100, y: 200, originalPoint: { time: anchor('2024-01-05'), price: 160 } },
				{ id: 'hl2', x: 300, y: 150, originalPoint: { time: anchor('2024-01-13'), price: 170 } }
			];
			mouse.setProjectedPoints(points);

			expect(mouse.hitTestPoint(105, 203)?.id).toBe('hl1');
			expect(mouse.hitTestPoint(305, 153)?.id).toBe('hl2');
			expect(mouse.hitTestPoint(105, 203 + HIT_TEST_RADIUS + 1)).toBeNull();
		});

		it('hit tests the line across full pane width', () => {
			mouse.setProjectedLines([{ id: 'hl1', y: 200 }]);

			expect(mouse.hitTestLine(500, 200)).toEqual({ id: 'hl1' });
			expect(mouse.hitTestLine(500, 200 + HIT_TEST_RADIUS - 1)).toEqual({ id: 'hl1' });
			expect(mouse.hitTestLine(500, 200 + HIT_TEST_RADIUS + 2)).toBeNull();
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
				{ id: 'hl1', x: 100, y: 200, originalPoint: { time: anchor('2024-01-05'), price: 160 } }
			]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);
			expect(hoverHandler).toHaveBeenCalledWith({ id: 'hl1' });

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(pointClickHandler).toHaveBeenCalledWith({
				id: 'hl1',
				point: { time: anchor('2024-01-05'), price: 160 }
			});

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			expect(mouse.isDragging()).toBe(true);
			expect(dragStartHandler).toHaveBeenCalledWith({ id: 'hl1' });

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);
			expect(pointDraggedHandler).toHaveBeenCalledWith(
				expect.objectContaining({ id: 'hl1', x: 150, y: 250 })
			);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			expect(mouse.isDragging()).toBe(false);
			expect(dragEndHandler).toHaveBeenCalledWith({ id: 'hl1' });
		});

		it('fires chartClicked in drawing mode instead of pointClicked', () => {
			const chartClickHandler = vi.fn();
			const pointClickHandler = vi.fn();
			mouse.chartClicked().subscribe(chartClickHandler);
			mouse.pointClicked().subscribe(pointClickHandler);
			mouse.setProjectedPoints([
				{ id: 'hl1', x: 100, y: 200, originalPoint: { time: anchor('2024-01-05'), price: 160 } }
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
				{ id: 'hl1', x: 100, y: 200, originalPoint: { time: anchor('2024-01-05'), price: 160 } }
			]);
			mouse.detached();
			expect(mouse.hitTestPoint(100, 200)).toBeNull();
		});
	});

	describe('HorizontalLinePaneRenderer', () => {
		let renderer: HorizontalLinePaneRenderer;
		let mockCanvas: ReturnType<typeof createMockCanvasTarget>;

		beforeEach(() => {
			renderer = new HorizontalLinePaneRenderer();
			mockCanvas = createMockCanvasTarget();
		});

		function renderData(
			options: {
				showLabel?: boolean;
				isSelected?: boolean;
				isHovered?: boolean;
				isLineHovered?: boolean;
				isDragging?: boolean;
			} = {}
		): HorizontalRendererData {
			return {
				lines: [
					{
						id: 'hl1',
						p1: {
							x: 100,
							y: 300,
							time: anchor('2024-01-01'),
							price: 160,
							isSelected: options.isSelected,
							isHovered: options.isHovered,
							isDragging: options.isDragging
						},
						label: '160.00',
						showLabel: options.showLabel,
						isSelected: options.isSelected,
						isHovered: options.isLineHovered
					}
				],
				preview: null
			};
		}

		it('draws a full-width horizontal line at the projected y', () => {
			renderer.update(renderData());
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).toHaveBeenCalled();
			const moveTo = mockCanvas.drawCalls.find((c) => c.type === 'moveTo');
			const lineTo = mockCanvas.drawCalls.find((c) => c.type === 'lineTo');
			// mediaSize.width === 800, hpr === 2 -> bitmap span 0..1600.
			expect(moveTo?.args).toEqual([0, 599]);
			expect(lineTo?.args).toEqual([1600, 599]);
			expect(mockCanvas.drawCalls.some((c) => c.type === 'stroke')).toBe(true);
		});

		it('hides the handle on resting unselected unhovered line (0 arcs)', () => {
			renderer.update(renderData());
			renderer.draw(mockCanvas.target);

			const arcs = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			expect(arcs).toHaveLength(0);
		});

		it('draws the handle with blue fill, white border, radius 5 when selected without ring', () => {
			renderer.update(renderData({ isSelected: true }));
			renderer.draw(mockCanvas.target);

			const arcs = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			expect(arcs).toHaveLength(1);
			expect(arcs[0].args.slice(0, 3)).toEqual([199, 599, HANDLE_RADIUS * 2]);
			expect(mockCanvas.context.fillStyle).toBe('#2962FF');
			expect(mockCanvas.context.strokeStyle).toBe('#ffffff');
		});

		it('draws the price label only when showLabel is true', () => {
			renderer.update(renderData({ showLabel: true }));
			renderer.draw(mockCanvas.target);
			const labels = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(labels.map((c) => c.args[0])).toContain('160.00');

			mockCanvas = createMockCanvasTarget();
			renderer.update(renderData({ showLabel: false }));
			renderer.draw(mockCanvas.target);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'fillText')).toHaveLength(0);
		});

		it('draws highlight rings exclusively when the point is hovered or dragged', () => {
			renderer.update(renderData({ isHovered: true }));
			renderer.draw(mockCanvas.target);

			// Highlight ring + handle dot = 2 arcs
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(2);

			mockCanvas = createMockCanvasTarget();
			renderer.update(renderData({ isDragging: true }));
			renderer.draw(mockCanvas.target);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(2);
		});

		it('draws the handle dot without highlight ring when line is hovered (1 arc)', () => {
			renderer.update(renderData({ isLineHovered: true }));
			renderer.draw(mockCanvas.target);

			const arcs = mockCanvas.drawCalls.filter((c) => c.type === 'arc');
			expect(arcs).toHaveLength(1);
			expect(arcs[0].args.slice(0, 3)).toEqual([199, 599, HANDLE_RADIUS * 2]);
			expect(mockCanvas.context.fillStyle).toBe('#2962FF');
			expect(mockCanvas.context.strokeStyle).toBe('#ffffff');
		});

		it('skips invisible lines', () => {
			const data = renderData({ showLabel: true });
			data.lines[0].visible = false;
			renderer.update(data);
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls.filter((c) => c.type === 'fillText')).toHaveLength(0);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(0);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'stroke')).toHaveLength(0);
		});

		it('draws a dashed mouse-following preview while in drawing mode', () => {
			renderer.update({
				lines: [],
				preview: {
					currentMouse: { x: 250, y: 100, time: anchor('2024-01-10'), price: 180 },
					label: '180.00',
					showLabel: true
				}
			});
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash')).toHaveLength(1);
			expect(mockCanvas.drawCalls.find((c) => c.type === 'moveTo')?.args).toEqual([0, 199]);
			expect(mockCanvas.drawCalls.find((c) => c.type === 'lineTo')?.args).toEqual([1600, 199]);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(1);
			const labels = mockCanvas.drawCalls.filter((c) => c.type === 'fillText');
			expect(labels.map((c) => c.args[0])).toContain('180.00');
		});

		it('draws only the dashed line when the preview has no cursor position', () => {
			renderer.update({
				lines: [],
				preview: { currentMouse: null, label: null, showLabel: true }
			});
			renderer.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls.filter((c) => c.type === 'arc')).toHaveLength(0);
			expect(mockCanvas.drawCalls.filter((c) => c.type === 'setLineDash')).toHaveLength(0);
		});

		it('draws nothing when data is null', () => {
			renderer.update(null);
			renderer.draw(mockCanvas.target);
			expect(mockCanvas.drawCalls).toHaveLength(0);
		});
	});

	describe('HorizontalLinePrimitive Integration', () => {
		let primitive: HorizontalLinePrimitive;
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let mockRequestUpdate: () => void;

		beforeEach(() => {
			primitive = new HorizontalLinePrimitive();
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
			expect(views[0]).toBeInstanceOf(HorizontalLinePaneView);
		});

		it('initializes lines, drawing mode, selection and label visibility from the constructor', () => {
			const seeded = new HorizontalLinePrimitive({
				horizontalLines: [{ id: 'hl1', p1: { time: anchor('2024-01-01'), price: 100 } }],
				isDrawingMode: true,
				selectedId: 'hl1',
				hideLabels: true
			});

			expect(seeded.getHorizontalLines()).toHaveLength(1);
			expect(seeded.isDrawingMode()).toBe(true);
			expect(seeded.getSelectedId()).toBe('hl1');
		});

		it('creates a line with a single chart click and exits drawing mode', () => {
			primitive.setDrawingMode(true);
			primitive.updateAllViews();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);

			expect(primitive.isDrawingMode()).toBe(false);
			const lines = primitive.getHorizontalLines();
			expect(lines).toHaveLength(1);
			expect(lines[0].p1).toEqual({ time: anchor('2024-01-05'), price: 160 });
			expect(lines[0].id).toBeTruthy();
		});

		it('updates the price live while dragging and keeps the anchor time fixed', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.updateAllViews();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			const line = primitive.getHorizontalLines()[0];
			expect(line.p1.price).toBe(150);
			expect(line.p1.time).toBe(anchor('2024-01-05'));

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);
			expect(primitive.getDraggingPoint()).toBeNull();
		});

		it('updates the rendered price label after a drag', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.updateAllViews();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);
			primitive.updateAllViews();

			const renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: HorizontalRendererData;
			};
			expect(renderer._data.lines[0].label).toBe('150.00');
		});

		it('selects a line when its handle is clicked and deselects on empty area', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.updateAllViews();
			expect(primitive.getSelectedId()).toBeNull();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 100, clientY: 200 })
			);
			expect(primitive.getSelectedId()).toBe('hl1');

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 400, clientY: 300 })
			);
			expect(primitive.getSelectedId()).toBeNull();
		});

		it('selects a line when clicked directly anywhere along its horizontal span', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.updateAllViews();
			expect(primitive.getSelectedId()).toBeNull();

			// Click at x=500, y=200 (far from handle at x=100, but on the horizontal line at y=200)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 500, clientY: 200 })
			);
			expect(primitive.getSelectedId()).toBe('hl1');
		});

		it('removes a line and clears its selection', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.select('hl1');

			expect(primitive.removeDrawing('hl1')).toBe(true);
			expect(primitive.getHorizontalLines()).toHaveLength(0);
			expect(primitive.getSelectedId()).toBeNull();
		});

		it('fires selectionChanged and drawingsChanged subscriptions', () => {
			const selectionHandler = vi.fn();
			const drawingsHandler = vi.fn();
			primitive.selectionChanged().subscribe(selectionHandler);
			primitive.drawingsChanged().subscribe(drawingsHandler);

			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			expect(drawingsHandler).toHaveBeenCalled();

			primitive.select('hl1');
			expect(selectionHandler).toHaveBeenCalledWith('hl1');
		});

		it('cancels drawing mode on Escape without creating a line', () => {
			primitive.setDrawingMode(true);
			primitive.updateAllViews();

			window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }));

			expect(primitive.isDrawingMode()).toBe(false);
			expect(primitive.getHorizontalLines()).toHaveLength(0);
		});

		it('updates the cursor and hit-test contract based on mode and hover', () => {
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();

			primitive.setDrawingMode(true);
			primitive.updateAllViews();
			expect(primitive.hitTest()).toEqual({
				cursorStyle: 'crosshair',
				externalId: 'horizontal-line-primitive',
				zOrder: 'top'
			});

			primitive.setDrawingMode(false);
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.updateAllViews();

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);
			expect(primitive.getHoveredPoint()).toEqual({ id: 'hl1' });
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('default');
		});

		it('shows handle without highlight ring when hovering line, and highlights point when hovering handle', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-05'), price: 160 } }]);
			primitive.updateAllViews();

			// Hover at x=500, y=200 (far from handle at x=100, on horizontal line)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 500, clientY: 200 })
			);
			primitive.updateAllViews();

			expect(primitive.getHoveredLine()).toEqual({ id: 'hl1' });
			expect(primitive.getHoveredPoint()).toBeNull();

			let renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: HorizontalRendererData;
			};
			expect(renderer._data.lines[0].isHovered).toBe(true);
			expect(renderer._data.lines[0].p1.isHovered).toBe(false);

			// Hover directly over handle at x=100, y=200
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 200 })
			);
			primitive.updateAllViews();

			expect(primitive.getHoveredPoint()).toEqual({ id: 'hl1' });
			renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: HorizontalRendererData;
			};
			expect(renderer._data.lines[0].p1.isHovered).toBe(true);
		});

		it('gates the price label on setHideLabels', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-10'), price: 160 } }]);
			primitive.updateAllViews();

			let renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: HorizontalRendererData;
			};
			expect(renderer._data.lines[0].showLabel).toBe(true);
			expect(renderer._data.lines[0].label).toBe('160.00');

			primitive.setHideLabels(true);
			primitive.updateAllViews();
			renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: HorizontalRendererData;
			};
			expect(renderer._data.lines[0].showLabel).toBe(false);
		});

		it('projects lines across timeframes and future whitespace via the time projector', () => {
			primitive.setHorizontalLines([{ id: 'hl1', p1: { time: anchor('2024-01-10'), price: 160 } }]);
			primitive.updateAllViews();

			const renderer = primitive.paneViews()[0]?.renderer() as unknown as {
				_data: HorizontalRendererData;
			};
			expect(renderer._data.lines).toHaveLength(1);
			expect(renderer._data.lines[0].p1.x).toBe(225);
			expect(renderer._data.lines[0].p1.y).toBe(200);
		});

		it('cleans up handlers and subscriptions on detach and destroy', () => {
			primitive.detached();
			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();
			primitive.destroy();
		});
	});
});
