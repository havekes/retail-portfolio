import { describe, it, expect, vi } from 'vitest';
import type {
	IChartApi,
	ISeriesApi,
	SeriesType,
	Time,
	SeriesAttachedParameter
} from 'lightweight-charts';
import { ValuationBandPrimitive, type CanvasTarget } from './valuation-band';

function createMockChartAndSeries() {
	const priceScale = {
		width: vi.fn(() => 50),
		applyOptions: vi.fn()
	};

	const series = {
		priceToCoordinate: vi.fn((price: number) => {
			if (price < 0 || price > 500) return null;
			return (500 - price) * 0.5;
		}),
		coordinateToPrice: vi.fn((y: number) => 500 - y / 0.5),
		priceScale: vi.fn(() => priceScale)
	} as unknown as ISeriesApi<SeriesType>;

	const chart = {
		timeScale: vi.fn(() => ({})),
		applyOptions: vi.fn()
	} as unknown as IChartApi;

	return { chart, series, priceScale };
}

function createMockCanvasTarget() {
	const drawCalls: { type: string; args: unknown[] }[] = [];
	const context = {
		canvas: { width: 800, height: 600 },
		save: vi.fn(() => drawCalls.push({ type: 'save', args: [] })),
		restore: vi.fn(() => drawCalls.push({ type: 'restore', args: [] })),
		fillRect: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'fillRect', args })),
		beginPath: vi.fn(() => drawCalls.push({ type: 'beginPath', args: [] })),
		moveTo: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'moveTo', args })),
		lineTo: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'lineTo', args })),
		stroke: vi.fn(() => drawCalls.push({ type: 'stroke', args: [] })),
		setLineDash: vi.fn((...args: unknown[]) => drawCalls.push({ type: 'setLineDash', args }))
	} as unknown as CanvasRenderingContext2D;

	const target = {
		useBitmapCoordinateSpace: (cb: (scope: unknown) => void) => {
			cb({
				context,
				horizontalPixelRatio: 1,
				verticalPixelRatio: 1
			});
		}
	};

	return { target, drawCalls, context };
}

describe('ValuationBandPrimitive', () => {
	it('attaches to chart and series and renders horizontal band when visible', () => {
		const primitive = new ValuationBandPrimitive(50, 100, true);
		const { chart, series } = createMockChartAndSeries();
		const requestUpdate = vi.fn();

		primitive.attached({
			chart,
			series,
			requestUpdate
		} as unknown as SeriesAttachedParameter<Time, SeriesType>);

		expect(requestUpdate).toHaveBeenCalled();

		const paneViews = primitive.paneViews();
		expect(paneViews).toHaveLength(1);
		expect(paneViews[0].zOrder()).toBe('bottom');

		const renderer = paneViews[0].renderer();
		expect(renderer).not.toBeNull();

		const { target, drawCalls, context } = createMockCanvasTarget();
		renderer?.draw(target as unknown as CanvasTarget);

		expect(drawCalls.some((c) => c.type === 'fillRect')).toBe(true);
		expect(context.save).toHaveBeenCalled();
		expect(context.restore).toHaveBeenCalled();
	});

	it('does not draw when visible is false or bounds are null', () => {
		const primitive = new ValuationBandPrimitive(50, 100, false);
		const { chart, series } = createMockChartAndSeries();
		primitive.attached({
			chart,
			series,
			requestUpdate: vi.fn()
		} as unknown as SeriesAttachedParameter<Time, SeriesType>);

		const renderer = primitive.paneViews()[0].renderer();
		const { target, drawCalls } = createMockCanvasTarget();
		renderer?.draw(target as unknown as CanvasTarget);

		expect(drawCalls).toHaveLength(0);

		// With null range
		primitive.setRange(null, null, true);
		const renderer2 = primitive.paneViews()[0].renderer();
		renderer2?.draw(target as unknown as CanvasTarget);
		expect(drawCalls).toHaveLength(0);
	});

	it('detaches cleanly', () => {
		const primitive = new ValuationBandPrimitive(50, 100, true);
		const { chart, series } = createMockChartAndSeries();
		primitive.attached({
			chart,
			series,
			requestUpdate: vi.fn()
		} as unknown as SeriesAttachedParameter<Time, SeriesType>);

		primitive.detached();
		const { target, drawCalls } = createMockCanvasTarget();
		primitive
			.paneViews()[0]
			.renderer()
			?.draw(target as unknown as CanvasTarget);
		expect(drawCalls).toHaveLength(0);
	});
});
