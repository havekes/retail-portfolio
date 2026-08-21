import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';

if (typeof globalThis.Path2D === 'undefined') {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	(globalThis as any).Path2D = class Path2D {
		addPath() {}
	};
}

if (typeof globalThis.ResizeObserver === 'undefined') {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	(globalThis as any).ResizeObserver = class ResizeObserver {
		observe() {}
		unobserve() {}
		disconnect() {}
	};
}

const mockSubscribeVisibleLogicalRangeChange = vi.fn();
const mockGetVisibleLogicalRange = vi.fn();
const mockSetVisibleLogicalRange = vi.fn();
const mockFitContent = vi.fn();
const mockSetData = vi.fn();
const mockAttachPrimitive = vi.fn((primitive) => {
	primitive?.attached?.({
		chart: {
			chartElement: () => document.createElement('div'),
			timeScale: () => ({
				timeToCoordinate: () => 100,
				coordinateToTime: () => '2024-01-01',
				height: () => 30,
				width: () => 750
			}),
			priceScale: () => ({
				width: () => 50,
				applyOptions: vi.fn()
			})
		},
		series: {
			priceToCoordinate: () => 100,
			coordinateToPrice: () => 100
		},
		requestUpdate: vi.fn()
	});
});

let rangeCallbacks: ((range: { from: number; to: number } | null) => void)[] = [];

vi.mock('lightweight-charts', () => {
	return {
		createChart: vi.fn(() => ({
			chartElement: vi.fn(() => document.createElement('div')),
			timeScale: vi.fn(() => ({
				subscribeVisibleLogicalRangeChange: vi.fn((cb) => {
					rangeCallbacks.push(cb);
					mockSubscribeVisibleLogicalRangeChange(cb);
					return vi.fn();
				}),
				getVisibleLogicalRange: mockGetVisibleLogicalRange,
				setVisibleLogicalRange: mockSetVisibleLogicalRange,
				fitContent: mockFitContent,
				timeToCoordinate: vi.fn(() => 100),
				coordinateToTime: vi.fn(() => '2024-01-01'),
				height: vi.fn(() => 30),
				width: vi.fn(() => 750)
			})),
			addSeries: vi.fn(() => ({
				setData: mockSetData,
				priceScale: vi.fn(() => ({
					applyOptions: vi.fn(),
					width: vi.fn(() => 50)
				})),
				attachPrimitive: mockAttachPrimitive,
				createPriceLine: vi.fn(),
				removePriceLine: vi.fn(),
				priceToCoordinate: vi.fn(() => 100),
				coordinateToPrice: vi.fn(() => 100)
			})),
			applyOptions: vi.fn(),
			priceScale: vi.fn(() => ({
				applyOptions: vi.fn(),
				width: vi.fn(() => 50)
			})),
			removeSeries: vi.fn(),
			remove: vi.fn()
		})),
		CandlestickSeries: 'CandlestickSeries',
		LineSeries: 'LineSeries',
		HistogramSeries: 'HistogramSeries'
	};
});

import type { Component } from 'svelte';
import type { Candle } from '$lib/utils/finance/candle';
import type { SecurityElliottWaves } from '$lib/utils/finance/elliott-wave';
import { render } from '@testing-library/svelte';
import { createChart } from 'lightweight-charts';
import { ElliottWavesPrimitive } from './plugins/elliott-wave/elliott-wave';

describe('SecurityChart - Infinite Scroll & Logical Range', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let SecurityChart: Component<any>;

	const initialCandles: Candle[] = [
		{ time: '2024-01-10', open: 10, high: 12, low: 9, close: 11 },
		{ time: '2024-01-11', open: 11, high: 13, low: 10, close: 12 }
	];

	beforeAll(async () => {
		const mod = await import('./security-chart.svelte');
		SecurityChart = mod.default;
	});

	beforeEach(() => {
		vi.clearAllMocks();
		rangeCallbacks = [];
		mockGetVisibleLogicalRange.mockReturnValue({ from: 0, to: 1 });
	});

	it('invokes onLoadMoreData when visible logical range approaches left edge (from <= 10)', async () => {
		const onLoadMoreData = vi.fn();
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				hasMoreData: true,
				onLoadMoreData
			}
		});

		expect(rangeCallbacks.length).toBeGreaterThan(0);

		// Trigger main chart logical range change near left edge (from = 5)
		rangeCallbacks[0]({ from: 5, to: 50 });

		expect(onLoadMoreData).toHaveBeenCalledTimes(1);
	});

	it('does not trigger duplicate onLoadMoreData calls while loading or when hasMoreData is false', async () => {
		const onLoadMoreData = vi.fn();
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				hasMoreData: true,
				onLoadMoreData
			}
		});

		// First trigger sets isLoadingMore = true
		rangeCallbacks[0]({ from: 5, to: 50 });
		expect(onLoadMoreData).toHaveBeenCalledTimes(1);

		// Rapid second scroll while still loading
		rangeCallbacks[0]({ from: 2, to: 40 });
		expect(onLoadMoreData).toHaveBeenCalledTimes(1);
	});

	it('does not invoke onLoadMoreData when hasMoreData is false', async () => {
		const onLoadMoreData = vi.fn();
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				hasMoreData: false,
				onLoadMoreData
			}
		});

		rangeCallbacks[0]({ from: 5, to: 50 });
		expect(onLoadMoreData).not.toHaveBeenCalled();
	});

	it('updates visible logical range with correct offset when candles are prepended', async () => {
		const onLoadMoreData = vi.fn();
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				hasMoreData: true,
				onLoadMoreData
			}
		});

		// User scrolled near left edge
		rangeCallbacks[0]({ from: 5, to: 25 });
		mockGetVisibleLogicalRange.mockReturnValue({ from: 5, to: 25 });

		// Prepend 2 older candles
		const prependedCandles: Candle[] = [
			{ time: '2024-01-08', open: 8, high: 10, low: 7, close: 9 },
			{ time: '2024-01-09', open: 9, high: 11, low: 8, close: 10 },
			...initialCandles
		];

		await rerender({
			candles: prependedCandles,
			hasMoreData: true,
			onLoadMoreData
		});

		// offset by 2 prepended candles: from 5 + 2 = 7, to 25 + 2 = 27
		expect(mockSetVisibleLogicalRange).toHaveBeenCalledWith({
			from: 7,
			to: 27
		});
	});

	it('initializes charts with localization and tickMarkFormatter options', () => {
		render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		expect(createChart).toHaveBeenCalled();
		const calls = vi.mocked(createChart).mock.calls;
		expect(calls.length).toBeGreaterThanOrEqual(1);

		const mainChartOptions = calls[0][1];
		expect(mainChartOptions?.localization?.timeFormatter).toBeDefined();
		expect(typeof mainChartOptions?.localization?.timeFormatter).toBe('function');
		expect(mainChartOptions?.timeScale?.tickMarkFormatter).toBeDefined();
		expect(typeof mainChartOptions?.timeScale?.tickMarkFormatter).toBe('function');
	});
});

describe('SecurityChart - Elliott Wave Integration', () => {
	/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
	let SecurityChart: Component<any>;

	const initialCandles: Candle[] = [
		{ time: '2024-01-10', open: 10, high: 12, low: 9, close: 11 },
		{ time: '2024-01-11', open: 11, high: 13, low: 10, close: 12 }
	];

	beforeAll(async () => {
		const mod = await import('./security-chart.svelte');
		SecurityChart = mod.default;
	});

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('attaches ElliottWavesPrimitive to candlestick series on mount with initial props', () => {
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				activeDegree: 'primary',
				isDrawingWave: true
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive).toBeDefined();
		expect(elliottPrimitive.getActiveDegree()).toBe('primary');
		expect(elliottPrimitive.isDrawingMode()).toBe(true);
	});

	it('syncs activeDegree prop changes to ElliottWavesPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				activeDegree: 'cycle'
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive.getActiveDegree()).toBe('cycle');

		await rerender({
			candles: initialCandles,
			activeDegree: 'primary'
		});

		expect(elliottPrimitive.getActiveDegree()).toBe('primary');
	});

	it('syncs isDrawingWave prop changes to ElliottWavesPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				isDrawingWave: false
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive.isDrawingMode()).toBe(false);

		await rerender({
			candles: initialCandles,
			isDrawingWave: true
		});

		expect(elliottPrimitive.isDrawingMode()).toBe(true);
	});

	it('syncs elliottWaves prop changes to ElliottWavesPrimitive', async () => {
		const sampleWaves: SecurityElliottWaves = {
			cycle: {
				points: [{ wave: 1, time: '2024-01-10', price: 10 }]
			},
			primary: null
		};

		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				elliottWaves: sampleWaves
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive.getWaveCount('cycle')).toEqual(sampleWaves.cycle);

		const updatedWaves: SecurityElliottWaves = {
			cycle: sampleWaves.cycle,
			primary: {
				points: [{ wave: 1, time: '2024-01-11', price: 12 }]
			}
		};

		await rerender({
			candles: initialCandles,
			elliottWaves: updatedWaves
		});

		expect(elliottPrimitive.getWaveCount('primary')).toEqual(updatedWaves.primary);
	});

	it('forwards primitive events to delegate callbacks', () => {
		const onWaveChange = vi.fn();
		const onDrawingModeChange = vi.fn();
		const onDegreeChange = vi.fn();

		render(SecurityChart, {
			props: {
				candles: initialCandles,
				onWaveChange,
				onDrawingModeChange,
				onDegreeChange
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		// Trigger wave points change via primitive API (first point is wave 0)
		elliottPrimitive.addPoint({ time: '2024-01-10', price: 15 }, 'cycle');
		expect(onWaveChange).toHaveBeenCalledWith(
			'cycle',
			expect.objectContaining({
				points: expect.arrayContaining([expect.objectContaining({ wave: 0, price: 15 })])
			})
		);

		// Trigger drawing mode change
		elliottPrimitive.setDrawingMode(true);
		expect(onDrawingModeChange).toHaveBeenCalledWith(true);

		// Trigger degree change
		elliottPrimitive.setActiveDegree('primary');
		expect(onDegreeChange).toHaveBeenCalledWith('primary');
	});

	it('preserves visible logical range and avoids resetting candles when elliottWaves prop updates', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				elliottWaves: null
			}
		});

		// Initial setData called once for candles
		const initialSetDataCalls = mockSetData.mock.calls.length;

		// Update elliottWaves prop (e.g. user draws or clears wave)
		await rerender({
			candles: initialCandles,
			elliottWaves: {
				cycle: {
					points: [
						{ wave: 0, time: '2024-01-10', price: 10 },
						{ wave: 1, time: '2024-01-11', price: 12 }
					]
				}
			}
		});

		// setData should NOT have been re-called because candles array reference didn't change
		expect(mockSetData.mock.calls.length).toBe(initialSetDataCalls);
	});

	it('destroys ElliottWavesPrimitive when component is unmounted', () => {
		const { unmount } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		const destroySpy = vi.spyOn(elliottPrimitive, 'destroy');
		unmount();
		expect(destroySpy).toHaveBeenCalled();
	});
});
