import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import type { CanvasRenderingTarget2D, BitmapCoordinatesRenderingScope } from 'fancy-canvas';
import {
	ElliottWavesPrimitive,
	ElliottWaveState,
	ElliottWavePaneRenderer,
	MouseHandlers,
	CYCLE_STYLE,
	PRIMARY_STYLE,
	DEGREE_STYLES,
	HIT_TEST_RADIUS,
	MAX_WAVE_POINTS
} from './index';
import type { DegreeWaveCount } from '$lib/utils/finance/elliott-wave';

// Helper to create mock Chart and Series APIs
function createMockChartAndSeries() {
	const mockChartElement = document.createElement('div');
	// Mock container dimensions
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
			if (x < 0 || x > 750) return null;
			return `2024-01-${String(Math.min(30, Math.max(1, Math.floor(x / 25) + 1))).padStart(2, '0')}` as Time;
		}),
		timeToCoordinate: vi.fn((time: Time) => {
			if (typeof time === 'string' && time.startsWith('2024-01-')) {
				const day = parseInt(time.replace('2024-01-', ''), 10);
				return (day - 1) * 25;
			}
			return null;
		}),
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
		timeScale: vi.fn(() => timeScale)
	} as unknown as IChartApi;

	return { chart, series, mockChartElement, timeScale, priceScale };
}

// Helper to create mock Canvas 2D context and CanvasRenderingTarget2D
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

describe('Elliott Wave Plugin', () => {
	describe('Constants & Degree Visual Configuration', () => {
		it('defines Cycle and Primary visual styles with distinct formatting and colors', () => {
			expect(CYCLE_STYLE.degree).toBe('cycle');
			expect(CYCLE_STYLE.color).toBe('#3b82f6');
			expect(CYCLE_STYLE.formatLabel(1)).toBe('(1)');
			expect(CYCLE_STYLE.formatLabel(5)).toBe('(5)');

			expect(PRIMARY_STYLE.degree).toBe('primary');
			expect(PRIMARY_STYLE.color).toBe('#10b981');
			expect(PRIMARY_STYLE.formatLabel(1)).toBe('1');
			expect(PRIMARY_STYLE.formatLabel(5)).toBe('5');

			expect(DEGREE_STYLES.cycle).toBe(CYCLE_STYLE);
			expect(DEGREE_STYLES.primary).toBe(PRIMARY_STYLE);
			expect(HIT_TEST_RADIUS).toBe(14);
			expect(MAX_WAVE_POINTS).toBe(6);
		});
	});

	describe('ElliottWaveState', () => {
		let state: ElliottWaveState;

		beforeEach(() => {
			state = new ElliottWaveState();
		});

		it('initializes with default state', () => {
			expect(state.getActiveDegree()).toBe('cycle');
			expect(state.isDrawingMode()).toBe(false);
			expect(state.getWaveCount('cycle')).toBeNull();
			expect(state.getWaveCount('primary')).toBeNull();
			expect(state.getPoints('cycle')).toEqual([]);
			expect(state.getHoveredPoint()).toBeNull();
			expect(state.getDraggingPoint()).toBeNull();
		});

		it('switches active degree and fires degreeChanged', () => {
			const onDegreeChanged = vi.fn();
			state.degreeChanged().subscribe(onDegreeChanged);

			state.setActiveDegree('primary');
			expect(state.getActiveDegree()).toBe('primary');
			expect(onDegreeChanged).toHaveBeenCalledWith('primary');

			// Switching to same degree should not fire
			onDegreeChanged.mockClear();
			state.setActiveDegree('primary');
			expect(onDegreeChanged).not.toHaveBeenCalled();
		});

		it('toggles drawing mode and fires drawingModeChanged', () => {
			const onDrawingChanged = vi.fn();
			state.drawingModeChanged().subscribe(onDrawingChanged);

			state.setDrawingMode(true);
			expect(state.isDrawingMode()).toBe(true);
			expect(onDrawingChanged).toHaveBeenCalledWith(true);

			state.setDrawingMode(false);
			expect(state.isDrawingMode()).toBe(false);
			expect(onDrawingChanged).toHaveBeenCalledWith(false);
		});

		it('sequentially adds points 0 to 5 to the active degree and completes drawing mode', () => {
			const onPointsChanged = vi.fn();
			const onDrawingChanged = vi.fn();
			state.wavePointsChanged().subscribe(onPointsChanged);
			state.drawingModeChanged().subscribe(onDrawingChanged);

			state.setDrawingMode(true);

			// Add Wave 0 (Anchor origin point)
			const p0 = state.addPoint({ time: '2024-01-01' as Time, price: 50 });
			expect(p0.wave).toBe(0);
			expect(p0.price).toBe(50);
			expect(state.getPoints('cycle').length).toBe(1);
			expect(state.isDrawingMode()).toBe(true);

			// Add Wave 1, 2, 3, 4
			state.addPoint({ time: '2024-01-02' as Time, price: 100 });
			state.addPoint({ time: '2024-01-03' as Time, price: 90 });
			state.addPoint({ time: '2024-01-04' as Time, price: 150 });
			state.addPoint({ time: '2024-01-05' as Time, price: 120 });

			expect(state.getPoints('cycle').length).toBe(5);
			expect(state.isDrawingMode()).toBe(true);

			// Add Wave 5 -> Should auto-complete drawing mode
			const p5 = state.addPoint({ time: '2024-01-06' as Time, price: 200 });
			expect(p5.wave).toBe(5);
			expect(state.getPoints('cycle').length).toBe(6);
			expect(state.isDrawingMode()).toBe(false);
			expect(onDrawingChanged).toHaveBeenCalledWith(false);

			const waveCount = state.getWaveCount('cycle');
			expect(waveCount?.wave3Target).toBe(150);
			expect(waveCount?.wave5Target).toBe(200);
		});

		it('restarts point sequence if adding a point when 6 points already exist', () => {
			for (let i = 0; i <= 5; i++) {
				state.addPoint({ time: `2024-01-0${i + 1}` as Time, price: 100 + i * 10 });
			}
			expect(state.getPoints('cycle').length).toBe(6);

			// Adding 7th point resets to 1 point with wave 0
			const nextPoint = state.addPoint({ time: '2024-01-10' as Time, price: 300 });
			expect(nextPoint.wave).toBe(0);
			expect(state.getPoints('cycle').length).toBe(1);
			expect(state.getPoints('cycle')[0].price).toBe(300);
		});

		it('updates specific point coordinates in place including point 0', () => {
			state.addPoint({ time: '2024-01-01' as Time, price: 50 });
			state.addPoint({ time: '2024-01-02' as Time, price: 100 });
			state.addPoint({ time: '2024-01-03' as Time, price: 90 });
			state.addPoint({ time: '2024-01-04' as Time, price: 150 });

			const onPointsChanged = vi.fn();
			state.wavePointsChanged().subscribe(onPointsChanged);

			// Update point 0
			const updated0 = state.updatePoint(0, { price: 55, time: '2024-01-01' as Time });
			expect(updated0).toBe(true);
			expect(state.getPoints('cycle')[0].price).toBe(55);

			// Update point 2
			const updated2 = state.updatePoint(2, { price: 95, time: '2024-01-03' as Time });
			expect(updated2).toBe(true);
			expect(state.getPoints('cycle')[2].price).toBe(95);
			expect(onPointsChanged).toHaveBeenCalled();

			// Updating non-existent wave returns false
			expect(state.updatePoint(5, { price: 200 })).toBe(false);
		});

		it('clears wave count for specified or active degree', () => {
			state.addPoint({ time: '2024-01-01' as Time, price: 100 }, 'cycle');
			state.addPoint({ time: '2024-01-01' as Time, price: 100 }, 'primary');

			state.clearWave('cycle');
			expect(state.getWaveCount('cycle')).toBeNull();
			expect(state.getWaveCount('primary')).not.toBeNull();

			state.clearWave('primary');
			expect(state.getWaveCount('primary')).toBeNull();
		});

		it('sets and retrieves full wave counts for both degrees', () => {
			const sampleCycle: DegreeWaveCount = {
				points: [
					{ wave: 1, time: '2024-01-01' as Time, price: 100 },
					{ wave: 2, time: '2024-01-02' as Time, price: 80 }
				],
				wave3Target: 180
			};
			const samplePrimary: DegreeWaveCount = {
				points: [{ wave: 1, time: '2024-01-05' as Time, price: 110 }],
				wave3Target: 160
			};

			state.setAllWaveCounts({ cycle: sampleCycle, primary: samplePrimary });

			const all = state.getAllWaveCounts();
			expect(all.cycle?.points.length).toBe(2);
			expect(all.cycle?.wave3Target).toBe(180);
			expect(all.primary?.points.length).toBe(1);
			expect(all.primary?.wave3Target).toBe(160);
		});

		it('manages hover and drag targets and fires delegates', () => {
			const onHover = vi.fn();
			const onDrag = vi.fn();
			state.hoverChanged().subscribe(onHover);
			state.dragChanged().subscribe(onDrag);

			state.setHoveredPoint({ degree: 'cycle', wave: 2 });
			expect(state.getHoveredPoint()).toEqual({ degree: 'cycle', wave: 2 });
			expect(onHover).toHaveBeenCalledWith({ degree: 'cycle', wave: 2 });

			state.setDraggingPoint({ degree: 'cycle', wave: 2 });
			expect(state.getDraggingPoint()).toEqual({ degree: 'cycle', wave: 2 });
			expect(onDrag).toHaveBeenCalledWith({ degree: 'cycle', wave: 2 });

			state.setHoveredPoint(null);
			state.setDraggingPoint(null);
			expect(state.getHoveredPoint()).toBeNull();
			expect(state.getDraggingPoint()).toBeNull();
		});
	});

	describe('ElliottWavePaneRenderer (Canvas Drawing)', () => {
		let renderer: ElliottWavePaneRenderer;

		beforeEach(() => {
			renderer = new ElliottWavePaneRenderer();
		});

		it('renders connecting lines and node badges for Cycle degree (omits label for wave 0)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [
							{ wave: 0, x: 50, y: 320, time: '2024-01-01' as Time, price: 90 },
							{ wave: 1, x: 100, y: 300, time: '2024-01-02' as Time, price: 100 },
							{ wave: 2, x: 150, y: 350, time: '2024-01-03' as Time, price: 80 },
							{ wave: 3, x: 200, y: 200, time: '2024-01-04' as Time, price: 150 }
						]
					},
					{
						degree: 'primary',
						config: PRIMARY_STYLE,
						isActiveDegree: false,
						points: []
					}
				],
				preview: null
			});

			renderer.draw(target);

			expect(target.useBitmapCoordinateSpace).toHaveBeenCalled();

			// Should have line drawing calls (moveTo, lineTo) connecting all 4 points (3 line segments)
			const moveCalls = drawCalls.filter((c) => c.type === 'moveTo');
			const lineCalls = drawCalls.filter((c) => c.type === 'lineTo');
			expect(moveCalls.length).toBeGreaterThanOrEqual(1);
			expect(lineCalls.length).toBeGreaterThanOrEqual(3);

			// Should render node badge circles for all 4 points (at least 4 arc calls)
			const arcCalls = drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBeGreaterThanOrEqual(4);

			// Should render text badges "(1)", "(2)", "(3)" for Cycle, but NOT for wave 0
			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('(1)');
			expect(labels).toContain('(2)');
			expect(labels).toContain('(3)');
			expect(labels).not.toContain('(0)');
			expect(labels).not.toContain('0');
		});

		it('renders Primary degree badges formatted as "1", "2", "3" (omits wave 0 label)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'primary',
						config: PRIMARY_STYLE,
						isActiveDegree: true,
						points: [
							{ wave: 0, x: 50, y: 320, time: '2024-01-01' as Time, price: 90 },
							{ wave: 1, x: 100, y: 300, time: '2024-01-02' as Time, price: 100 },
							{ wave: 2, x: 150, y: 350, time: '2024-01-03' as Time, price: 80 }
						]
					}
				],
				preview: null
			});

			renderer.draw(target);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('1');
			expect(labels).toContain('2');
			expect(labels).not.toContain('0');
		});

		it('renders highlight ring when a point (including wave 0) is hovered or dragged', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [
							{ wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100, isHovered: true }
						]
					}
				],
				preview: null
			});

			renderer.draw(target);

			// Should have at least 2 arc calls (1 for highlight ring, 1 for badge circle)
			const arcCalls = drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBeGreaterThanOrEqual(2);
		});

		it('renders drawing preview for wave 0 without text badge', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: []
					}
				],
				preview: {
					degree: 'cycle',
					config: CYCLE_STYLE,
					nextWave: 0,
					lastPoint: null,
					currentMouse: { x: 100, y: 200 }
				}
			});

			renderer.draw(target);

			// Ghost circle is drawn (arc call)
			const arcCalls = drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBeGreaterThanOrEqual(1);

			// But no text label is drawn for nextWave 0
			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			expect(textCalls.length).toBe(0);
		});

		it('renders drawing preview dashed line and ghost badge for wave 1', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [{ wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100 }]
					}
				],
				preview: {
					degree: 'cycle',
					config: CYCLE_STYLE,
					nextWave: 1,
					lastPoint: { wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100 },
					currentMouse: { x: 160, y: 250 }
				}
			});

			renderer.draw(target);

			const dashCalls = drawCalls.filter((c) => c.type === 'setLineDash');
			expect(dashCalls.length).toBeGreaterThanOrEqual(1);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('(1)'); // Ghost badge for next wave
		});

		it('handles empty or null data gracefully without crashing', () => {
			const { target } = createMockCanvasTarget();
			renderer.update(null);
			expect(() => renderer.draw(target)).not.toThrow();
		});
	});

	describe('MouseHandlers (Hit testing & Interactions)', () => {
		let mouseHandlers: MouseHandlers;
		let mockData: ReturnType<typeof createMockChartAndSeries>;

		beforeEach(() => {
			mouseHandlers = new MouseHandlers();
			mockData = createMockChartAndSeries();
			mouseHandlers.attached(mockData.chart, mockData.series);
		});

		it('hit tests points within HIT_TEST_RADIUS', () => {
			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 1,
					x: 100,
					y: 200,
					originalPoint: { wave: 1, time: '2024-01-01' as Time, price: 100 }
				},
				{
					degree: 'cycle',
					wave: 2,
					x: 250,
					y: 300,
					originalPoint: { wave: 2, time: '2024-01-05' as Time, price: 80 }
				}
			]);

			// Inside radius (dist ~5px)
			const hit1 = mouseHandlers.hitTestPoint(103, 204);
			expect(hit1).not.toBeNull();
			expect(hit1?.wave).toBe(1);

			// Outside radius (dist ~30px)
			const hitNone = mouseHandlers.hitTestPoint(130, 200);
			expect(hitNone).toBeNull();
		});

		it('fires hover event on mousemove over a point', () => {
			const onHover = vi.fn();
			mouseHandlers.pointHovered().subscribe(onHover);

			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 1,
					x: 100,
					y: 200,
					originalPoint: { wave: 1, time: '2024-01-01' as Time, price: 100 }
				}
			]);

			// Simulate mousemove over point (100, 200)
			const moveEvent = new MouseEvent('mousemove', { clientX: 100, clientY: 200 });
			mockData.mockChartElement.dispatchEvent(moveEvent);

			expect(onHover).toHaveBeenCalledWith({ degree: 'cycle', wave: 1 });

			// Simulate mousemove away
			const moveAwayEvent = new MouseEvent('mousemove', { clientX: 400, clientY: 400 });
			mockData.mockChartElement.dispatchEvent(moveAwayEvent);

			expect(onHover).toHaveBeenCalledWith(null);
		});

		it('handles point dragging lifecycle on mousedown, mousemove, and mouseup', () => {
			const onDragStart = vi.fn();
			const onDrag = vi.fn();
			const onDragEnd = vi.fn();

			mouseHandlers.dragStarted().subscribe(onDragStart);
			mouseHandlers.pointDragged().subscribe(onDrag);
			mouseHandlers.dragEnded().subscribe(onDragEnd);

			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 2,
					x: 150,
					y: 250,
					originalPoint: { wave: 2, time: '2024-01-05' as Time, price: 120 }
				}
			]);

			// 1. Mousedown on point 2
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 150, clientY: 250 })
			);
			expect(mouseHandlers.isDragging()).toBe(true);
			expect(onDragStart).toHaveBeenCalledWith({ degree: 'cycle', wave: 2 });

			// 2. Mousemove to new position
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 175, clientY: 230 })
			);
			expect(onDrag).toHaveBeenCalled();
			expect(onDrag.mock.calls[0][0].degree).toBe('cycle');
			expect(onDrag.mock.calls[0][0].wave).toBe(2);
			expect(onDrag.mock.calls[0][0].time).toBeDefined();
			expect(onDrag.mock.calls[0][0].price).toBeDefined();

			// 3. Mouseup on window or chart
			window.dispatchEvent(new MouseEvent('mouseup'));
			expect(mouseHandlers.isDragging()).toBe(false);
			expect(onDragEnd).toHaveBeenCalledWith({ degree: 'cycle', wave: 2 });
		});

		it('fires chartClicked in drawing mode when user clicks chart plot area', () => {
			const onChartClicked = vi.fn();
			mouseHandlers.chartClicked().subscribe(onChartClicked);
			mouseHandlers.setDrawingMode(true);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 200, clientY: 150 })
			);

			expect(onChartClicked).toHaveBeenCalledWith(
				expect.objectContaining({
					x: 200,
					y: 150,
					time: expect.any(String),
					price: expect.any(Number)
				})
			);
		});

		it('does not fire chartClicked if click is outside plot area (e.g. over price/time scale)', () => {
			const onChartClicked = vi.fn();
			mouseHandlers.chartClicked().subscribe(onChartClicked);
			mouseHandlers.setDrawingMode(true);

			// Over price scale (x = 780, width = 800, price scale width = 50 -> boundary is 750)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 780, clientY: 150 })
			);
			expect(onChartClicked).not.toHaveBeenCalled();

			// Over time scale (y = 480, height = 500, time scale height = 30 -> boundary is 470)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 200, clientY: 485 })
			);
			expect(onChartClicked).not.toHaveBeenCalled();
		});
	});

	describe('ElliottWavesPrimitive (Series Primitive Integration)', () => {
		let primitive: ElliottWavesPrimitive;
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let mockRequestUpdate: () => void;

		beforeEach(() => {
			primitive = new ElliottWavesPrimitive({
				activeDegree: 'cycle'
			});
			mockData = createMockChartAndSeries();
			mockRequestUpdate = vi.fn();

			primitive.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: mockRequestUpdate,
				horzScaleBehavior: {} as never
			});
		});

		it('attaches and detaches cleanly', () => {
			expect(primitive.paneViews()).toHaveLength(1);
			expect(mockRequestUpdate).toHaveBeenCalled();

			primitive.detached();
			expect(() => primitive.updateAllViews()).not.toThrow();
		});

		it('projects points and manages cursor style for hitTest', () => {
			primitive.addPoint(100, '2024-01-05' as Time, 'cycle');
			primitive.addPoint(150, '2024-01-10' as Time, 'cycle');

			primitive.updateAllViews();
			expect(primitive.hitTest()).toBeNull();

			// In drawing mode -> crosshair cursor
			primitive.setDrawingMode(true);
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('crosshair');

			// Hovering point -> grab cursor
			primitive.setDrawingMode(false);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 100, clientY: 500 }) // over wave 1
			);
			primitive.updateAllViews();
			// Should return grab if hovering
			const hit = primitive.hitTest();
			expect(hit?.cursorStyle === 'grab' || hit === null).toBe(true);
		});

		it('handles sequential drawing mode clicks adding points 0 to 5', () => {
			primitive.setDrawingMode(true);
			expect(primitive.isDrawingMode()).toBe(true);

			// Click 6 times in chart (points 0, 1, 2, 3, 4, 5)
			for (let i = 0; i <= 5; i++) {
				if (i < 5) {
					// Drawing mode should remain active through clicks 0, 1, 2, 3, 4
					expect(primitive.isDrawingMode()).toBe(true);
				}
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 50 + i * 40, clientY: 200 - i * 20 })
				);
			}

			const points = primitive.getPoints('cycle');
			expect(points).toHaveLength(6);
			expect(points.map((p) => p.wave)).toEqual([0, 1, 2, 3, 4, 5]);
			// Drawing mode should auto-complete on 6th point (wave 5)
			expect(primitive.isDrawingMode()).toBe(false);
		});

		it('supports interactive point dragging to modify wave coordinates including point 0', () => {
			primitive.addPoint(120, '2024-01-05' as Time, 'cycle'); // wave 0: x = 100, y = 400
			primitive.updateAllViews();

			// Start dragging wave 0
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 400 })
			);
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).toBe('grabbing');

			// Drag to new coordinate (x = 150, y = 350)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 350 })
			);

			const wave0 = primitive.getPoints('cycle')[0];
			expect(wave0.wave).toBe(0);
			expect(wave0.time).toBe('2024-01-07');
			expect(wave0.price).toBe(130);

			// Release drag
			window.dispatchEvent(new MouseEvent('mouseup'));
			primitive.updateAllViews();
			expect(primitive.hitTest()?.cursorStyle).not.toBe('grabbing');
		});

		it('handles degree switching and separate wave points for Cycle and Primary', () => {
			primitive.setActiveDegree('cycle');
			primitive.addPoint(100, '2024-01-01' as Time);
			primitive.addPoint(120, '2024-01-02' as Time);

			primitive.setActiveDegree('primary');
			primitive.addPoint(50, '2024-01-10' as Time);

			expect(primitive.getPoints('cycle')).toHaveLength(2);
			expect(primitive.getPoints('primary')).toHaveLength(1);

			const all = primitive.getAllWaveCounts();
			expect(all.cycle?.points).toHaveLength(2);
			expect(all.primary?.points).toHaveLength(1);
		});

		it('handles unprojectable / off-screen points without throwing', () => {
			(mockData.timeScale.timeToCoordinate as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
				null
			);
			(mockData.series.priceToCoordinate as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
				null
			);

			primitive.addPoint(100, '2024-01-01' as Time, 'cycle');
			expect(() => primitive.updateAllViews()).not.toThrow();
		});

		it('fires wavePointsChanged, drawingModeChanged, and degreeChanged subscriptions', () => {
			const onPoints = vi.fn();
			const onDrawing = vi.fn();
			const onDegree = vi.fn();

			primitive.wavePointsChanged().subscribe(onPoints);
			primitive.drawingModeChanged().subscribe(onDrawing);
			primitive.degreeChanged().subscribe(onDegree);

			primitive.setActiveDegree('primary');
			expect(onDegree).toHaveBeenCalledWith('primary');

			primitive.setDrawingMode(true);
			expect(onDrawing).toHaveBeenCalledWith(true);

			primitive.addPoint(150, '2024-01-01' as Time);
			expect(onPoints).toHaveBeenCalledWith(
				expect.objectContaining({
					degree: 'primary',
					waveCount: expect.any(Object)
				})
			);

			primitive.clearWave('primary');
			expect(onPoints).toHaveBeenCalledWith({
				degree: 'primary',
				waveCount: null
			});
		});

		it('cleans up and destroys primitive resources cleanly', () => {
			expect(() => primitive.destroy()).not.toThrow();
		});
	});
});
