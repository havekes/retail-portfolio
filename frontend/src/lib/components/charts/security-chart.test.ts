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
import { tick } from 'svelte';
import type { Candle } from '$lib/utils/finance/candle';
import type { SecurityElliottWaves, WaveDegree } from '$lib/utils/finance/elliott-wave';
import type { SecurityFibonacciTools, FibToolType } from '$lib/utils/finance/fibonacci';
import type { IndicatorData } from './security-chart.svelte';
import { render } from '@testing-library/svelte';
import { createChart } from 'lightweight-charts';
import { ElliottWavesPrimitive } from './plugins/elliott-wave/elliott-wave';
import { FibonacciPrimitive } from './plugins/fibonacci/fibonacci-primitive';

interface SecurityChartInstance {
	addIndicator: (indicator: IndicatorData) => void;
	removeIndicator: (type: string) => void;
	updateIndicatorData: (indicator: IndicatorData) => void;
	updateData: (candles: Candle[]) => void;
	getSelectedWaveDegree: () => WaveDegree | null;
	setSelectedWaveDegree: (degree: WaveDegree | null) => void;
	getSelectedFibTool: () => FibToolType | null;
	setSelectedFibTool: (tool: FibToolType | null) => void;
}

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

	it('initializes ElliottWavesPrimitive with snapToWicks prop', () => {
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				snapToWicks: true
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive).toBeDefined();
		expect(elliottPrimitive.getSnapToWicks()).toBe(true);
	});

	it('syncs snapToWicks prop changes to ElliottWavesPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				snapToWicks: false
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive.getSnapToWicks()).toBe(false);

		await rerender({
			candles: initialCandles,
			snapToWicks: true
		});

		expect(elliottPrimitive.getSnapToWicks()).toBe(true);
	});

	it('initializes ElliottWavesPrimitive with selectedWaveDegree prop', () => {
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				selectedWaveDegree: 'cycle'
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive).toBeDefined();
		expect(elliottPrimitive.getSelectedDegree()).toBe('cycle');
	});

	it('syncs selectedWaveDegree prop changes to ElliottWavesPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				selectedWaveDegree: null
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		expect(elliottPrimitive.getSelectedDegree()).toBeNull();

		await rerender({
			candles: initialCandles,
			selectedWaveDegree: 'primary'
		});

		expect(elliottPrimitive.getSelectedDegree()).toBe('primary');
	});

	it('forwards selection changes to onWaveSelect callback', () => {
		const onWaveSelect = vi.fn();

		render(SecurityChart, {
			props: {
				candles: initialCandles,
				onWaveSelect
			}
		});

		const elliottPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof ElliottWavesPrimitive
		)?.[0] as ElliottWavesPrimitive;

		elliottPrimitive.setSelectedDegree('cycle');
		expect(onWaveSelect).toHaveBeenCalledWith('cycle');

		elliottPrimitive.setSelectedDegree(null);
		expect(onWaveSelect).toHaveBeenCalledWith(null);
	});

	it('supports getSelectedWaveDegree and setSelectedWaveDegree component methods', () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		expect(component.getSelectedWaveDegree()).toBeNull();

		component.setSelectedWaveDegree('primary');
		expect(component.getSelectedWaveDegree()).toBe('primary');

		component.setSelectedWaveDegree(null);
		expect(component.getSelectedWaveDegree()).toBeNull();
	});
});

describe('SecurityChart - Fibonacci Integration', () => {
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

	it('attaches FibonacciPrimitive to candlestick series on mount with initial props', () => {
		const initialTools: SecurityFibonacciTools = {
			retracement: {
				p1: { time: '2024-01-10', price: 10 },
				p2: { time: '2024-01-11', price: 20 },
				visible: true
			},
			extension: null
		};

		render(SecurityChart, {
			props: {
				candles: initialCandles,
				activeFibTool: 'extension',
				isDrawingFib: true,
				fibonacciTools: initialTools
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		expect(fibPrimitive).toBeDefined();
		expect(fibPrimitive.getActiveTool()).toBe('extension');
		expect(fibPrimitive.isDrawingMode()).toBe(true);
		expect(fibPrimitive.getRetracement()).toEqual(initialTools.retracement);
	});

	it('syncs activeFibTool prop changes to FibonacciPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				activeFibTool: 'retracement'
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		expect(fibPrimitive.getActiveTool()).toBe('retracement');

		await rerender({
			candles: initialCandles,
			activeFibTool: 'extension'
		});

		expect(fibPrimitive.getActiveTool()).toBe('extension');
	});

	it('syncs isDrawingFib prop changes to FibonacciPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				isDrawingFib: false
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		expect(fibPrimitive.isDrawingMode()).toBe(false);

		await rerender({
			candles: initialCandles,
			isDrawingFib: true
		});

		expect(fibPrimitive.isDrawingMode()).toBe(true);
	});

	it('syncs fibonacciTools prop changes to FibonacciPrimitive', async () => {
		const sampleTools: SecurityFibonacciTools = {
			retracement: {
				p1: { time: '2024-01-10', price: 10 },
				p2: { time: '2024-01-11', price: 15 }
			},
			extension: null
		};

		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				fibonacciTools: sampleTools
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		expect(fibPrimitive.getRetracement()).toEqual(sampleTools.retracement);

		const updatedTools: SecurityFibonacciTools = {
			retracement: sampleTools.retracement,
			extension: {
				p1: { time: '2024-01-10', price: 10 },
				p2: { time: '2024-01-11', price: 15 },
				p3: { time: '2024-01-12', price: 12 }
			}
		};

		await rerender({
			candles: initialCandles,
			fibonacciTools: updatedTools
		});

		expect(fibPrimitive.getExtension()).toEqual(updatedTools.extension);
	});

	it('forwards primitive delegate events to onFibChange, onFibDrawingModeChange, and onFibToolChange', () => {
		const onFibChange = vi.fn();
		const onFibDrawingModeChange = vi.fn();
		const onFibToolChange = vi.fn();

		render(SecurityChart, {
			props: {
				candles: initialCandles,
				onFibChange,
				onFibDrawingModeChange,
				onFibToolChange
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		// Trigger drawings change via adding 2 retracement points
		fibPrimitive.setDrawingMode(true);
		fibPrimitive.setActiveTool('retracement');
		fibPrimitive.addPoint({ time: '2024-01-10', price: 10 }, 'retracement');
		fibPrimitive.addPoint({ time: '2024-01-11', price: 20 }, 'retracement');

		expect(onFibChange).toHaveBeenCalledWith(
			expect.objectContaining({
				retracement: expect.objectContaining({
					p1: { time: '2024-01-10', price: 10 },
					p2: { time: '2024-01-11', price: 20 }
				})
			})
		);

		// Trigger drawing mode change
		fibPrimitive.setDrawingMode(true);
		expect(onFibDrawingModeChange).toHaveBeenCalledWith(true);

		// Trigger tool change
		fibPrimitive.setActiveTool('extension');
		expect(onFibToolChange).toHaveBeenCalledWith('extension');
	});

	it('preserves visible logical range and avoids resetting candles when fibonacciTools prop updates', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				fibonacciTools: null
			}
		});

		const initialSetDataCalls = mockSetData.mock.calls.length;

		await rerender({
			candles: initialCandles,
			fibonacciTools: {
				retracement: {
					p1: { time: '2024-01-10', price: 10 },
					p2: { time: '2024-01-11', price: 20 }
				},
				extension: null
			}
		});

		expect(mockSetData.mock.calls.length).toBe(initialSetDataCalls);
	});

	it('forwards candle updates to FibonacciPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		const setCandlesSpy = vi.spyOn(fibPrimitive, 'setCandles');

		const newCandles: Candle[] = [
			...initialCandles,
			{ time: '2024-01-12', open: 12, high: 14, low: 11, close: 13 }
		];

		await rerender({
			candles: newCandles
		});

		expect(setCandlesSpy).toHaveBeenCalledWith(newCandles);
	});

	it('destroys FibonacciPrimitive when component is unmounted', () => {
		const { unmount } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		const destroySpy = vi.spyOn(fibPrimitive, 'destroy');
		unmount();
		expect(destroySpy).toHaveBeenCalled();
	});

	it('initializes FibonacciPrimitive with selectedFibTool prop', () => {
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				selectedFibTool: 'retracement'
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		expect(fibPrimitive.getSelectedTool()).toBe('retracement');
	});

	it('syncs selectedFibTool prop changes to FibonacciPrimitive', async () => {
		const { rerender } = render(SecurityChart, {
			props: {
				candles: initialCandles,
				selectedFibTool: null
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		expect(fibPrimitive.getSelectedTool()).toBeNull();

		await rerender({
			candles: initialCandles,
			selectedFibTool: 'extension'
		});

		expect(fibPrimitive.getSelectedTool()).toBe('extension');
	});

	it('forwards primitive selection changes to onFibSelect callback', () => {
		const onFibSelect = vi.fn();
		render(SecurityChart, {
			props: {
				candles: initialCandles,
				onFibSelect
			}
		});

		const fibPrimitive = mockAttachPrimitive.mock.calls.find(
			(c) => c[0] instanceof FibonacciPrimitive
		)?.[0] as FibonacciPrimitive;

		fibPrimitive.setSelectedTool('retracement');
		expect(onFibSelect).toHaveBeenCalledWith('retracement');

		fibPrimitive.setSelectedTool(null);
		expect(onFibSelect).toHaveBeenCalledWith(null);
	});

	it('supports getSelectedFibTool and setSelectedFibTool component methods', () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		expect(component.getSelectedFibTool()).toBeNull();

		component.setSelectedFibTool('extension');
		expect(component.getSelectedFibTool()).toBe('extension');

		component.setSelectedFibTool(null);
		expect(component.getSelectedFibTool()).toBeNull();
	});
});

describe('SecurityChart - Bottom Pane & Oscillator Sizing', () => {
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
		mockGetVisibleLogicalRange.mockReturnValue({ from: 10, to: 50 });
	});

	it('renders root and chart containers with min-h-0 and overflow-hidden classes', () => {
		const { container } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		const rootEl = container.firstElementChild as HTMLElement;
		expect(rootEl.className).toContain('min-h-0');
		expect(rootEl.className).toContain('flex-1');
		expect(rootEl.className).toContain('overflow-hidden');

		const mainContainer = rootEl.querySelector('#main-chart') as HTMLElement;
		expect(mainContainer).toBeDefined();
		expect(mainContainer.className).toContain('min-h-0');
		expect(mainContainer.className).toContain('overflow-hidden');
		expect(mainContainer.className).not.toContain('transition-all');
		expect(mainContainer.style.height).toBe('100%');

		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;
		expect(bottomContainer).toBeDefined();
		expect(bottomContainer.className).toContain('min-h-0');
		expect(bottomContainer.className).toContain('overflow-hidden');
		expect(bottomContainer.className).not.toContain('transition-all');
		expect(bottomContainer.style.height).toBe('0px');
		expect(bottomContainer.style.display).toBe('none');
	});

	it('adjusts main and bottom container heights when RSI indicator is added', async () => {
		const { container, component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;

		component.addIndicator({
			type: 'rsi',
			label: 'RSI (14)',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 55 }]
		});
		await tick();

		expect(mainContainer.style.height).toBe('70%');
		expect(bottomContainer.style.height).toBe('30%');
		expect(bottomContainer.style.display).toBe('block');
		expect(bottomContainer.className).toContain('border-t');
		expect(bottomContainer.className).toContain('border-border');
	});

	it('adjusts main and bottom container heights when MACD indicator is added', async () => {
		const { container, component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;

		component.addIndicator({
			type: 'macd',
			label: 'MACD (12, 26, 9)',
			color: '#2962FF',
			data: [{ time: '2024-01-10', histogram: 0.5, macd: 1.2, signal: 0.7 }]
		});
		await tick();

		expect(mainContainer.style.height).toBe('70%');
		expect(bottomContainer.style.height).toBe('30%');
		expect(bottomContainer.style.display).toBe('block');
	});

	it('adjusts main and bottom container heights when OBV indicator is added', async () => {
		const { container, component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;

		component.addIndicator({
			type: 'obv',
			label: 'OBV',
			color: '#26a69a',
			data: [{ time: '2024-01-10', value: 1000 }]
		});
		await tick();

		expect(mainContainer.style.height).toBe('70%');
		expect(bottomContainer.style.height).toBe('30%');
		expect(bottomContainer.style.display).toBe('block');
	});

	it('restores 100% height to main container and hides bottom pane when bottom indicators are removed', async () => {
		const { container, component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;

		// Add multiple bottom indicators
		component.addIndicator({
			type: 'rsi',
			label: 'RSI (14)',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 55 }]
		});
		component.addIndicator({
			type: 'macd',
			label: 'MACD (12, 26, 9)',
			color: '#2962FF',
			data: [{ time: '2024-01-10', histogram: 0.5, macd: 1.2, signal: 0.7 }]
		});
		await tick();

		expect(mainContainer.style.height).toBe('70%');
		expect(bottomContainer.style.height).toBe('30%');

		// Remove RSI, MACD still active -> bottom pane stays active
		component.removeIndicator('rsi');
		await tick();
		expect(mainContainer.style.height).toBe('70%');
		expect(bottomContainer.style.height).toBe('30%');

		// Remove MACD -> all bottom indicators gone -> restores 100% height
		component.removeIndicator('macd');
		await tick();
		expect(mainContainer.style.height).toBe('100%');
		expect(bottomContainer.style.height).toBe('0px');
		expect(bottomContainer.style.display).toBe('none');
	});

	it('invokes applyOptions on chart instances when bottom pane is toggled and dimensions exist', async () => {
		const { container, component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;

		Object.defineProperty(mainContainer, 'clientWidth', { value: 800, configurable: true });
		Object.defineProperty(mainContainer, 'clientHeight', { value: 420, configurable: true });
		Object.defineProperty(bottomContainer, 'clientWidth', { value: 800, configurable: true });
		Object.defineProperty(bottomContainer, 'clientHeight', { value: 180, configurable: true });

		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];
		const bottomChart = createdCharts[1];

		// Clear initial createChart / mount applyOptions calls
		vi.mocked(mainChart.applyOptions).mockClear();
		vi.mocked(bottomChart.applyOptions).mockClear();

		// Activate bottom pane
		component.addIndicator({
			type: 'rsi',
			label: 'RSI',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 50 }]
		});
		await tick();

		expect(mainChart.applyOptions).toHaveBeenCalledWith({
			width: 800,
			height: 420
		});
		expect(bottomChart.applyOptions).toHaveBeenCalledWith({
			width: 800,
			height: 180
		});

		// Remove indicator and verify main chart is resized back
		vi.mocked(mainChart.applyOptions).mockClear();
		Object.defineProperty(mainContainer, 'clientHeight', { value: 600, configurable: true });

		component.removeIndicator('rsi');
		await tick();
		expect(mainChart.applyOptions).toHaveBeenCalledWith({
			width: 800,
			height: 600
		});
	});

	it('synchronizes visible logical range between main chart and bottom chart', async () => {
		const { container, component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		const bottomContainer = mainContainer.nextElementSibling as HTMLElement;

		Object.defineProperty(mainContainer, 'clientWidth', { value: 800, configurable: true });
		Object.defineProperty(mainContainer, 'clientHeight', { value: 420, configurable: true });
		Object.defineProperty(bottomContainer, 'clientWidth', { value: 800, configurable: true });
		Object.defineProperty(bottomContainer, 'clientHeight', { value: 180, configurable: true });

		mockGetVisibleLogicalRange.mockReturnValue({ from: 15, to: 45 });

		// Activate bottom pane
		component.addIndicator({
			type: 'rsi',
			label: 'RSI',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 50 }]
		});
		await tick();

		// Bottom chart should sync initial logical range from main chart
		expect(mockSetVisibleLogicalRange).toHaveBeenCalledWith({ from: 15, to: 45 });

		// Main chart time scale subscription triggers bottom chart sync
		mockSetVisibleLogicalRange.mockClear();
		// callback 0 is main chart listener, callback 1 is bottom chart listener
		rangeCallbacks[0]({ from: 20, to: 60 });
		expect(mockSetVisibleLogicalRange).toHaveBeenCalledWith({ from: 20, to: 60 });

		// Bottom chart time scale subscription triggers main chart sync
		mockSetVisibleLogicalRange.mockClear();
		rangeCallbacks[1]({ from: 25, to: 65 });
		expect(mockSetVisibleLogicalRange).toHaveBeenCalledWith({ from: 25, to: 65 });
	});
});
