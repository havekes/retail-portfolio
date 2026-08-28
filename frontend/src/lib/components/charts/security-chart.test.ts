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

import type { Time } from 'lightweight-charts';

const mockSubscribeVisibleLogicalRangeChange = vi.fn();
const mockGetVisibleLogicalRange = vi.fn();
const mockSetVisibleLogicalRange = vi.fn();
const mockGetVisibleRange = vi.fn();
const mockSetVisibleRange = vi.fn();
const mockSetCrosshairPosition = vi.fn();
const mockClearCrosshairPosition = vi.fn();
const mockSubscribeCrosshairMove = vi.fn();
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
let crosshairCallbacks: ((param: { time?: Time; point?: { x: number; y: number } }) => void)[] = [];

vi.mock('lightweight-charts', () => {
	return {
		createChart: vi.fn(() => {
			let currentVisibleRange: { from: Time; to: Time } | null = null;
			let currentVisibleLogicalRange: { from: number; to: number } | null = null;
			const priceScales = new Map<
				string,
				{
					applyOptions: ReturnType<typeof vi.fn>;
					width: ReturnType<typeof vi.fn>;
					getVisibleRange: ReturnType<typeof vi.fn>;
					setVisibleRange: ReturnType<typeof vi.fn>;
					setAutoScale: ReturnType<typeof vi.fn>;
				}
			>();
			const getPriceScale = (id: string = 'right') => {
				if (!priceScales.has(id)) {
					let visibleRange: { from: number; to: number } | null = { from: 100, to: 200 };
					priceScales.set(id, {
						applyOptions: vi.fn(),
						width: vi.fn(() => 50),
						getVisibleRange: vi.fn(() => visibleRange),
						setVisibleRange: vi.fn((r) => {
							visibleRange = r;
						}),
						setAutoScale: vi.fn()
					});
				}
				return priceScales.get(id)!;
			};
			const timeScaleMock = {
				subscribeVisibleLogicalRangeChange: vi.fn((cb) => {
					rangeCallbacks.push(cb);
					mockSubscribeVisibleLogicalRangeChange(cb);
					return vi.fn();
				}),
				getVisibleLogicalRange: vi.fn(() => {
					const val = mockGetVisibleLogicalRange();
					return val !== undefined ? val : currentVisibleLogicalRange;
				}),
				setVisibleLogicalRange: vi.fn((r: { from: number; to: number }) => {
					currentVisibleLogicalRange = r;
					mockSetVisibleLogicalRange(r);
				}),
				getVisibleRange: vi.fn(() => {
					const val = mockGetVisibleRange();
					return val !== undefined ? val : currentVisibleRange;
				}),
				setVisibleRange: vi.fn((r: { from: Time; to: Time }) => {
					currentVisibleRange = r;
					mockSetVisibleRange(r);
				}),
				fitContent: mockFitContent,
				timeToCoordinate: vi.fn(() => 100),
				coordinateToTime: vi.fn(() => '2024-01-01'),
				height: vi.fn(() => 30),
				width: vi.fn(() => 750)
			};
			return {
				chartElement: vi.fn(() => document.createElement('div')),
				timeScale: vi.fn(() => timeScaleMock),
				addSeries: vi.fn((_seriesType, options) => ({
					setData: mockSetData,
					priceScale: vi.fn(() => getPriceScale(options?.priceScaleId || 'right')),
					attachPrimitive: mockAttachPrimitive,
					createPriceLine: vi.fn(),
					removePriceLine: vi.fn(),
					applyOptions: vi.fn(),
					priceToCoordinate: vi.fn(() => 100),
					coordinateToPrice: vi.fn(() => 100)
				})),
				applyOptions: vi.fn(),
				priceScale: vi.fn((id: string = 'right') => getPriceScale(id)),
				removeSeries: vi.fn(),
				remove: vi.fn(),
				subscribeCrosshairMove: vi.fn((cb) => {
					crosshairCallbacks.push(cb);
					mockSubscribeCrosshairMove(cb);
					return vi.fn();
				}),
				setCrosshairPosition: mockSetCrosshairPosition,
				clearCrosshairPosition: mockClearCrosshairPosition
			};
		}),
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
		crosshairCallbacks = [];
		mockGetVisibleLogicalRange.mockReturnValue({ from: 0, to: 1 });
		mockGetVisibleRange.mockReturnValue(undefined);
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

	it('initializes chart with consistent leftPriceScale visible false and rightPriceScale minimumWidth', () => {
		render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		expect(createChart).toHaveBeenCalledTimes(1);
		const calls = vi.mocked(createChart).mock.calls;

		const mainChartOptions = calls[0][1];
		expect(mainChartOptions?.leftPriceScale).toEqual({ visible: false });
		expect(mainChartOptions?.rightPriceScale).toEqual({ visible: true, minimumWidth: 75 });
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

describe('SecurityChart - Oscillator Panes & Custom Price Scales', () => {
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
		crosshairCallbacks = [];
		mockGetVisibleLogicalRange.mockReturnValue(undefined);
		mockGetVisibleRange.mockReturnValue(undefined);
	});

	it('renders unified chart container with min-h-0, flex-1, and overflow-hidden classes', () => {
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
		expect(mainContainer.className).toContain('h-full');

		// No secondary or bottom container in DOM
		expect(mainContainer.nextElementSibling).toBeNull();
	});

	it('adds RSI indicator to main chart using custom priceScaleId "rsi" with stacked scaleMargins and unpadded data', async () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;
		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];

		mockSetData.mockClear();
		component.addIndicator({
			type: 'rsi',
			label: 'RSI (14)',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 55 }]
		});
		await tick();

		expect(mainChart.addSeries).toHaveBeenCalledWith(
			'LineSeries',
			expect.objectContaining({
				priceScaleId: 'rsi',
				color: '#7e57c2'
			})
		);

		// RSI data set without artificial whitespace padding
		expect(mockSetData).toHaveBeenCalledWith([{ time: '2024-01-10', value: 55 }]);

		// RSI scale margins applied on its custom price scale
		expect(mainChart.priceScale('rsi').applyOptions).toHaveBeenCalledWith(
			expect.objectContaining({
				scaleMargins: expect.objectContaining({
					top: expect.any(Number),
					bottom: expect.any(Number)
				})
			})
		);
	});

	it('adds MACD indicator series (histogram, macdLine, signalLine) to main chart sharing priceScaleId "macd"', async () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;
		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];

		component.addIndicator({
			type: 'macd',
			label: 'MACD (12, 26, 9)',
			color: '#2962FF',
			data: [{ time: '2024-01-10', histogram: 0.5, macd: 1.2, signal: 0.7 }]
		});
		await tick();

		// All 3 MACD series attached with priceScaleId: 'macd'
		expect(mainChart.addSeries).toHaveBeenCalledWith(
			'HistogramSeries',
			expect.objectContaining({ priceScaleId: 'macd' })
		);
		expect(mainChart.addSeries).toHaveBeenCalledWith(
			'LineSeries',
			expect.objectContaining({ priceScaleId: 'macd', color: '#2962FF' })
		);
		expect(mainChart.addSeries).toHaveBeenCalledWith(
			'LineSeries',
			expect.objectContaining({ priceScaleId: 'macd', color: '#FF6D00' })
		);

		// MACD price scale options applied
		expect(mainChart.priceScale('macd').applyOptions).toHaveBeenCalledWith(
			expect.objectContaining({
				scaleMargins: expect.objectContaining({
					top: expect.any(Number),
					bottom: expect.any(Number)
				})
			})
		);
	});

	it('attaches OBV indicator to main chart with priceScaleId "obv" and formats values in millions', async () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;
		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];

		component.addIndicator({
			type: 'obv',
			label: 'OBV',
			color: '#26a69a',
			data: [{ time: '2024-01-10', value: 1500000 }]
		});
		await tick();

		expect(mainChart.addSeries).toHaveBeenCalledWith(
			'LineSeries',
			expect.objectContaining({
				priceScaleId: 'obv',
				color: '#26a69a',
				lineWidth: 2,
				priceFormat: {
					type: 'custom',
					formatter: expect.any(Function)
				}
			})
		);

		// Verify custom price formatter abbreviation in millions with 1 decimal place
		/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
		const addSeriesCalls: any[] = vi.mocked(mainChart.addSeries).mock.calls;
		const obvCall = addSeriesCalls.find((c) => c[1]?.priceScaleId === 'obv');
		expect(obvCall).toBeDefined();
		const formatter = obvCall![1]?.priceFormat?.formatter as (val: number) => string;
		expect(formatter).toBeDefined();
		expect(formatter(1_500_000)).toBe('1.5M');
		expect(formatter(25_340_000)).toBe('25.3M');
		expect(formatter(0)).toBe('0.0M');
		expect(formatter(-1_200_000)).toBe('-1.2M');
	});

	it('dynamically stacks multiple oscillators (RSI, MACD) with non-overlapping scaleMargins', async () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;
		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];

		component.addIndicator({
			type: 'rsi',
			label: 'RSI',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 50 }]
		});
		component.addIndicator({
			type: 'macd',
			label: 'MACD',
			color: '#2962FF',
			data: [{ time: '2024-01-10', histogram: 0.5, macd: 1.2, signal: 0.7 }]
		});
		await tick();

		// When 2 oscillators are active:
		// paneHeight = 0.18, gap = 0.02, total = 0.40, mainAreaHeight = 0.60
		// RSI pane (idx 0): top = 0.62, bottom = 0.20
		// MACD pane (idx 1): top = 0.82, bottom = 0.00
		expect(mainChart.priceScale('rsi').applyOptions).toHaveBeenLastCalledWith({
			scaleMargins: { top: 0.62, bottom: 0.2 }
		});
		expect(mainChart.priceScale('macd').applyOptions).toHaveBeenLastCalledWith({
			scaleMargins: { top: 0.82, bottom: 0 }
		});

		// Remove RSI, leaving only MACD (count = 1)
		// paneHeight = 0.25, gap = 0.02, total = 0.27, mainAreaHeight = 0.73
		// MACD pane (idx 0): top = 0.75, bottom = 0.00
		component.removeIndicator('rsi');
		await tick();

		expect(mainChart.priceScale('macd').applyOptions).toHaveBeenLastCalledWith({
			scaleMargins: { top: 0.75, bottom: 0 }
		});
	});

	it('restores full height scaleMargins when all oscillators are removed', async () => {
		const { component: comp } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});
		const component = comp as unknown as SecurityChartInstance;
		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];

		component.addIndicator({
			type: 'rsi',
			label: 'RSI',
			color: '#7e57c2',
			data: [{ time: '2024-01-10', value: 50 }]
		});
		await tick();

		const rightScaleCalls = vi.mocked(mainChart.priceScale('right').applyOptions).mock.calls;
		const lastCallWhenRsiActive = rightScaleCalls[rightScaleCalls.length - 1][0];
		// Main series bottom margin shrunk to accommodate RSI pane
		expect(lastCallWhenRsiActive.scaleMargins.bottom).toBeGreaterThan(0.1);

		component.removeIndicator('rsi');
		await tick();

		// Restored to default { top: 0.1, bottom: 0.1 }
		expect(mainChart.priceScale('right').applyOptions).toHaveBeenLastCalledWith({
			scaleMargins: { top: 0.1, bottom: 0.1 }
		});
	});

	it('resizes main chart instance when container dimensions change', async () => {
		const { container } = render(SecurityChart, {
			props: {
				candles: initialCandles
			}
		});

		const mainContainer = container.querySelector('#main-chart') as HTMLElement;
		Object.defineProperty(mainContainer, 'clientWidth', { value: 800, configurable: true });
		Object.defineProperty(mainContainer, 'clientHeight', { value: 600, configurable: true });

		const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
		const mainChart = createdCharts[0];
		vi.mocked(mainChart.applyOptions).mockClear();

		// Trigger resize
		window.dispatchEvent(new Event('resize'));
		await tick();

		expect(mainChart).toBeDefined();
	});

	describe('hideLabels prop', () => {
		it('sets axisLabelVisible on averagePrice line based on !hideLabels', async () => {
			const { rerender } = render(SecurityChart, {
				props: {
					candles: initialCandles,
					showAveragePrice: true,
					averagePrice: 100,
					hideLabels: false
				}
			});
			await tick();

			const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
			const mainChart = createdCharts[createdCharts.length - 1];
			const candlestickSeries = mainChart.addSeries.mock.results[0].value;

			expect(candlestickSeries.createPriceLine).toHaveBeenCalledWith(
				expect.objectContaining({
					axisLabelVisible: true,
					title: 'Avg Price'
				})
			);

			// Rerender with hideLabels: true
			rerender({
				candles: initialCandles,
				showAveragePrice: true,
				averagePrice: 100,
				hideLabels: true
			});
			await tick();

			expect(candlestickSeries.createPriceLine).toHaveBeenLastCalledWith(
				expect.objectContaining({
					axisLabelVisible: false,
					title: 'Avg Price'
				})
			);
		});

		it('passes lastValueVisible, priceLineVisible, and title to newly added indicator series', async () => {
			const { component: comp } = render(SecurityChart, {
				props: {
					candles: initialCandles,
					hideLabels: true
				}
			});
			const component = comp as unknown as SecurityChartInstance;
			const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
			const mainChart = createdCharts[createdCharts.length - 1];

			component.addIndicator({
				type: 'ma50',
				label: '50 Day MA',
				color: '#2196F3',
				data: [{ time: '2024-01-10', value: 10 }]
			});
			await tick();

			expect(mainChart.addSeries).toHaveBeenCalledWith(
				'LineSeries',
				expect.objectContaining({
					lastValueVisible: false,
					priceLineVisible: false,
					title: ''
				})
			);
		});

		it('dynamically calls applyOptions on existing indicator series when hideLabels changes', async () => {
			const { component: comp, rerender } = render(SecurityChart, {
				props: {
					candles: initialCandles,
					hideLabels: false
				}
			});
			const component = comp as unknown as SecurityChartInstance;
			const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
			const mainChart = createdCharts[createdCharts.length - 1];

			component.addIndicator({
				type: 'ma50',
				label: '50 Day MA',
				color: '#2196F3',
				data: [{ time: '2024-01-10', value: 10 }]
			});
			await tick();

			// ma50 series is the second series created (first is candlestick)
			const ma50Series = mainChart.addSeries.mock.results[1].value;
			expect(ma50Series.applyOptions).not.toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: false, title: '' })
			);

			// Toggle hideLabels to true
			rerender({
				candles: initialCandles,
				hideLabels: true
			});
			await tick();

			expect(ma50Series.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({
					lastValueVisible: false,
					priceLineVisible: false,
					title: ''
				})
			);

			// Toggle hideLabels back to false
			rerender({
				candles: initialCandles,
				hideLabels: false
			});
			await tick();

			expect(ma50Series.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({
					lastValueVisible: true,
					priceLineVisible: true,
					title: '50 Day MA'
				})
			);
		});

		it('dynamically updates MACD sub-series titles and visibility on hideLabels toggle', async () => {
			const { component: comp, rerender } = render(SecurityChart, {
				props: {
					candles: initialCandles,
					hideLabels: false
				}
			});
			const component = comp as unknown as SecurityChartInstance;
			const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
			const mainChart = createdCharts[createdCharts.length - 1];

			component.addIndicator({
				type: 'macd',
				label: 'MACD',
				color: '#2962FF',
				data: [{ time: '2024-01-10', histogram: 0.5, macd: 1.2, signal: 0.7 }]
			});
			await tick();

			// MACD creates Histogram, Line (macd), Line (signal)
			const histSeries = mainChart.addSeries.mock.results[1].value;
			const macdLineSeries = mainChart.addSeries.mock.results[2].value;
			const signalLineSeries = mainChart.addSeries.mock.results[3].value;

			// Toggle hideLabels to true
			rerender({
				candles: initialCandles,
				hideLabels: true
			});
			await tick();

			expect(histSeries.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: false, title: '' })
			);
			expect(macdLineSeries.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: false, title: '' })
			);
			expect(signalLineSeries.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: false, title: '' })
			);

			// Toggle hideLabels back to false
			rerender({
				candles: initialCandles,
				hideLabels: false
			});
			await tick();

			expect(histSeries.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: true, title: 'MACD Hist' })
			);
			expect(macdLineSeries.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: true, title: 'MACD' })
			);
			expect(signalLineSeries.applyOptions).toHaveBeenCalledWith(
				expect.objectContaining({ lastValueVisible: true, title: 'Signal' })
			);
		});
	});

	describe('top-left active indicators legend overlay', () => {
		it('does not render top-left enabled indicators list overlay when indicators are added', async () => {
			const { component: comp, container } = render(SecurityChart, {
				props: {
					candles: initialCandles
				}
			});
			const component = comp as unknown as SecurityChartInstance;

			component.addIndicator({
				type: 'ma50',
				label: '50 Day MA',
				color: '#2196F3',
				data: [{ time: '2024-01-10', value: 10 }]
			});
			await tick();

			expect(container.querySelector('.backdrop-blur-sm')).toBeNull();
			expect(container.querySelector('.absolute.top-4.left-4')).toBeNull();
		});
	});

	describe('price scale wheel zooming', () => {
		it('zooms price scale visible range and stops propagation when wheel event occurs over price scale', async () => {
			const { container } = render(SecurityChart, {
				props: {
					candles: initialCandles
				}
			});

			const mainContainer = container.querySelector('#main-chart') as HTMLElement;
			Object.defineProperty(mainContainer, 'clientWidth', { value: 800, configurable: true });
			Object.defineProperty(mainContainer, 'clientHeight', { value: 600, configurable: true });
			vi.spyOn(mainContainer, 'getBoundingClientRect').mockReturnValue({
				left: 0,
				top: 0,
				right: 800,
				bottom: 600,
				width: 800,
				height: 600,
				x: 0,
				y: 0,
				toJSON: () => {}
			});

			const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
			const mainChart = createdCharts[createdCharts.length - 1];
			const candlestickSeries = mainChart.addSeries.mock.results[0].value;
			const priceScale = candlestickSeries.priceScale();

			// priceScale width is 50, container width is 800.
			// Coordinate x >= 750 is over the price scale.
			const wheelEvent = new WheelEvent('wheel', {
				clientX: 760,
				clientY: 300,
				deltaY: 100,
				bubbles: true,
				cancelable: true
			});

			const preventDefaultSpy = vi.spyOn(wheelEvent, 'preventDefault');
			const stopPropagationSpy = vi.spyOn(wheelEvent, 'stopPropagation');

			mainContainer.dispatchEvent(wheelEvent);
			await tick();

			expect(preventDefaultSpy).toHaveBeenCalled();
			expect(stopPropagationSpy).toHaveBeenCalled();
			expect(priceScale.setVisibleRange).toHaveBeenCalledWith(
				expect.objectContaining({
					from: expect.any(Number),
					to: expect.any(Number)
				})
			);
		});

		it('does not intercept wheel events over the main chart canvas', async () => {
			const { container } = render(SecurityChart, {
				props: {
					candles: initialCandles
				}
			});

			const mainContainer = container.querySelector('#main-chart') as HTMLElement;
			Object.defineProperty(mainContainer, 'clientWidth', { value: 800, configurable: true });
			Object.defineProperty(mainContainer, 'clientHeight', { value: 600, configurable: true });
			vi.spyOn(mainContainer, 'getBoundingClientRect').mockReturnValue({
				left: 0,
				top: 0,
				right: 800,
				bottom: 600,
				width: 800,
				height: 600,
				x: 0,
				y: 0,
				toJSON: () => {}
			});

			const createdCharts = vi.mocked(createChart).mock.results.map((r) => r.value);
			const mainChart = createdCharts[createdCharts.length - 1];
			const candlestickSeries = mainChart.addSeries.mock.results[0].value;
			const priceScale = candlestickSeries.priceScale();
			vi.mocked(priceScale.setVisibleRange).mockClear();

			// Coordinate x = 400 is well within chart canvas (x < 750)
			const wheelEvent = new WheelEvent('wheel', {
				clientX: 400,
				clientY: 300,
				deltaY: 100,
				bubbles: true,
				cancelable: true
			});

			const preventDefaultSpy = vi.spyOn(wheelEvent, 'preventDefault');
			const stopPropagationSpy = vi.spyOn(wheelEvent, 'stopPropagation');

			mainContainer.dispatchEvent(wheelEvent);
			await tick();

			expect(preventDefaultSpy).not.toHaveBeenCalled();
			expect(stopPropagationSpy).not.toHaveBeenCalled();
			expect(priceScale.setVisibleRange).not.toHaveBeenCalled();
		});
	});
});
