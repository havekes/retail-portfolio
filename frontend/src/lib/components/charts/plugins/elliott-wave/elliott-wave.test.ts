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
	INTERMEDIATE_STYLE,
	DEGREE_STYLES,
	IMPULSE_COLOR,
	CORRECTIVE_COLOR,
	VERTICAL_LABEL_OFFSET,
	getWaveColor,
	getWaveLabelOffset,
	getWaveOrder,
	HIT_TEST_RADIUS,
	MAX_IMPULSE_POINTS,
	MAX_CORRECTIVE_POINTS,
	MAX_WAVE_POINTS,
	TimeProjector,
	computeIntervalSeconds,
	addIntervalToTime,
	snapPriceToWick,
	buildCandleLookup,
	findCandleByTime
} from './index';
import type { DegreeWaveCount } from '$lib/utils/finance/elliott-wave';
import type { Candle } from '$lib/utils/finance/candle';

// Helper to build daily candles for future-coordinate tests.
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

// Helper to configure a TimeProjector with the default mock chart + daily candles.
function configureFutureProjector(
	mockData: ReturnType<typeof createMockChartAndSeries>,
	candleCount = 30
): TimeProjector {
	const projector = new TimeProjector();
	projector.attach(mockData.chart);
	projector.updateCandles(createDailyCandles(candleCount));
	return projector;
}

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
			// Last candle (day 30) sits at x = 725; beyond that is the future area
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
		it('defines Cycle, Primary, and Intermediate visual styles with distinct formatting and colors', () => {
			expect(CYCLE_STYLE.degree).toBe('cycle');
			expect(CYCLE_STYLE.color).toBe('#3b82f6');
			expect(CYCLE_STYLE.formatLabel(1)).toBe('I');
			expect(CYCLE_STYLE.formatLabel(2)).toBe('II');
			expect(CYCLE_STYLE.formatLabel(3)).toBe('III');
			expect(CYCLE_STYLE.formatLabel(4)).toBe('IV');
			expect(CYCLE_STYLE.formatLabel(5)).toBe('V');

			expect(PRIMARY_STYLE.degree).toBe('primary');
			expect(PRIMARY_STYLE.color).toBe('#10b981');
			expect(PRIMARY_STYLE.formatLabel(1)).toBe('①');
			expect(PRIMARY_STYLE.formatLabel(2)).toBe('②');
			expect(PRIMARY_STYLE.formatLabel(3)).toBe('③');
			expect(PRIMARY_STYLE.formatLabel(4)).toBe('④');
			expect(PRIMARY_STYLE.formatLabel(5)).toBe('⑤');

			expect(INTERMEDIATE_STYLE.degree).toBe('intermediate');
			expect(INTERMEDIATE_STYLE.formatLabel(1)).toBe('(1)');
			expect(INTERMEDIATE_STYLE.formatLabel(2)).toBe('(2)');
			expect(INTERMEDIATE_STYLE.formatLabel(3)).toBe('(3)');
			expect(INTERMEDIATE_STYLE.formatLabel(4)).toBe('(4)');
			expect(INTERMEDIATE_STYLE.formatLabel(5)).toBe('(5)');

			expect(DEGREE_STYLES.cycle).toBe(CYCLE_STYLE);
			expect(DEGREE_STYLES.primary).toBe(PRIMARY_STYLE);
			expect(DEGREE_STYLES.intermediate).toBe(INTERMEDIATE_STYLE);
			expect(HIT_TEST_RADIUS).toBe(14);
			expect(MAX_WAVE_POINTS).toBe(6);
			expect(MAX_IMPULSE_POINTS).toBe(6);
			expect(MAX_CORRECTIVE_POINTS).toBe(4);
			expect(VERTICAL_LABEL_OFFSET).toBe(14);
			expect(IMPULSE_COLOR).toBe('#22c55e');
			expect(CORRECTIVE_COLOR).toBe('#ef4444');
		});

		it('formats corrective waves for Cycle (A, B, C), Primary (Ⓐ, Ⓑ, Ⓒ), and Intermediate ((A), (B), (C))', () => {
			expect(CYCLE_STYLE.formatLabel('A')).toBe('A');
			expect(CYCLE_STYLE.formatLabel('B')).toBe('B');
			expect(CYCLE_STYLE.formatLabel('C')).toBe('C');

			expect(PRIMARY_STYLE.formatLabel('A')).toBe('Ⓐ');
			expect(PRIMARY_STYLE.formatLabel('B')).toBe('Ⓑ');
			expect(PRIMARY_STYLE.formatLabel('C')).toBe('Ⓒ');

			expect(INTERMEDIATE_STYLE.formatLabel('A')).toBe('(A)');
			expect(INTERMEDIATE_STYLE.formatLabel('B')).toBe('(B)');
			expect(INTERMEDIATE_STYLE.formatLabel('C')).toBe('(C)');

			// Numeric wave with type='corrective' mapping
			expect(CYCLE_STYLE.formatLabel(1, 'corrective')).toBe('A');
			expect(PRIMARY_STYLE.formatLabel(2, 'corrective')).toBe('Ⓑ');
			expect(INTERMEDIATE_STYLE.formatLabel(3, 'corrective')).toBe('(C)');

			// Wave 0 returns empty string
			expect(CYCLE_STYLE.formatLabel(0)).toBe('');
			expect(PRIMARY_STYLE.formatLabel(0)).toBe('');
			expect(INTERMEDIATE_STYLE.formatLabel(0)).toBe('');
		});

		it('getWaveColor colors ALL impulse segments/waves green and ALL corrective red', () => {
			// All impulse wave segments are green; waves 2 and 4 must NOT be red
			expect(getWaveColor(1)).toBe(IMPULSE_COLOR);
			expect(getWaveColor(2)).toBe(IMPULSE_COLOR);
			expect(getWaveColor(3)).toBe(IMPULSE_COLOR);
			expect(getWaveColor(4)).toBe(IMPULSE_COLOR);
			expect(getWaveColor(5)).toBe(IMPULSE_COLOR);
			expect(getWaveColor('impulse')).toBe(IMPULSE_COLOR);

			// All corrective wave segments are red
			expect(getWaveColor('A')).toBe(CORRECTIVE_COLOR);
			expect(getWaveColor('B')).toBe(CORRECTIVE_COLOR);
			expect(getWaveColor('C')).toBe(CORRECTIVE_COLOR);
			expect(getWaveColor('corrective')).toBe(CORRECTIVE_COLOR);
		});

		it('getWaveLabelOffset returns top offset (-14) for peaks and bottom offset (+14) for troughs', () => {
			// Peaks: 1, 3, 5, B -> top offset (-14)
			expect(getWaveLabelOffset(1)).toBe(-14);
			expect(getWaveLabelOffset(3)).toBe(-14);
			expect(getWaveLabelOffset(5)).toBe(-14);
			expect(getWaveLabelOffset('B')).toBe(-14);

			// Troughs: 2, 4, A, C -> bottom offset (+14)
			expect(getWaveLabelOffset(2)).toBe(14);
			expect(getWaveLabelOffset(4)).toBe(14);
			expect(getWaveLabelOffset('A')).toBe(14);
			expect(getWaveLabelOffset('C')).toBe(14);

			// Anchor point 0
			expect(getWaveLabelOffset(0)).toBe(0);
		});

		it('getWaveOrder provides correct sequence for impulse and corrective waves', () => {
			expect(getWaveOrder(0)).toBe(0);
			expect(getWaveOrder(1)).toBe(1);
			expect(getWaveOrder('A')).toBe(1);
			expect(getWaveOrder(2)).toBe(2);
			expect(getWaveOrder('B')).toBe(2);
			expect(getWaveOrder(3)).toBe(3);
			expect(getWaveOrder('C')).toBe(3);
			expect(getWaveOrder(4)).toBe(4);
			expect(getWaveOrder(5)).toBe(5);
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
			expect(state.getWaveCount('intermediate')).toBeNull();
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

		it('tracks activeWaveType and fires waveTypeChanged event', () => {
			expect(state.getActiveWaveType()).toBe('impulse');

			const onTypeChanged = vi.fn();
			state.waveTypeChanged().subscribe(onTypeChanged);

			state.setActiveWaveType('corrective');
			expect(state.getActiveWaveType()).toBe('corrective');
			expect(onTypeChanged).toHaveBeenCalledWith('corrective');

			// Switching to same type does not refire
			onTypeChanged.mockClear();
			state.setActiveWaveType('corrective');
			expect(onTypeChanged).not.toHaveBeenCalled();
		});

		it('draws corrective wave (0, A, B, C) and exits drawing mode after 4 points', () => {
			state.setActiveWaveType('corrective');
			state.setDrawingMode(true);

			const p0 = state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			expect(p0.wave).toBe(0);
			expect(state.isDrawingMode()).toBe(true);

			const pA = state.addPoint({ time: '2024-01-02' as Time, price: 70 });
			expect(pA.wave).toBe('A');
			expect(state.isDrawingMode()).toBe(true);

			const pB = state.addPoint({ time: '2024-01-03' as Time, price: 85 });
			expect(pB.wave).toBe('B');
			expect(state.isDrawingMode()).toBe(true);

			const pC = state.addPoint({ time: '2024-01-04' as Time, price: 60 });
			expect(pC.wave).toBe('C');

			// 4 points placed -> drawing mode automatically ends
			expect(state.isDrawingMode()).toBe(false);

			const count = state.getWaveCount('cycle');
			expect(count?.type).toBe('corrective');
			expect(count?.points.map((p) => p.wave)).toEqual([0, 'A', 'B', 'C']);

			// Adding a 5th point resets and starts a new corrective wave
			const nextPoint = state.addPoint({ time: '2024-01-05' as Time, price: 90 });
			expect(nextPoint.wave).toBe(0);
			expect(state.getPoints('cycle').length).toBe(1);
		});

		it('resets points when switching between impulse and corrective wave types', () => {
			// Start with an impulse wave point
			state.setActiveWaveType('impulse');
			state.addPoint({ time: '2024-01-01' as Time, price: 100 });
			state.addPoint({ time: '2024-01-02' as Time, price: 120 });
			expect(state.getPoints('cycle').length).toBe(2);

			// Switch to corrective -> next point resets
			state.setActiveWaveType('corrective');
			const newP0 = state.addPoint({ time: '2024-01-03' as Time, price: 150 });
			expect(newP0.wave).toBe(0);
			expect(state.getPoints('cycle').length).toBe(1);
			expect(state.getWaveCount('cycle')?.type).toBe('corrective');
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
			state.addPoint({ time: '2024-01-01' as Time, price: 100 }, 'intermediate');

			state.clearWave('cycle');
			expect(state.getWaveCount('cycle')).toBeNull();
			expect(state.getWaveCount('primary')).not.toBeNull();
			expect(state.getWaveCount('intermediate')).not.toBeNull();

			state.clearWave('primary');
			expect(state.getWaveCount('primary')).toBeNull();
			expect(state.getWaveCount('intermediate')).not.toBeNull();

			state.clearWave('intermediate');
			expect(state.getWaveCount('intermediate')).toBeNull();
		});

		it('sets and retrieves full wave counts for all degrees', () => {
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
			const sampleIntermediate: DegreeWaveCount = {
				points: [{ wave: 1, time: '2024-01-08' as Time, price: 120 }],
				wave3Target: 170
			};

			state.setAllWaveCounts({
				cycle: sampleCycle,
				primary: samplePrimary,
				intermediate: sampleIntermediate
			});

			const all = state.getAllWaveCounts();
			expect(all.cycle?.points.length).toBe(2);
			expect(all.cycle?.wave3Target).toBe(180);
			expect(all.primary?.points.length).toBe(1);
			expect(all.primary?.wave3Target).toBe(160);
			expect(all.intermediate?.points.length).toBe(1);
			expect(all.intermediate?.wave3Target).toBe(170);
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

		it('tracks selected degree, fires selectionChanged delegate, and auto-clears on clearWave and setDrawingMode', () => {
			const onSelectionChanged = vi.fn();
			state.selectionChanged().subscribe(onSelectionChanged);

			expect(state.getSelectedDegree()).toBeNull();

			state.setSelectedDegree('cycle');
			expect(state.getSelectedDegree()).toBe('cycle');
			expect(onSelectionChanged).toHaveBeenCalledWith('cycle');

			// Setting same degree again does not re-fire
			onSelectionChanged.mockClear();
			state.setSelectedDegree('cycle');
			expect(onSelectionChanged).not.toHaveBeenCalled();

			// Switch to primary
			state.setSelectedDegree('primary');
			expect(state.getSelectedDegree()).toBe('primary');
			expect(onSelectionChanged).toHaveBeenCalledWith('primary');

			// Entering drawing mode auto-clears selection
			state.setDrawingMode(true);
			expect(state.getSelectedDegree()).toBeNull();
			expect(onSelectionChanged).toHaveBeenCalledWith(null);
			state.setDrawingMode(false);

			// Clearing a selected wave auto-clears selection
			state.setSelectedDegree('cycle');
			expect(state.getSelectedDegree()).toBe('cycle');
			state.clearWave('cycle');
			expect(state.getSelectedDegree()).toBeNull();

			// Clearing a different wave does not clear selection
			state.setSelectedDegree('primary');
			state.clearWave('cycle');
			expect(state.getSelectedDegree()).toBe('primary');
		});
	});

	describe('ElliottWavePaneRenderer (Canvas Drawing)', () => {
		let renderer: ElliottWavePaneRenderer;

		beforeEach(() => {
			renderer = new ElliottWavePaneRenderer();
		});

		it('renders wave segments colored green for impulse and red for corrective, with Roman numerals for Cycle (omits label for wave 0, no badge background)', () => {
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

			// 3 connecting lines should be drawn between wave points (0->1, 1->2, 2->3)
			const lineCalls = drawCalls.filter((c) => c.type === 'lineTo');
			const moveCalls = drawCalls.filter((c) => c.type === 'moveTo');
			expect(lineCalls).toHaveLength(3);
			expect(moveCalls).toHaveLength(3);

			// Should render anchor dot only for wave 0, no badge background circles for points 1, 2, 3
			const arcCalls = drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls).toHaveLength(1);

			// Should render Roman numeral text badges "I", "II", "III" for Cycle, but NOT for wave 0
			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('I');
			expect(labels).toContain('II');
			expect(labels).toContain('III');
			expect(labels).not.toContain('(0)');
			expect(labels).not.toContain('0');
		});

		it('renders Primary degree badges formatted as circled numbers (omits wave 0 label)', () => {
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

			const lineCalls = drawCalls.filter((c) => c.type === 'lineTo');
			expect(lineCalls).toHaveLength(2);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('①');
			expect(labels).toContain('②');
			expect(labels).not.toContain('0');
		});

		it('renders Intermediate degree badges formatted as "(1)", "(2)" (omits wave 0 label)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'intermediate',
						config: INTERMEDIATE_STYLE,
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

			const lineCalls = drawCalls.filter((c) => c.type === 'lineTo');
			expect(lineCalls).toHaveLength(2);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('(1)');
			expect(labels).toContain('(2)');
			expect(labels).not.toContain('(0)');
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

			// Should have at least 2 arc calls (1 for highlight ring, 1 for anchor dot)
			const arcCalls = drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBeGreaterThanOrEqual(2);
		});

		it('renders selection ring around node badges when wave degree is selected', () => {
			const { target, drawCalls, context } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						isSelected: true,
						points: [
							{ wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100, isSelected: true },
							{ wave: 1, x: 150, y: 250, time: '2024-01-02' as Time, price: 120, isSelected: true }
						]
					}
				],
				preview: null
			});

			renderer.draw(target);

			// Should have selection halo for point 0 (1 ring + 1 dot = 2 arcs) and point 1 (1 ring = 1 arc) -> total 3 arcs
			const arcCalls = drawCalls.filter((c) => c.type === 'arc');
			expect(arcCalls.length).toBeGreaterThanOrEqual(2);
			expect(context.fillStyle).toBeDefined();
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
			expect(labels).toContain('I'); // Ghost badge for next wave (Cycle = Roman numeral)
		});

		it('renders drawing preview dashed line and ghost badge for wave 2 (green for impulse)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [
							{ wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100 },
							{ wave: 1, x: 150, y: 250, time: '2024-01-02' as Time, price: 120 }
						]
					}
				],
				preview: {
					degree: 'cycle',
					config: CYCLE_STYLE,
					nextWave: 2,
					lastPoint: { wave: 1, x: 150, y: 250, time: '2024-01-02' as Time, price: 120 },
					currentMouse: { x: 200, y: 280 }
				}
			});

			renderer.draw(target);

			const dashCalls = drawCalls.filter((c) => c.type === 'setLineDash');
			expect(dashCalls.length).toBeGreaterThanOrEqual(1);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('II');
		});

		it('renders drawing preview dashed line and ghost badge for corrective wave A (red)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						type: 'corrective',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [{ wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100 }]
					}
				],
				preview: {
					degree: 'cycle',
					type: 'corrective',
					config: CYCLE_STYLE,
					nextWave: 'A',
					lastPoint: { wave: 0, x: 100, y: 300, time: '2024-01-01' as Time, price: 100 },
					currentMouse: { x: 160, y: 250 }
				}
			});

			renderer.draw(target);

			const dashCalls = drawCalls.filter((c) => c.type === 'setLineDash');
			expect(dashCalls.length).toBeGreaterThanOrEqual(1);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labels = textCalls.map((c) => c.args[0]);
			expect(labels).toContain('A');
		});

		it('renders wave labels with vertical offsets (-14 for peaks, +14 for troughs)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						type: 'impulse',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [
							{ wave: 0, x: 50, y: 320, time: '2024-01-01' as Time, price: 90 },
							{ wave: 1, x: 100, y: 300, time: '2024-01-02' as Time, price: 100 },
							{ wave: 2, x: 150, y: 350, time: '2024-01-03' as Time, price: 80 },
							{ wave: 3, x: 200, y: 200, time: '2024-01-04' as Time, price: 150 }
						]
					}
				],
				preview: null
			});

			renderer.draw(target);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const label1 = textCalls.find((c) => c.args[0] === 'I');
			const label2 = textCalls.find((c) => c.args[0] === 'II');
			const label3 = textCalls.find((c) => c.args[0] === 'III');

			// Peak wave 1: y = (300 - 14) * 2 = 572
			expect(label1?.args[2]).toBe((300 - 14) * 2);
			// Trough wave 2: y = (350 + 14) * 2 = 728
			expect(label2?.args[2]).toBe((350 + 14) * 2);
			// Peak wave 3: y = (200 - 14) * 2 = 372
			expect(label3?.args[2]).toBe((200 - 14) * 2);
		});

		it('renders corrective wave (0, A, B, C) with red segments and offset labels (A below, B above, C below)', () => {
			const { target, drawCalls } = createMockCanvasTarget();

			renderer.update({
				degrees: [
					{
						degree: 'cycle',
						type: 'corrective',
						config: CYCLE_STYLE,
						isActiveDegree: true,
						points: [
							{ wave: 0, x: 50, y: 300, time: '2024-01-01' as Time, price: 100 },
							{ wave: 'A', x: 100, y: 250, time: '2024-01-02' as Time, price: 70 },
							{ wave: 'B', x: 150, y: 200, time: '2024-01-03' as Time, price: 85 },
							{ wave: 'C', x: 200, y: 280, time: '2024-01-04' as Time, price: 60 }
						]
					}
				],
				preview: null
			});

			renderer.draw(target);

			const textCalls = drawCalls.filter((c) => c.type === 'fillText');
			const labelA = textCalls.find((c) => c.args[0] === 'A');
			const labelB = textCalls.find((c) => c.args[0] === 'B');
			const labelC = textCalls.find((c) => c.args[0] === 'C');

			expect(labelA).toBeDefined();
			expect(labelB).toBeDefined();
			expect(labelC).toBeDefined();

			// Wave A (trough): y = (250 + 14) * 2 = 528
			expect(labelA?.args[2]).toBe((250 + 14) * 2);
			// Wave B (peak): y = (200 - 14) * 2 = 372
			expect(labelB?.args[2]).toBe((200 - 14) * 2);
			// Wave C (trough): y = (280 + 14) * 2 = 588
			expect(labelC?.args[2]).toBe((280 + 14) * 2);
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

			// Disabling chart scroll/panning while dragging (pressedMouseMove off)
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: false }
			});

			// 2. Mousemove to new position
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 175, clientY: 230 })
			);
			expect(onDrag).toHaveBeenCalled();
			expect(onDrag.mock.calls[0][0].degree).toBe('cycle');
			expect(onDrag.mock.calls[0][0].wave).toBe(2);
			expect(onDrag.mock.calls[0][0].time).toBeDefined();
			expect(onDrag.mock.calls[0][0].price).toBeDefined();

			// 3. Mouseup on window or chart restores chart scrolling
			window.dispatchEvent(new MouseEvent('mouseup'));
			expect(mouseHandlers.isDragging()).toBe(false);
			expect(onDragEnd).toHaveBeenCalledWith({ degree: 'cycle', wave: 2 });
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: true }
			});
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

		it('fires pointClicked when clicking a wave point in non-drawing mode', () => {
			const onPointClicked = vi.fn();
			const onEmptyAreaClicked = vi.fn();
			mouseHandlers.pointClicked().subscribe(onPointClicked);
			mouseHandlers.emptyAreaClicked().subscribe(onEmptyAreaClicked);

			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 1,
					x: 100,
					y: 200,
					originalPoint: { wave: 1, time: '2024-01-01' as Time, price: 100 }
				}
			]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 102, clientY: 202 })
			);

			expect(onPointClicked).toHaveBeenCalledWith(
				expect.objectContaining({
					degree: 'cycle',
					wave: 1
				})
			);
			expect(onEmptyAreaClicked).not.toHaveBeenCalled();
		});

		it('fires emptyAreaClicked when clicking empty space in plot area in non-drawing mode', () => {
			const onPointClicked = vi.fn();
			const onEmptyAreaClicked = vi.fn();
			mouseHandlers.pointClicked().subscribe(onPointClicked);
			mouseHandlers.emptyAreaClicked().subscribe(onEmptyAreaClicked);

			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 1,
					x: 100,
					y: 200,
					originalPoint: { wave: 1, time: '2024-01-01' as Time, price: 100 }
				}
			]);

			// Click in empty space (x = 300, y = 300)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 300, clientY: 300 })
			);

			expect(onEmptyAreaClicked).toHaveBeenCalledTimes(1);
			expect(onPointClicked).not.toHaveBeenCalled();
		});

		it('does not fire emptyAreaClicked when dragging a point finishes', () => {
			const onEmptyAreaClicked = vi.fn();
			mouseHandlers.emptyAreaClicked().subscribe(onEmptyAreaClicked);

			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 1,
					x: 100,
					y: 200,
					originalPoint: { wave: 1, time: '2024-01-01' as Time, price: 100 }
				}
			]);

			// 1. Mousedown on point 1
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			// 2. Mousemove to drag
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);
			// 3. Mouseup to release
			window.dispatchEvent(new MouseEvent('mouseup'));
			// 4. Click event following mouseup
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 150, clientY: 250 })
			);

			expect(onEmptyAreaClicked).not.toHaveBeenCalled();
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

		it('handles degree switching and separate wave points for Cycle, Primary, and Intermediate', () => {
			primitive.setActiveDegree('cycle');
			primitive.addPoint(100, '2024-01-01' as Time);
			primitive.addPoint(120, '2024-01-02' as Time);

			primitive.setActiveDegree('primary');
			primitive.addPoint(50, '2024-01-10' as Time);

			primitive.setActiveDegree('intermediate');
			primitive.addPoint(70, '2024-01-15' as Time);

			expect(primitive.getPoints('cycle')).toHaveLength(2);
			expect(primitive.getPoints('primary')).toHaveLength(1);
			expect(primitive.getPoints('intermediate')).toHaveLength(1);

			const all = primitive.getAllWaveCounts();
			expect(all.cycle?.points).toHaveLength(2);
			expect(all.primary?.points).toHaveLength(1);
			expect(all.intermediate?.points).toHaveLength(1);
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

	describe('Future Wave Points (beyond last candle)', () => {
		describe('TimeProjector', () => {
			it('derives the bar interval from median candle spacing', () => {
				const candles = createDailyCandles(10);
				expect(computeIntervalSeconds(candles)).toBe(86400);
			});

			it('addIntervalToTime preserves the reference time format', () => {
				expect(addIntervalToTime('2024-01-30', 3, 86400)).toBe('2024-02-02');
				expect(addIntervalToTime(1706601600 as Time, 2, 3600)).toBe(1706608800);
			});

			it('projects a future coordinate to an extrapolated future time', () => {
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);
				mockData.timeScale.coordinateToTime.mockReturnValue(null); // force future path

				// x = 800 -> logical 32 -> 3 bars beyond last (index 29) -> +3 days
				const time = projector.coordinateToTime(800);
				expect(time).toBe('2024-02-02');
			});

			it('projects a future time to an extrapolated x coordinate', () => {
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);
				mockData.timeScale.timeToCoordinate.mockReturnValue(null); // force future path

				// '2024-02-02' is 3 days beyond '2024-01-30' -> logical 32 -> x = 800
				const x = projector.timeToCoordinate('2024-02-02' as Time);
				expect(x).toBe(800);
			});

			it('falls back to the time scale answer within historical data', () => {
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);

				// x = 200 is within data (coordinateToTime returns '2024-01-09')
				expect(projector.coordinateToTime(200)).toBe('2024-01-09');
				// historical time maps back through the time scale
				expect(projector.timeToCoordinate('2024-01-05' as Time)).toBe(100);
			});

			it('returns null when no candle data has been provided', () => {
				const mockData = createMockChartAndSeries();
				const projector = new TimeProjector();
				projector.attach(mockData.chart);
				mockData.timeScale.coordinateToTime.mockReturnValue(null);

				expect(projector.coordinateToTime(800)).toBeNull();
				expect(projector.timeToCoordinate('2024-02-02' as Time)).toBeNull();
			});
		});

		it('fires chartClicked with an extrapolated future time when clicking in the future area', () => {
			const mouseHandlers = new MouseHandlers();
			const mockData = createMockChartAndSeries();
			const projector = configureFutureProjector(mockData);
			mouseHandlers.attached(mockData.chart, mockData.series, projector);

			const onChartClicked = vi.fn();
			mouseHandlers.chartClicked().subscribe(onChartClicked);
			mouseHandlers.setDrawingMode(true);

			// x = 750 is one whole bar beyond the last candle (x > 725) but still
			// inside the plot area (<= 750) -> future placement
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 750, clientY: 150 })
			);

			expect(onChartClicked).toHaveBeenCalledWith(
				expect.objectContaining({
					x: 750,
					time: '2024-01-31',
					price: expect.any(Number)
				})
			);
		});

		it('fires pointDragged with an extrapolated future time when dragging a point into the future area', () => {
			const mouseHandlers = new MouseHandlers();
			const mockData = createMockChartAndSeries();
			const projector = configureFutureProjector(mockData);
			mouseHandlers.attached(mockData.chart, mockData.series, projector);

			const onDrag = vi.fn();
			mouseHandlers.pointDragged().subscribe(onDrag);

			mouseHandlers.setProjectedPoints([
				{
					degree: 'cycle',
					wave: 1,
					x: 100,
					y: 200,
					originalPoint: { wave: 1, time: '2024-01-05' as Time, price: 100 }
				}
			]);

			// mousedown on the point, then drag into the future area (x = 750)
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 750, clientY: 230 })
			);

			expect(onDrag).toHaveBeenCalledWith(
				expect.objectContaining({
					degree: 'cycle',
					wave: 1,
					time: '2024-01-31'
				})
			);
		});

		it('renders a wave point at its future position via logical projection', () => {
			const primitive = new ElliottWavesPrimitive({ activeDegree: 'cycle' });
			const mockData = createMockChartAndSeries();
			const mockRequestUpdate = vi.fn();
			primitive.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: mockRequestUpdate,
				horzScaleBehavior: {} as never
			});
			primitive.setCandles(createDailyCandles(30));

			// Add a point at a genuinely future time (beyond the '2024-01-*' data
			// so the time scale returns null and the projector extrapolates).
			primitive.addPoint(150, '2024-02-02' as Time, 'cycle');

			primitive.updateAllViews();
			// '2024-02-02' is 3 days beyond '2024-01-30' -> logical 32 -> x = 800
			expect(mockData.timeScale.logicalToCoordinate).toHaveBeenCalled();
			const projected = (
				primitive as unknown as {
					_paneViews: { renderer(): { _data: unknown } }[];
				}
			)._paneViews[0].renderer()._data as {
				degrees: { points: { x: number }[] }[];
			};
			expect(projected.degrees[0].points[0].x).toBe(800);
		});
	});

	describe('Snap to Candle Wicks', () => {
		describe('snapPriceToWick', () => {
			const candle: Candle = {
				time: '2024-01-01',
				open: 100,
				high: 110,
				low: 90,
				close: 105
			};

			it('snaps to high wick when pointer is closer to high', () => {
				expect(snapPriceToWick(106, candle)).toBe(110);
			});

			it('snaps to low wick when pointer is closer to low', () => {
				expect(snapPriceToWick(94, candle)).toBe(90);
			});

			it('resolves exact midpoint tie to high wick', () => {
				// Midpoint of 110 and 90 is 100 (distance = 10 to both)
				expect(snapPriceToWick(100, candle)).toBe(110);
			});

			it('snaps to high wick when pointer price is above candle high', () => {
				expect(snapPriceToWick(125, candle)).toBe(110);
			});

			it('snaps to low wick when pointer price is below candle low', () => {
				expect(snapPriceToWick(75, candle)).toBe(90);
			});

			it('handles candle with equal high and low', () => {
				const flatCandle: Candle = {
					time: '2024-01-01',
					open: 100,
					high: 100,
					low: 100,
					close: 100
				};
				expect(snapPriceToWick(105, flatCandle)).toBe(100);
				expect(snapPriceToWick(95, flatCandle)).toBe(100);
			});
		});

		describe('buildCandleLookup & findCandleByTime', () => {
			const candles = createDailyCandles(5);
			const lookup = buildCandleLookup(candles);

			it('finds candle by string date', () => {
				const candle = findCandleByTime(lookup, '2024-01-03' as Time);
				expect(candle).toBeDefined();
				expect(candle?.time).toBe('2024-01-03');
				expect(candle?.high).toBe(112);
			});

			it('finds candle by epoch seconds number', () => {
				const epoch = Math.floor(new Date('2024-01-03T00:00:00Z').getTime() / 1000);
				const candle = findCandleByTime(lookup, epoch as Time);
				expect(candle).toBeDefined();
				expect(candle?.time).toBe('2024-01-03');
			});

			it('finds candle by BusinessDay object', () => {
				const busDay: Time = { year: 2024, month: 1, day: 3 } as never;
				const candle = findCandleByTime(lookup, busDay);
				expect(candle).toBeDefined();
				expect(candle?.time).toBe('2024-01-03');
			});

			it('returns undefined for non-existent time, null, or undefined', () => {
				expect(findCandleByTime(lookup, '2024-05-01' as Time)).toBeUndefined();
				expect(findCandleByTime(lookup, null)).toBeUndefined();
				expect(findCandleByTime(lookup, undefined)).toBeUndefined();
			});
		});

		describe('MouseHandlers Wick Snapping', () => {
			it('emits raw mouse price when snapToWicks is false (default)', () => {
				const mouseHandlers = new MouseHandlers();
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);
				mouseHandlers.attached(mockData.chart, mockData.series, projector);
				mouseHandlers.setCandles(createDailyCandles(30));
				mouseHandlers.setDrawingMode(true);

				expect(mouseHandlers.getSnapToWicks()).toBe(false);

				const onChartClicked = vi.fn();
				mouseHandlers.chartClicked().subscribe(onChartClicked);

				// clientX: 100 (day 5: high 114, low 99), clientY: 460 (price: 200 - 460*0.2 = 108)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 100, clientY: 460 })
				);

				expect(onChartClicked).toHaveBeenCalledWith({
					time: '2024-01-05',
					price: 108,
					x: 100,
					y: 460
				});
			});

			it('snaps placement click to nearest candle wick when snapToWicks is true', () => {
				const mouseHandlers = new MouseHandlers();
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);
				mouseHandlers.attached(mockData.chart, mockData.series, projector);
				mouseHandlers.setCandles(createDailyCandles(30));
				mouseHandlers.setDrawingMode(true);
				mouseHandlers.setSnapToWicks(true);

				expect(mouseHandlers.getSnapToWicks()).toBe(true);

				const onChartClicked = vi.fn();
				mouseHandlers.chartClicked().subscribe(onChartClicked);

				// clientX: 350 (day 15: high 124, low 109), clientY: 390 (price: 200 - 390*0.2 = 122, closer to 124)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 350, clientY: 390 })
				);

				expect(onChartClicked).toHaveBeenCalledWith({
					time: '2024-01-15',
					price: 124,
					x: 350,
					y: (200 - 124) / 0.2 // 380
				});

				// clientY: 440 (price: 112, closer to low 109)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 350, clientY: 440 })
				);

				expect(onChartClicked).toHaveBeenCalledWith({
					time: '2024-01-15',
					price: 109,
					x: 350,
					y: (200 - 109) / 0.2 // 455
				});
			});

			it('snaps drag moves to nearest candle wick when snapToWicks is true', () => {
				const mouseHandlers = new MouseHandlers();
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);
				mouseHandlers.attached(mockData.chart, mockData.series, projector);
				mouseHandlers.setCandles(createDailyCandles(30));
				mouseHandlers.setSnapToWicks(true);

				const onPointDragged = vi.fn();
				mouseHandlers.pointDragged().subscribe(onPointDragged);

				mouseHandlers.setProjectedPoints([
					{
						degree: 'cycle',
						wave: 1,
						x: 50,
						y: 100,
						originalPoint: { wave: 1, time: '2024-01-03' as Time, price: 112 }
					}
				]);

				// mousedown on point
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('mousedown', { clientX: 50, clientY: 100 })
				);

				// mousemove to day 15 (clientX: 350) with clientY: 390 (price 122 -> snaps to high 124)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('mousemove', { clientX: 350, clientY: 390 })
				);

				expect(onPointDragged).toHaveBeenCalledWith({
					degree: 'cycle',
					wave: 1,
					time: '2024-01-15',
					price: 124,
					x: 350,
					y: (200 - 124) / 0.2
				});
			});

			it('does not snap click or drag in the future projection area', () => {
				const mouseHandlers = new MouseHandlers();
				const mockData = createMockChartAndSeries();
				const projector = configureFutureProjector(mockData);
				mouseHandlers.attached(mockData.chart, mockData.series, projector);
				mouseHandlers.setCandles(createDailyCandles(30));
				mouseHandlers.setDrawingMode(true);
				mouseHandlers.setSnapToWicks(true);

				const onChartClicked = vi.fn();
				mouseHandlers.chartClicked().subscribe(onChartClicked);

				// clientX: 750 (future area -> '2024-01-31'), clientY: 460 (price: 108)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 750, clientY: 460 })
				);

				expect(onChartClicked).toHaveBeenCalledWith({
					time: '2024-01-31',
					price: 108,
					x: 750,
					y: 460
				});
			});
		});

		describe('ElliottWavesPrimitive Snap and Preview Ghost', () => {
			it('initializes snapToWicks from constructor and updates via setter', () => {
				const defaultPrimitive = new ElliottWavesPrimitive();
				expect(defaultPrimitive.getSnapToWicks()).toBe(false);

				const snapPrimitive = new ElliottWavesPrimitive({ snapToWicks: true });
				expect(snapPrimitive.getSnapToWicks()).toBe(true);

				snapPrimitive.setSnapToWicks(false);
				expect(snapPrimitive.getSnapToWicks()).toBe(false);
			});

			it('renders drawing preview currentMouse at raw pointer y when snapToWicks is false', () => {
				const primitive = new ElliottWavesPrimitive({ activeDegree: 'cycle', snapToWicks: false });
				const mockData = createMockChartAndSeries();
				const mockRequestUpdate = vi.fn();
				primitive.attached({
					chart: mockData.chart,
					series: mockData.series,
					requestUpdate: mockRequestUpdate,
					horzScaleBehavior: {} as never
				});
				primitive.setCandles(createDailyCandles(30));
				primitive.setDrawingMode(true);

				// Move mouse to day 5 (clientX: 100), clientY: 460 (price 108)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('mousemove', { clientX: 100, clientY: 460 })
				);

				primitive.updateAllViews();
				const rendererData = (
					primitive as unknown as {
						_paneViews: { renderer(): { _data: unknown } }[];
					}
				)._paneViews[0].renderer()._data as {
					preview: { currentMouse: { x: number; y: number } };
				};

				expect(rendererData.preview.currentMouse).toEqual({
					x: 100,
					y: 460
				});
			});

			it('renders drawing preview currentMouse at snapped wick y when snapToWicks is true', () => {
				const primitive = new ElliottWavesPrimitive({ activeDegree: 'cycle', snapToWicks: true });
				const mockData = createMockChartAndSeries();
				const mockRequestUpdate = vi.fn();
				primitive.attached({
					chart: mockData.chart,
					series: mockData.series,
					requestUpdate: mockRequestUpdate,
					horzScaleBehavior: {} as never
				});
				primitive.setCandles(createDailyCandles(30));
				primitive.setDrawingMode(true);

				// Move mouse to day 5 (clientX: 100, high 114, low 99), clientY: 460 (price 108 -> snaps to high 114)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('mousemove', { clientX: 100, clientY: 460 })
				);

				primitive.updateAllViews();
				const rendererData = (
					primitive as unknown as {
						_paneViews: { renderer(): { _data: unknown } }[];
					}
				)._paneViews[0].renderer()._data as {
					preview: { currentMouse: { x: number; y: number } };
				};

				expect(rendererData.preview.currentMouse).toEqual({
					x: 100,
					y: (200 - 114) / 0.2 // 430
				});
			});

			it('renders drawing preview currentMouse at raw y in future area even when snapToWicks is true', () => {
				const primitive = new ElliottWavesPrimitive({ activeDegree: 'cycle', snapToWicks: true });
				const mockData = createMockChartAndSeries();
				const mockRequestUpdate = vi.fn();
				primitive.attached({
					chart: mockData.chart,
					series: mockData.series,
					requestUpdate: mockRequestUpdate,
					horzScaleBehavior: {} as never
				});
				primitive.setCandles(createDailyCandles(30));
				primitive.setDrawingMode(true);

				// Move mouse to future area (clientX: 750), clientY: 460
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('mousemove', { clientX: 750, clientY: 460 })
				);

				primitive.updateAllViews();
				const rendererData = (
					primitive as unknown as {
						_paneViews: { renderer(): { _data: unknown } }[];
					}
				)._paneViews[0].renderer()._data as {
					preview: { currentMouse: { x: number; y: number } };
				};

				expect(rendererData.preview.currentMouse).toEqual({
					x: 750,
					y: 460
				});
			});
		});

		describe('ElliottWavesPrimitive Selection Integration', () => {
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

			it('initializes selectedDegree from constructor and updates via setSelectedDegree', () => {
				const defaultPrimitive = new ElliottWavesPrimitive();
				expect(defaultPrimitive.getSelectedDegree()).toBeNull();

				const selectedPrimitive = new ElliottWavesPrimitive({ selectedDegree: 'primary' });
				expect(selectedPrimitive.getSelectedDegree()).toBe('primary');

				selectedPrimitive.setSelectedDegree('cycle');
				expect(selectedPrimitive.getSelectedDegree()).toBe('cycle');

				selectedPrimitive.setSelectedDegree(null);
				expect(selectedPrimitive.getSelectedDegree()).toBeNull();
			});

			it('selects wave degree on point click and deselects on empty space click', () => {
				primitive.addPoint(100, '2024-01-05' as Time, 'cycle');
				primitive.addPoint(120, '2024-01-06' as Time, 'primary');
				primitive.updateAllViews();

				expect(primitive.getSelectedDegree()).toBeNull();

				// Click on cycle point 0 (x: 100, y: 500)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 100, clientY: 500 })
				);
				expect(primitive.getSelectedDegree()).toBe('cycle');

				// Click on empty space (x: 300, y: 300)
				mockData.mockChartElement.dispatchEvent(
					new MouseEvent('click', { clientX: 300, clientY: 300 })
				);
				expect(primitive.getSelectedDegree()).toBeNull();
			});

			it('fires selectionChanged subscription when selected degree changes', () => {
				const onSelectionChanged = vi.fn();
				primitive.selectionChanged().subscribe(onSelectionChanged);

				primitive.setSelectedDegree('cycle');
				expect(onSelectionChanged).toHaveBeenCalledWith('cycle');

				primitive.setSelectedDegree(null);
				expect(onSelectionChanged).toHaveBeenCalledWith(null);
			});
		});
	});
});
