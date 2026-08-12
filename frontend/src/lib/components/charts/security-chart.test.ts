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

let rangeCallbacks: ((range: { from: number; to: number } | null) => void)[] = [];

vi.mock('lightweight-charts', () => {
	return {
		createChart: vi.fn(() => ({
			timeScale: vi.fn(() => ({
				subscribeVisibleLogicalRangeChange: vi.fn((cb) => {
					rangeCallbacks.push(cb);
					mockSubscribeVisibleLogicalRangeChange(cb);
					return vi.fn();
				}),
				getVisibleLogicalRange: mockGetVisibleLogicalRange,
				setVisibleLogicalRange: mockSetVisibleLogicalRange,
				fitContent: mockFitContent
			})),
			addSeries: vi.fn(() => ({
				setData: mockSetData,
				priceScale: vi.fn(() => ({
					applyOptions: vi.fn()
				})),
				attachPrimitive: vi.fn(),
				createPriceLine: vi.fn(),
				removePriceLine: vi.fn()
			})),
			applyOptions: vi.fn(),
			priceScale: vi.fn(() => ({
				applyOptions: vi.fn()
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
import { render } from '@testing-library/svelte';

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
});
