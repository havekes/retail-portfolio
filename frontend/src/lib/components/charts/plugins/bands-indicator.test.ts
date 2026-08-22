import { describe, it, expect, vi, beforeEach } from 'vitest';
import type {
	IChartApi,
	ISeriesApi,
	SeriesType,
	Time,
	SeriesAttachedParameter
} from 'lightweight-charts';
import { BandsIndicator, type BandData } from './bands-indicator';

interface BitmapScope {
	context: CanvasRenderingContext2D;
	horizontalPixelRatio: number;
	verticalPixelRatio: number;
}

interface CanvasTarget {
	useBitmapCoordinateSpace: (cb: (scope: BitmapScope) => void) => void;
}

function createMockChartAndSeries() {
	const timeScale = {
		timeToCoordinate: vi.fn((time: Time) => {
			if (typeof time === 'string' && time.startsWith('2024-01-')) {
				const day = parseInt(time.replace('2024-01-', ''), 10);
				return (day - 1) * 50;
			}
			return null;
		}),
		coordinateToTime: vi.fn(() => null),
		width: vi.fn(() => 800),
		height: vi.fn(() => 30)
	};

	const priceScale = {
		width: vi.fn(() => 50),
		applyOptions: vi.fn()
	};

	const series = {
		priceToCoordinate: vi.fn((price: number) => {
			if (price < 0 || price > 500) return null;
			// Higher price = lower Y coordinate in chart space
			return (500 - price) * 0.5;
		}),
		coordinateToPrice: vi.fn((y: number) => 500 - y / 0.5),
		priceScale: vi.fn(() => priceScale)
	} as unknown as ISeriesApi<SeriesType>;

	const chart = {
		timeScale: vi.fn(() => timeScale),
		chartElement: vi.fn(() => document.createElement('div')),
		applyOptions: vi.fn()
	} as unknown as IChartApi;

	return { chart, series, timeScale, priceScale };
}

function createMockCanvasTarget() {
	const drawCalls: { type: string; args: unknown[] }[] = [];
	const context = {
		save: vi.fn(() => drawCalls.push({ type: 'save', args: [] })),
		restore: vi.fn(() => drawCalls.push({ type: 'restore', args: [] })),
		beginPath: vi.fn(() => drawCalls.push({ type: 'beginPath', args: [] })),
		moveTo: vi.fn((x: number, y: number) => drawCalls.push({ type: 'moveTo', args: [x, y] })),
		lineTo: vi.fn((x: number, y: number) => drawCalls.push({ type: 'lineTo', args: [x, y] })),
		fill: vi.fn(() => drawCalls.push({ type: 'fill', args: [] })),
		fillStyle: '',
		strokeStyle: '',
		lineWidth: 1
	} as unknown as CanvasRenderingContext2D;

	const scope: BitmapScope = {
		context,
		horizontalPixelRatio: 2,
		verticalPixelRatio: 2
	};

	const target: CanvasTarget = {
		useBitmapCoordinateSpace: vi.fn((callback: (s: BitmapScope) => void) => {
			callback(scope);
		})
	};

	return { target, context, scope, drawCalls };
}

describe('BandsIndicator Plugin', () => {
	const sampleData: BandData[] = [
		{ time: '2024-01-01' as Time, upper: 120, lower: 90 },
		{ time: '2024-01-02' as Time, upper: 130, lower: 95 },
		{ time: '2024-01-03' as Time, upper: 125, lower: 92 }
	];
	const sampleColor = 'rgba(76, 175, 80, 0.2)';

	describe('Lifecycle and View Management', () => {
		it('instantiates pane views and returns zOrder of bottom', () => {
			const indicator = new BandsIndicator(sampleData, sampleColor);
			const views = indicator.paneViews();

			expect(views).toHaveLength(1);
			expect(views[0].zOrder()).toBe('bottom');
		});

		it('attaches chart and series, requesting a render update', () => {
			const indicator = new BandsIndicator(sampleData, sampleColor);
			const { chart, series } = createMockChartAndSeries();
			const requestUpdate = vi.fn();

			const attachParam: SeriesAttachedParameter<Time, SeriesType> = {
				chart,
				series,
				requestUpdate,
				horzScaleBehavior: {} as never
			};

			indicator.attached(attachParam);
			expect(requestUpdate).toHaveBeenCalledTimes(1);
		});

		it('allows calling updateAllViews without throwing', () => {
			const indicator = new BandsIndicator(sampleData, sampleColor);
			expect(() => indicator.updateAllViews()).not.toThrow();
		});

		it('resets chart and series references on detached', () => {
			const indicator = new BandsIndicator(sampleData, sampleColor);
			const { chart, series } = createMockChartAndSeries();
			const requestUpdate = vi.fn();

			indicator.attached({ chart, series, requestUpdate, horzScaleBehavior: {} as never });
			indicator.detached();

			// After detaching, renderer created by pane view has null chart/series and draw no-ops
			const views = indicator.paneViews();
			const renderer = views[0].renderer();
			const { target } = createMockCanvasTarget();

			renderer?.draw(target);
			expect(target.useBitmapCoordinateSpace).not.toHaveBeenCalled();
		});
	});

	describe('BandRenderer Drawing and Geometry', () => {
		let mockData: ReturnType<typeof createMockChartAndSeries>;
		let mockCanvas: ReturnType<typeof createMockCanvasTarget>;

		beforeEach(() => {
			mockData = createMockChartAndSeries();
			mockCanvas = createMockCanvasTarget();
		});

		it('no-ops when data array is empty', () => {
			const indicator = new BandsIndicator([], sampleColor);
			indicator.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: vi.fn(),
				horzScaleBehavior: {} as never
			});

			const renderer = indicator.paneViews()[0].renderer();
			renderer?.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).not.toHaveBeenCalled();
		});

		it('no-ops when chart or series is not attached', () => {
			const indicator = new BandsIndicator(sampleData, sampleColor);
			// Not calling indicator.attached()
			const renderer = indicator.paneViews()[0].renderer();
			renderer?.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).not.toHaveBeenCalled();
		});

		it('renders polygon with upper edge left-to-right and lower edge right-to-left', () => {
			const indicator = new BandsIndicator(sampleData, sampleColor);
			indicator.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: vi.fn(),
				horzScaleBehavior: {} as never
			});

			const renderer = indicator.paneViews()[0].renderer();
			renderer?.draw(mockCanvas.target);

			expect(mockCanvas.target.useBitmapCoordinateSpace).toHaveBeenCalledTimes(1);

			// Pixel ratio is 2
			// Data points:
			// Item 0: 2024-01-01 -> time x = 0, upper 120 -> y = (500-120)*0.5 = 190, lower 90 -> y = (500-90)*0.5 = 205
			//   scaled px = 0, upper py = 380, lower py = 410
			// Item 1: 2024-01-02 -> time x = 50, upper 130 -> y = (500-130)*0.5 = 185, lower 95 -> y = (500-95)*0.5 = 202.5
			//   scaled px = 100, upper py = 370, lower py = 405
			// Item 2: 2024-01-03 -> time x = 100, upper 125 -> y = (500-125)*0.5 = 187.5, lower 92 -> y = (500-92)*0.5 = 204
			//   scaled px = 200, upper py = 375, lower py = 408

			// Upper edge left to right:
			// 1. moveTo(0, 380)
			// 2. lineTo(100, 370)
			// 3. lineTo(200, 375)
			// Lower edge right to left:
			// 4. lineTo(200, 408)
			// 5. lineTo(100, 405)
			// 6. lineTo(0, 410)

			expect(mockCanvas.drawCalls[0]).toEqual({ type: 'beginPath', args: [] });
			expect(mockCanvas.drawCalls[1]).toEqual({ type: 'moveTo', args: [0, 380] });
			expect(mockCanvas.drawCalls[2]).toEqual({ type: 'lineTo', args: [100, 370] });
			expect(mockCanvas.drawCalls[3]).toEqual({ type: 'lineTo', args: [200, 375] });
			expect(mockCanvas.drawCalls[4]).toEqual({ type: 'lineTo', args: [200, 408] });
			expect(mockCanvas.drawCalls[5]).toEqual({ type: 'lineTo', args: [100, 405] });
			expect(mockCanvas.drawCalls[6]).toEqual({ type: 'lineTo', args: [0, 410] });
			expect(mockCanvas.drawCalls[7]).toEqual({ type: 'fill', args: [] });

			expect(mockCanvas.context.fillStyle).toBe(sampleColor);
		});

		it('skips items where timeToCoordinate returns null', () => {
			const dataWithUnknownTime: BandData[] = [
				{ time: 'unknown-date' as Time, upper: 120, lower: 90 }, // timeToCoordinate returns null
				{ time: '2024-01-02' as Time, upper: 130, lower: 95 },
				{ time: '2024-01-03' as Time, upper: 125, lower: 92 }
			];

			const indicator = new BandsIndicator(dataWithUnknownTime, sampleColor);
			indicator.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: vi.fn(),
				horzScaleBehavior: {} as never
			});

			const renderer = indicator.paneViews()[0].renderer();
			renderer?.draw(mockCanvas.target);

			// Item 0 is skipped; Item 1 becomes the first point and calls moveTo
			const moveCalls = mockCanvas.drawCalls.filter((c) => c.type === 'moveTo');
			expect(moveCalls).toHaveLength(1);
			expect(moveCalls[0].args).toEqual([100, 370]);

			// Total lineTo calls should be 3 (1 for remaining upper item 2, 2 for lower items 2 and 1)
			const lineCalls = mockCanvas.drawCalls.filter((c) => c.type === 'lineTo');
			expect(lineCalls).toHaveLength(3);
			expect(mockCanvas.drawCalls).toContainEqual({ type: 'fill', args: [] });
		});

		it('skips coordinates where priceToCoordinate returns null', () => {
			const dataWithOutOfRangePrice: BandData[] = [
				{ time: '2024-01-01' as Time, upper: 600, lower: 90 }, // upper > 500 => priceToCoordinate is null
				{ time: '2024-01-02' as Time, upper: 130, lower: -10 }, // lower < 0 => priceToCoordinate is null
				{ time: '2024-01-03' as Time, upper: 125, lower: 92 }
			];

			const indicator = new BandsIndicator(dataWithOutOfRangePrice, sampleColor);
			indicator.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: vi.fn(),
				horzScaleBehavior: {} as never
			});

			const renderer = indicator.paneViews()[0].renderer();
			renderer?.draw(mockCanvas.target);

			// Upper pass:
			// - item 0: upper is null -> skipped
			// - item 1: upper 130 -> valid -> moveTo(100, 370)
			// - item 2: upper 125 -> valid -> lineTo(200, 375)
			// Lower pass (reverse: 2, 1, 0):
			// - item 2: lower 92 -> valid -> lineTo(200, 408)
			// - item 1: lower -10 -> null -> skipped
			// - item 0: lower 90 -> valid -> lineTo(0, 410)

			expect(mockCanvas.drawCalls[0]).toEqual({ type: 'beginPath', args: [] });
			expect(mockCanvas.drawCalls[1]).toEqual({ type: 'moveTo', args: [100, 370] });
			expect(mockCanvas.drawCalls[2]).toEqual({ type: 'lineTo', args: [200, 375] });
			expect(mockCanvas.drawCalls[3]).toEqual({ type: 'lineTo', args: [200, 408] });
			expect(mockCanvas.drawCalls[4]).toEqual({ type: 'lineTo', args: [0, 410] });
			expect(mockCanvas.drawCalls[5]).toEqual({ type: 'fill', args: [] });
		});

		it('executes beginPath and fill without points when all coordinates return null', () => {
			mockData.timeScale.timeToCoordinate.mockReturnValue(null);

			const indicator = new BandsIndicator(sampleData, sampleColor);
			indicator.attached({
				chart: mockData.chart,
				series: mockData.series,
				requestUpdate: vi.fn(),
				horzScaleBehavior: {} as never
			});

			const renderer = indicator.paneViews()[0].renderer();
			renderer?.draw(mockCanvas.target);

			expect(mockCanvas.drawCalls).toEqual([
				{ type: 'beginPath', args: [] },
				{ type: 'fill', args: [] }
			]);
		});
	});
});
