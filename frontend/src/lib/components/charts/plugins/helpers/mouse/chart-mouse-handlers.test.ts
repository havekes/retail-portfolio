import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { IChartApi, ISeriesApi, SeriesType, Time } from 'lightweight-charts';
import { ChartMouseHandlers, type ChartMouseHandlersConfig } from './chart-mouse-handlers';

interface TestOriginalPoint {
	label: string;
}

interface TestPoint {
	id: number;
	x: number;
	y: number;
	originalPoint: TestOriginalPoint;
}

interface TestTarget {
	id: number;
}

const TEST_RADIUS = 14;

function makePoint(id: number, x: number, y: number): TestPoint {
	return { id, x, y, originalPoint: { label: `point-${id}` } };
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

function makeHandlers(config?: Partial<ChartMouseHandlersConfig<TestPoint, TestTarget>>) {
	return new ChartMouseHandlers<TestPoint, TestTarget, TestOriginalPoint>({
		hitTestRadius: TEST_RADIUS,
		toTarget: (p) => ({ id: p.id }),
		...config
	});
}

describe('ChartMouseHandlers', () => {
	let handlers: ChartMouseHandlers<TestPoint, TestTarget, TestOriginalPoint>;
	let mockData: ReturnType<typeof createMockChartAndSeries>;

	beforeEach(() => {
		handlers = makeHandlers();
		mockData = createMockChartAndSeries();
		handlers.attached(mockData.chart, mockData.series);
	});

	describe('hitTestPoint boundary semantics', () => {
		it('hits a point at exactly hitTestRadius distance (inclusive boundary)', () => {
			handlers.setProjectedPoints([makePoint(1, 100, 200)]);

			// dist = 14 (exactly on the radius boundary) -> hit
			expect(handlers.hitTestPoint(114, 200)?.id).toBe(1);
			expect(handlers.hitTestPoint(100, 214)?.id).toBe(1);
		});

		it('misses a point just beyond hitTestRadius', () => {
			handlers.setProjectedPoints([makePoint(1, 100, 200)]);

			// dist = 15 (one pixel beyond the radius) -> miss
			expect(handlers.hitTestPoint(115, 200)).toBeNull();
			expect(handlers.hitTestPoint(100, 215)).toBeNull();
		});

		it('resolves exact-distance ties first-wins (earliest point in the array wins)', () => {
			handlers.setProjectedPoints([
				makePoint(1, 100, 200),
				makePoint(2, 100, 200),
				makePoint(3, 114, 200)
			]);

			// Query at (107, 200): dist to points 1 and 2 is 7, dist to point 3 is 7.
			// First point in the array at that distance wins.
			const hit = handlers.hitTestPoint(107, 200);
			expect(hit?.id).toBe(1);
		});

		it('keeps the closest point when distances differ', () => {
			handlers.setProjectedPoints([makePoint(1, 100, 200), makePoint(2, 110, 200)]);

			expect(handlers.hitTestPoint(100, 200)?.id).toBe(1);
			expect(handlers.hitTestPoint(106, 200)?.id).toBe(2);
		});
	});

	describe('adjustPosition hook', () => {
		it('applies the hook to the pointDragged payload during a drag', () => {
			const adjustPosition = vi.fn(() => ({ price: 123, y: 321 }));
			handlers = makeHandlers({ adjustPosition });
			handlers.attached(mockData.chart, mockData.series);

			const onPointDragged = vi.fn();
			handlers.pointDragged().subscribe(onPointDragged);
			handlers.setProjectedPoints([makePoint(1, 100, 200)]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			expect(onPointDragged).toHaveBeenCalledWith({
				id: 1,
				time: '2024-01-07',
				price: 123,
				x: 150,
				y: 321
			});
			expect(adjustPosition).toHaveBeenCalledWith(
				expect.objectContaining({ x: 150, y: 250, price: 150, time: '2024-01-07' }),
				mockData.series
			);
		});

		it('applies the hook to the chartClicked payload on a draw-mode click', () => {
			const adjustPosition = vi.fn(() => ({ price: 123, y: 321 }));
			handlers = makeHandlers({ adjustPosition });
			handlers.attached(mockData.chart, mockData.series);
			handlers.setDrawingMode(true);

			const onChartClicked = vi.fn();
			handlers.chartClicked().subscribe(onChartClicked);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 150, clientY: 250 })
			);

			expect(onChartClicked).toHaveBeenCalledWith({
				time: '2024-01-07',
				price: 123,
				x: 150,
				y: 321
			});
		});

		it('passes the raw position through when no hook is configured (drag path)', () => {
			const onPointDragged = vi.fn();
			handlers.pointDragged().subscribe(onPointDragged);
			handlers.setProjectedPoints([makePoint(1, 100, 200)]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			expect(onPointDragged).toHaveBeenCalledWith({
				id: 1,
				time: '2024-01-07',
				price: 150,
				x: 150,
				y: 250
			});
		});

		it('passes the raw position through when no hook is configured (draw-click path)', () => {
			handlers.setDrawingMode(true);

			const onChartClicked = vi.fn();
			handlers.chartClicked().subscribe(onChartClicked);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('click', { clientX: 150, clientY: 250 })
			);

			expect(onChartClicked).toHaveBeenCalledWith({
				time: '2024-01-07',
				price: 150,
				x: 150,
				y: 250
			});
		});
	});

	describe('drag lifecycle and scroll lock', () => {
		it('locks chart scrolling on drag start, fires drag events, restores on drag end', () => {
			const onDragStarted = vi.fn();
			const onPointDragged = vi.fn();
			const onDragEnded = vi.fn();
			handlers.dragStarted().subscribe(onDragStarted);
			handlers.pointDragged().subscribe(onPointDragged);
			handlers.dragEnded().subscribe(onDragEnded);

			handlers.setProjectedPoints([makePoint(1, 100, 200)]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);

			expect(handlers.isDragging()).toBe(true);
			expect(handlers.getDragTarget()).toEqual({ id: 1 });
			expect(onDragStarted).toHaveBeenCalledWith({ id: 1 });
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: false }
			});

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousemove', { clientX: 150, clientY: 250 })
			);

			expect(onPointDragged).toHaveBeenCalledWith(
				expect.objectContaining({ id: 1, x: 150, y: 250 })
			);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mouseup', { clientX: 150, clientY: 250 })
			);

			expect(handlers.isDragging()).toBe(false);
			expect(handlers.getDragTarget()).toBeNull();
			expect(onDragEnded).toHaveBeenCalledWith({ id: 1 });
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: true }
			});
		});

		it('restores chart scroll when detached mid-drag', () => {
			handlers.setProjectedPoints([makePoint(1, 100, 200)]);

			mockData.mockChartElement.dispatchEvent(
				new MouseEvent('mousedown', { clientX: 100, clientY: 200 })
			);
			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: false }
			});

			handlers.detached();

			expect(mockData.chart.applyOptions).toHaveBeenCalledWith({
				handleScroll: { pressedMouseMove: true }
			});
			expect(handlers.isDragging()).toBe(false);
		});
	});

	describe('listener lifecycle', () => {
		it('detached() removes all attached DOM listeners', () => {
			const elementRemoveSpy = vi.spyOn(mockData.mockChartElement, 'removeEventListener');
			const windowRemoveSpy = vi.spyOn(window, 'removeEventListener');

			handlers.detached();

			const removedElementEvents = elementRemoveSpy.mock.calls.map((call) => call[0]);
			expect(removedElementEvents).toEqual(
				expect.arrayContaining(['mousemove', 'mousedown', 'mouseup', 'click', 'mouseleave'])
			);
			expect(windowRemoveSpy).toHaveBeenCalledWith('mouseup', expect.any(Function));
		});
	});
});
