<script lang="ts">
	import { CandlestickSeries, createChart, LineSeries, HistogramSeries } from 'lightweight-charts';
	import type { Time, IChartApi, ISeriesApi, IPriceLine, SeriesType } from 'lightweight-charts';
	import { onMount } from 'svelte';
	import type { Candle } from '@/utils/finance/candle';
	import { formatLocalTime, formatLocalTickMark } from '@/utils/date';
	import { BandsIndicator } from './plugins/bands-indicator';
	import { AVG_PRICE_LINE_COLOR } from './colors';
	import { UserPriceAlerts } from './plugins/user-price-alerts/user-price-alerts';
	import type { UserAlertInfo } from './plugins/user-price-alerts/state';
	import type { PriceAlert } from '$lib/api/alertsService';
	import { ElliottWavesPrimitive } from './plugins/elliott-wave/elliott-wave';
	import type {
		DegreeWaveCount,
		SecurityElliottWaves,
		WaveDegree,
		WaveType
	} from '$lib/utils/finance/elliott-wave';
	import { areWaveCountsEqual } from '$lib/utils/finance/elliott-wave';
	import { FibonacciPrimitive } from './plugins/fibonacci/fibonacci-primitive';
	import type { FibToolType, SecurityFibonacciTools } from '$lib/utils/finance/fibonacci';
	import { areFibonacciToolsEqual } from '$lib/utils/finance/fibonacci';

	interface MacdDataItem {
		time: Time;
		histogram: number;
		macd: number;
		signal: number;
	}

	interface BbDataItem {
		time: Time;
		upper: number;
		middle: number;
		lower: number;
	}

	export interface IndicatorData {
		type: string;
		label: string;
		color: string;
		data: ({ time: Time; value: number } | MacdDataItem | BbDataItem)[];
	}

	let containerRef = $state<HTMLDivElement | null>(null);
	let bottomContainerRef = $state<HTMLDivElement | null>(null);
	let chartInstance = $state<IChartApi | null>(null);
	let bottomChartInstance = $state<IChartApi | null>(null);
	let seriesInstance = $state<ISeriesApi<'Candlestick'> | null>(null);

	interface MacdSeries {
		histogram: ISeriesApi<'Histogram'>;
		macdLine: ISeriesApi<'Line'>;
		signalLine: ISeriesApi<'Line'>;
	}

	interface BbSeries {
		upper: ISeriesApi<'Line'>;
		middle: ISeriesApi<'Line'>;
		lower: ISeriesApi<'Line'>;
		bandsPrimitive: BandsIndicator;
	}

	let indicatorSeries = $state<Map<string, ISeriesApi<SeriesType> | MacdSeries | BbSeries>>(
		new Map()
	);
	let bottomIndicatorData = $state<Map<string, ({ time: Time; value: number } | MacdDataItem)[]>>(
		new Map()
	);
	let activeIndicators = $state<{ type: string; label: string; color?: string }[]>([]);
	let userAlertsPrimitive = $state<UserPriceAlerts | null>(null);
	let elliottWavesPrimitive = $state<ElliottWavesPrimitive | null>(null);
	let fibonacciPrimitive = $state<FibonacciPrimitive | null>(null);

	let showBottomPane = $derived(
		activeIndicators.some((i) => i.type === 'rsi' || i.type === 'macd' || i.type === 'obv')
	);

	let {
		candles = [],
		containerId = 'main-chart',
		alerts = [],
		onAddAlert,
		onRemoveAlert,
		averagePrice = 0,
		showAveragePrice = false,
		hasMoreData = true,
		isLoadingMore = $bindable(false),
		onLoadMoreData,
		elliottWaves = null,
		activeDegree = 'cycle',
		activeWaveType = 'impulse',
		isDrawingWave = false,
		selectedWaveDegree = $bindable<WaveDegree | null>(null),
		snapToWicks = false,
		onWaveChange,
		onDrawingModeChange,
		onDegreeChange,
		onWaveTypeChange,
		onWaveSelect,
		fibonacciTools = null,
		activeFibTool = 'retracement',
		isDrawingFib = false,
		selectedFibTool = $bindable<FibToolType | null>(null),
		onFibChange,
		onFibDrawingModeChange,
		onFibToolChange,
		onFibSelect
	} = $props<{
		candles?: Candle[];
		containerId?: string;
		alerts?: PriceAlert[];
		onAddAlert?: (price: number, condition: 'above' | 'below') => void;
		onRemoveAlert?: (alertId: number) => void;
		averagePrice?: number;
		showAveragePrice?: boolean;
		hasMoreData?: boolean;
		isLoadingMore?: boolean;
		onLoadMoreData?: () => void;
		elliottWaves?: SecurityElliottWaves | null;
		activeDegree?: WaveDegree;
		activeWaveType?: WaveType;
		isDrawingWave?: boolean;
		selectedWaveDegree?: WaveDegree | null;
		snapToWicks?: boolean;
		onWaveChange?: (degree: WaveDegree, waveCount: DegreeWaveCount | null) => void;
		onDrawingModeChange?: (isDrawing: boolean) => void;
		onDegreeChange?: (degree: WaveDegree) => void;
		onWaveTypeChange?: (type: WaveType) => void;
		onWaveSelect?: (degree: WaveDegree | null) => void;
		fibonacciTools?: SecurityFibonacciTools | null;
		activeFibTool?: FibToolType | null;
		isDrawingFib?: boolean;
		selectedFibTool?: FibToolType | null;
		onFibChange?: (tools: SecurityFibonacciTools) => void;
		onFibDrawingModeChange?: (isDrawing: boolean) => void;
		onFibToolChange?: (tool: FibToolType | null) => void;
		onFibSelect?: (tool: FibToolType | null) => void;
	}>();

	let avgPriceLine: IPriceLine | null = null;
	let previousFirstCandleTime: Time | null = null;
	let lastCandlesRef: Candle[] | null = null;

	const DEFAULT_PRICE_SCALE_MIN_WIDTH = 75;
	let syncedPriceScaleWidth = DEFAULT_PRICE_SCALE_MIN_WIDTH;

	function getTimeValue(t: Time): string | number {
		if (typeof t === 'string' || typeof t === 'number') return t;
		if (typeof t === 'object' && t !== null && 'year' in t) {
			return `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`;
		}
		return String(t);
	}

	function isSameLogicalRange(
		r1: { from: number; to: number } | null,
		r2: { from: number; to: number } | null
	): boolean {
		if (!r1 || !r2) return false;
		return Math.abs(r1.from - r2.from) < 0.0001 && Math.abs(r1.to - r2.to) < 0.0001;
	}

	function padIndicatorData<T extends { time: Time }>(
		data: T[],
		candlesList: Candle[]
	): (T | { time: Time })[] {
		if (!candlesList || candlesList.length === 0) return data;
		if (!data || data.length === 0) {
			return candlesList.map((c) => ({ time: c.time }));
		}
		const firstDataTime = getTimeValue(data[0].time);
		const firstIndex = candlesList.findIndex((c) => getTimeValue(c.time) === firstDataTime);
		if (firstIndex <= 0) return data;

		const padding: { time: Time }[] = candlesList
			.slice(0, firstIndex)
			.map((c) => ({ time: c.time }));
		return [...padding, ...data];
	}

	function syncPriceScaleWidths() {
		if (!chartInstance || !bottomChartInstance || !showBottomPane) return;
		const mainWidth = chartInstance.priceScale('right').width();
		const bottomWidth = bottomChartInstance.priceScale('right').width();
		const maxWidth = Math.max(mainWidth, bottomWidth, DEFAULT_PRICE_SCALE_MIN_WIDTH);
		if (maxWidth !== syncedPriceScaleWidth) {
			syncedPriceScaleWidth = maxWidth;
			chartInstance.priceScale('right').applyOptions({ minimumWidth: maxWidth });
			bottomChartInstance.priceScale('right').applyOptions({ minimumWidth: maxWidth });
		}
	}

	function getBottomIndicatorValueAtTime(type: string, time: Time): number {
		if (type === 'macd') return 0;
		const data = bottomIndicatorData.get(type);
		if (!data) return 0;
		const targetTimeVal = getTimeValue(time);
		const item = data.find((d) => getTimeValue(d.time) === targetTimeVal);
		if (item && 'value' in item && typeof item.value === 'number') {
			return item.value;
		}
		return 0;
	}

	$effect(() => {
		if (!hasMoreData) {
			isLoadingMore = false;
		}
	});

	$effect(() => {
		if (!seriesInstance) return;

		if (showAveragePrice && averagePrice > 0) {
			if (avgPriceLine) {
				seriesInstance.removePriceLine(avgPriceLine);
			}
			avgPriceLine = seriesInstance.createPriceLine({
				price: averagePrice,
				color: AVG_PRICE_LINE_COLOR,
				lineWidth: 2,
				lineStyle: 2, // Dashed
				axisLabelVisible: true,
				title: 'Avg Price'
			});
		} else if (avgPriceLine) {
			seriesInstance.removePriceLine(avgPriceLine);
			avgPriceLine = null;
		}
	});

	$effect(() => {
		const isBottomActive = showBottomPane;

		if (
			containerRef &&
			chartInstance &&
			(containerRef.clientWidth > 0 || containerRef.clientHeight > 0)
		) {
			chartInstance.applyOptions({
				width: containerRef.clientWidth,
				height: containerRef.clientHeight
			});
		}

		if (
			isBottomActive &&
			bottomChartInstance &&
			bottomContainerRef &&
			(bottomContainerRef.clientWidth > 0 || bottomContainerRef.clientHeight > 0)
		) {
			bottomChartInstance.applyOptions({
				width: bottomContainerRef.clientWidth,
				height: bottomContainerRef.clientHeight
			});
			if (chartInstance) {
				const sourceRange = chartInstance.timeScale().getVisibleLogicalRange();
				if (sourceRange) {
					const targetRange = bottomChartInstance.timeScale().getVisibleLogicalRange();
					if (!isSameLogicalRange(sourceRange, targetRange)) {
						bottomChartInstance.timeScale().setVisibleLogicalRange(sourceRange);
					}
				}
				syncPriceScaleWidths();
			}
		}
	});

	$effect(() => {
		if (userAlertsPrimitive && alerts) {
			const alertInfos: UserAlertInfo[] = (alerts as PriceAlert[]).map((a: PriceAlert) => ({
				id: a.id.toString(),
				price: a.target_price
			}));
			userAlertsPrimitive.setAlerts(alertInfos);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		if (activeDegree && elliottWavesPrimitive.getActiveDegree() !== activeDegree) {
			elliottWavesPrimitive.setActiveDegree(activeDegree);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		if (activeWaveType && elliottWavesPrimitive.getActiveWaveType() !== activeWaveType) {
			elliottWavesPrimitive.setActiveWaveType(activeWaveType);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		if (isDrawingWave !== undefined && elliottWavesPrimitive.isDrawingMode() !== isDrawingWave) {
			elliottWavesPrimitive.setDrawingMode(isDrawingWave);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		if (snapToWicks !== undefined && elliottWavesPrimitive.getSnapToWicks() !== snapToWicks) {
			elliottWavesPrimitive.setSnapToWicks(snapToWicks);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		if (
			selectedWaveDegree !== undefined &&
			elliottWavesPrimitive.getSelectedDegree() !== selectedWaveDegree
		) {
			elliottWavesPrimitive.setSelectedDegree(selectedWaveDegree);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		const currentCycle = elliottWavesPrimitive.getWaveCount('cycle');
		const currentPrimary = elliottWavesPrimitive.getWaveCount('primary');
		const currentIntermediate = elliottWavesPrimitive.getWaveCount('intermediate');
		const nextCycle = elliottWaves?.cycle ?? null;
		const nextPrimary = elliottWaves?.primary ?? null;
		const nextIntermediate = elliottWaves?.intermediate ?? null;

		if (!areWaveCountsEqual(currentCycle, nextCycle)) {
			elliottWavesPrimitive.setWaveCount('cycle', nextCycle);
		}
		if (!areWaveCountsEqual(currentPrimary, nextPrimary)) {
			elliottWavesPrimitive.setWaveCount('primary', nextPrimary);
		}
		if (!areWaveCountsEqual(currentIntermediate, nextIntermediate)) {
			elliottWavesPrimitive.setWaveCount('intermediate', nextIntermediate);
		}
	});

	$effect(() => {
		if (!fibonacciPrimitive) return;
		if (activeFibTool !== undefined && fibonacciPrimitive.getActiveTool() !== activeFibTool) {
			fibonacciPrimitive.setActiveTool(activeFibTool);
		}
	});

	$effect(() => {
		if (!fibonacciPrimitive) return;
		if (isDrawingFib !== undefined && fibonacciPrimitive.isDrawingMode() !== isDrawingFib) {
			fibonacciPrimitive.setDrawingMode(isDrawingFib);
		}
	});

	$effect(() => {
		if (!fibonacciPrimitive) return;
		if (selectedFibTool !== undefined && fibonacciPrimitive.getSelectedTool() !== selectedFibTool) {
			fibonacciPrimitive.setSelectedTool(selectedFibTool);
		}
	});

	$effect(() => {
		if (!fibonacciPrimitive) return;
		const currentDrawings = fibonacciPrimitive.getDrawings();
		const nextDrawings: SecurityFibonacciTools = fibonacciTools ?? {
			retracement: null,
			extension: null
		};

		if (!areFibonacciToolsEqual(currentDrawings, nextDrawings)) {
			fibonacciPrimitive.setDrawings(nextDrawings);
		}
	});

	$effect(() => {
		if (seriesInstance && candles && candles.length > 0) {
			if (candles === lastCandlesRef) {
				return;
			}
			lastCandlesRef = candles;

			const firstCandle = candles[0];
			const isPrepending =
				previousFirstCandleTime !== null &&
				getTimeValue(firstCandle.time) < getTimeValue(previousFirstCandleTime);

			let addedCandles = 0;
			let currentRange: { from: number; to: number } | null = null;

			if (isPrepending && previousFirstCandleTime !== null) {
				const prevIndex = candles.findIndex(
					(c: Candle) => getTimeValue(c.time) === getTimeValue(previousFirstCandleTime!)
				);
				if (prevIndex > 0) {
					addedCandles = prevIndex;
				}
				if (chartInstance) {
					const range = chartInstance.timeScale().getVisibleLogicalRange();
					if (range) {
						currentRange = { from: range.from, to: range.to };
					}
				}
			}

			seriesInstance.setData(candles);
			elliottWavesPrimitive?.setCandles(candles);
			fibonacciPrimitive?.setCandles(candles);

			if (chartInstance) {
				if (isPrepending && currentRange && addedCandles > 0) {
					chartInstance.timeScale().setVisibleLogicalRange({
						from: currentRange.from + addedCandles,
						to: currentRange.to + addedCandles
					});
				} else if (previousFirstCandleTime === null) {
					const visibleDays = 250;
					if (candles.length > visibleDays) {
						chartInstance.timeScale().setVisibleLogicalRange({
							from: candles.length - visibleDays,
							to: candles.length - 1
						});
					} else {
						chartInstance.timeScale().fitContent();
					}
				}
			}

			previousFirstCandleTime = firstCandle.time;
			isLoadingMore = false;
		}
	});

	onMount(() => {
		if (!containerRef || !bottomContainerRef) return;

		chartInstance = createChart(containerRef, {
			width: containerRef.clientWidth,
			height: containerRef.clientHeight,
			layout: {
				background: { color: 'transparent' },
				textColor: '#888'
			},
			grid: {
				vertLines: { color: '#40404020' },
				horzLines: { color: '#40404020' }
			},
			localization: {
				timeFormatter: formatLocalTime
			},
			timeScale: {
				timeVisible: true,
				borderVisible: false,
				tickMarkFormatter: formatLocalTickMark
			},
			leftPriceScale: {
				visible: false
			},
			rightPriceScale: {
				visible: true,
				minimumWidth: DEFAULT_PRICE_SCALE_MIN_WIDTH
			}
		});

		bottomChartInstance = createChart(bottomContainerRef, {
			width: bottomContainerRef.clientWidth,
			height: bottomContainerRef.clientHeight,
			layout: {
				background: { color: 'transparent' },
				textColor: '#888'
			},
			grid: {
				vertLines: { color: '#40404020' },
				horzLines: { color: '#40404020' }
			},
			localization: {
				timeFormatter: formatLocalTime
			},
			timeScale: {
				timeVisible: false,
				borderVisible: false,
				tickMarkFormatter: formatLocalTickMark
			},
			leftPriceScale: {
				visible: false
			},
			rightPriceScale: {
				visible: true,
				minimumWidth: DEFAULT_PRICE_SCALE_MIN_WIDTH
			}
		});

		chartInstance.timeScale().subscribeVisibleLogicalRangeChange((range) => {
			if (showBottomPane && chartInstance && bottomChartInstance) {
				const sourceRange = range ?? chartInstance.timeScale().getVisibleLogicalRange();
				if (sourceRange) {
					const targetRange = bottomChartInstance.timeScale().getVisibleLogicalRange();
					if (!isSameLogicalRange(sourceRange, targetRange)) {
						bottomChartInstance.timeScale().setVisibleLogicalRange(sourceRange);
					}
				}
				syncPriceScaleWidths();
			}
			if (range && range.from <= 10 && !isLoadingMore && hasMoreData) {
				isLoadingMore = true;
				onLoadMoreData?.();
			}
		});

		bottomChartInstance.timeScale().subscribeVisibleLogicalRangeChange((range) => {
			if (showBottomPane && chartInstance && bottomChartInstance) {
				const sourceRange = range ?? bottomChartInstance.timeScale().getVisibleLogicalRange();
				if (sourceRange) {
					const targetRange = chartInstance.timeScale().getVisibleLogicalRange();
					if (!isSameLogicalRange(sourceRange, targetRange)) {
						chartInstance.timeScale().setVisibleLogicalRange(sourceRange);
					}
				}
				syncPriceScaleWidths();
			}
		});

		chartInstance.subscribeCrosshairMove((param) => {
			if (!showBottomPane || !bottomChartInstance || !chartInstance) return;
			if (param.time === undefined || param.point === undefined) {
				bottomChartInstance.clearCrosshairPosition();
				return;
			}

			const activeBottom = activeIndicators.find(
				(i) => i.type === 'rsi' || i.type === 'macd' || i.type === 'obv'
			);
			if (!activeBottom) return;

			let targetSeries: ISeriesApi<SeriesType> | undefined;
			if (activeBottom.type === 'rsi' || activeBottom.type === 'obv') {
				targetSeries = indicatorSeries.get(activeBottom.type) as ISeriesApi<SeriesType> | undefined;
			} else if (activeBottom.type === 'macd') {
				const macdSeries = indicatorSeries.get('macd') as MacdSeries | undefined;
				targetSeries = macdSeries?.histogram;
			}

			if (!targetSeries) return;

			const price = getBottomIndicatorValueAtTime(activeBottom.type, param.time);
			bottomChartInstance.setCrosshairPosition(price, param.time, targetSeries);
		});

		seriesInstance = chartInstance.addSeries(CandlestickSeries, {
			upColor: '#26a69a',
			downColor: '#ef5350',
			borderVisible: false,
			wickUpColor: '#26a69a',
			wickDownColor: '#ef5350'
		});

		seriesInstance.priceScale().applyOptions({
			scaleMargins: { top: 0.1, bottom: 0.1 }
		});

		userAlertsPrimitive = new UserPriceAlerts();
		userAlertsPrimitive.setSymbolName('Price');
		seriesInstance.attachPrimitive(userAlertsPrimitive);

		userAlertsPrimitive.alertAdded().subscribe((alert: UserAlertInfo) => {
			const currentPrice = candles[candles.length - 1]?.close ?? 0;
			const condition = alert.price > currentPrice ? 'above' : 'below';
			if (onAddAlert) {
				onAddAlert(alert.price, condition);
			}
		});

		userAlertsPrimitive.alertRemoved().subscribe((idStr: string) => {
			const id = Number(idStr);
			if (!isNaN(id) && onRemoveAlert) {
				onRemoveAlert(id);
			}
		});

		elliottWavesPrimitive = new ElliottWavesPrimitive({
			activeDegree,
			activeWaveType,
			waves: {
				cycle: elliottWaves?.cycle ?? null,
				primary: elliottWaves?.primary ?? null,
				intermediate: elliottWaves?.intermediate ?? null
			},
			snapToWicks,
			selectedDegree: selectedWaveDegree
		});
		if (isDrawingWave) {
			elliottWavesPrimitive.setDrawingMode(isDrawingWave);
		}
		seriesInstance.attachPrimitive(elliottWavesPrimitive);

		elliottWavesPrimitive.wavePointsChanged().subscribe(({ degree, waveCount }) => {
			onWaveChange?.(degree, waveCount);
		});

		elliottWavesPrimitive.drawingModeChanged().subscribe((isDrawing) => {
			onDrawingModeChange?.(isDrawing);
		});

		elliottWavesPrimitive.degreeChanged().subscribe((degree) => {
			onDegreeChange?.(degree);
		});

		elliottWavesPrimitive.waveTypeChanged().subscribe((type) => {
			onWaveTypeChange?.(type);
		});

		elliottWavesPrimitive.selectionChanged().subscribe((degree) => {
			if (selectedWaveDegree !== degree) {
				selectedWaveDegree = degree;
			}
			onWaveSelect?.(degree);
		});

		fibonacciPrimitive = new FibonacciPrimitive({
			activeTool: activeFibTool,
			drawings: fibonacciTools ?? undefined,
			isDrawingMode: isDrawingFib,
			selectedTool: selectedFibTool
		});
		seriesInstance.attachPrimitive(fibonacciPrimitive);

		fibonacciPrimitive.drawingsChanged().subscribe((drawings) => {
			onFibChange?.(drawings);
		});

		fibonacciPrimitive.drawingModeChanged().subscribe((isDrawing) => {
			onFibDrawingModeChange?.(isDrawing);
		});

		fibonacciPrimitive.toolChanged().subscribe((tool) => {
			onFibToolChange?.(tool);
		});

		fibonacciPrimitive.selectionChanged().subscribe((tool) => {
			if (selectedFibTool !== tool) {
				selectedFibTool = tool;
			}
			onFibSelect?.(tool);
		});

		const resizeObserver = new ResizeObserver(() => {
			if (
				containerRef &&
				chartInstance &&
				(containerRef.clientWidth > 0 || containerRef.clientHeight > 0)
			) {
				chartInstance.applyOptions({
					width: containerRef.clientWidth,
					height: containerRef.clientHeight
				});
			}
			if (
				bottomContainerRef &&
				bottomChartInstance &&
				showBottomPane &&
				(bottomContainerRef.clientWidth > 0 || bottomContainerRef.clientHeight > 0)
			) {
				bottomChartInstance.applyOptions({
					width: bottomContainerRef.clientWidth,
					height: bottomContainerRef.clientHeight
				});
				syncPriceScaleWidths();
			}
		});

		resizeObserver.observe(containerRef);
		resizeObserver.observe(bottomContainerRef);

		return () => {
			resizeObserver.disconnect();
			userAlertsPrimitive?.destroy();
			elliottWavesPrimitive?.destroy();
			fibonacciPrimitive?.destroy();
			chartInstance?.remove();
			bottomChartInstance?.remove();
		};
	});

	export function updateData(newCandles: Candle[]) {
		if (seriesInstance) {
			lastCandlesRef = newCandles;
			seriesInstance.setData(newCandles);

			const visibleDays = 250;
			if (newCandles.length > visibleDays) {
				chartInstance?.timeScale()?.setVisibleLogicalRange({
					from: newCandles.length - visibleDays,
					to: newCandles.length - 1
				});
			} else {
				chartInstance?.timeScale()?.fitContent();
			}
		}
	}

	export function addIndicator(indicator: IndicatorData) {
		if (!chartInstance || indicatorSeries.has(indicator.type)) return;

		const isVolume = indicator.type === 'volume';
		const isBottomPane =
			indicator.type === 'rsi' || indicator.type === 'macd' || indicator.type === 'obv';
		const currentCandles = candles && candles.length > 0 ? candles : (lastCandlesRef ?? []);

		if (isBottomPane && bottomChartInstance) {
			let series;
			if (indicator.type === 'rsi') {
				const paddedData = padIndicatorData(
					indicator.data as { time: Time; value: number }[],
					currentCandles
				);
				series = bottomChartInstance.addSeries(LineSeries, {
					color: indicator.color,
					lineWidth: 2
				});
				indicatorSeries.set('rsi', series);
				bottomIndicatorData.set(
					'rsi',
					paddedData as ({ time: Time; value: number } | MacdDataItem)[]
				);
				if (paddedData.length > 0) series.setData(paddedData as never);
			} else if (indicator.type === 'macd') {
				const paddedData = padIndicatorData(indicator.data as MacdDataItem[], currentCandles);
				const histogram = bottomChartInstance.addSeries(HistogramSeries, { base: 0 });
				const macdLineColor = indicator.color || '#2962FF';
				const macdLine = bottomChartInstance.addSeries(LineSeries, {
					color: macdLineColor,
					lineWidth: 1
				});
				const signalLine = bottomChartInstance.addSeries(LineSeries, {
					color: '#FF6D00',
					lineWidth: 1
				});

				const macdSeries: MacdSeries = { histogram, macdLine, signalLine };
				indicatorSeries.set('macd', macdSeries);
				bottomIndicatorData.set(
					'macd',
					paddedData as ({ time: Time; value: number } | MacdDataItem)[]
				);

				if (paddedData.length > 0) {
					histogram.setData(
						paddedData.map((d) =>
							'histogram' in d && typeof d.histogram === 'number'
								? {
										time: d.time,
										value: d.histogram,
										color: d.histogram >= 0 ? '#26a69a80' : '#ef535080'
									}
								: { time: d.time }
						) as never
					);
					macdLine.setData(
						paddedData.map((d) =>
							'macd' in d && typeof d.macd === 'number'
								? { time: d.time, value: d.macd }
								: { time: d.time }
						) as never
					);
					signalLine.setData(
						paddedData.map((d) =>
							'signal' in d && typeof d.signal === 'number'
								? { time: d.time, value: d.signal }
								: { time: d.time }
						) as never
					);
				}
			} else if (indicator.type === 'obv') {
				const paddedData = padIndicatorData(
					indicator.data as { time: Time; value: number }[],
					currentCandles
				);
				series = bottomChartInstance.addSeries(LineSeries, {
					color: indicator.color,
					lineWidth: 2,
					priceFormat: {
						type: 'custom',
						formatter: (val: number) => `${(val / 1_000_000).toFixed(1)}M`
					}
				});
				indicatorSeries.set('obv', series);
				bottomIndicatorData.set(
					'obv',
					paddedData as ({ time: Time; value: number } | MacdDataItem)[]
				);
				if (paddedData.length > 0) series.setData(paddedData as never);
			}

			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];
			if (chartInstance) {
				const sourceRange = chartInstance.timeScale().getVisibleLogicalRange();
				if (sourceRange) {
					bottomChartInstance.timeScale().setVisibleLogicalRange(sourceRange);
				}
			}
			syncPriceScaleWidths();
			return;
		}

		if (indicator.type === 'bb' && chartInstance) {
			const hexToRgba = (hex: string, alpha: number) => {
				if (!hex) return `rgba(139, 92, 246, ${alpha})`;
				hex = hex.replace('#', '');
				if (hex.length === 3)
					hex = hex
						.split('')
						.map((c) => c + c)
						.join('');
				const r = parseInt(hex.slice(0, 2), 16) || 139;
				const g = parseInt(hex.slice(2, 4), 16) || 92;
				const b = parseInt(hex.slice(4, 6), 16) || 246;
				return `rgba(${r}, ${g}, ${b}, ${alpha})`;
			};

			const color = indicator.color || '#8b5cf6';

			const upper = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 0.5),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false
			});
			const middle = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 1),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false
			});
			const lower = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 0.5),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false
			});

			const bandsPrimitive = new BandsIndicator(
				indicator.data as BbDataItem[],
				hexToRgba(color, 0.15)
			);
			middle.attachPrimitive(bandsPrimitive);

			const bbSeries: BbSeries = { upper, middle, lower, bandsPrimitive };
			indicatorSeries.set('bb', bbSeries);

			if (indicator.data.length > 0) {
				upper.setData(
					(indicator.data as BbDataItem[]).map((d) => ({ time: d.time, value: d.upper }))
				);
				middle.setData(
					(indicator.data as BbDataItem[]).map((d) => ({ time: d.time, value: d.middle }))
				);
				lower.setData(
					(indicator.data as BbDataItem[]).map((d) => ({ time: d.time, value: d.lower }))
				);
			}

			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];
			return;
		}

		// Proceed with regular chart instance logic
		const seriesType = isVolume ? HistogramSeries : LineSeries;

		const options = {
			color: indicator.color,
			lineWidth: 2,
			crosshairMarkerVisible: true,
			priceLineVisible: false,
			title: indicator.label
		};

		if (isVolume) {
			Object.assign(options, {
				priceFormat: { type: 'volume' },
				priceScaleId: ''
			});
		}

		const series = chartInstance.addSeries(seriesType, options as never);

		if (isVolume) {
			series.priceScale().applyOptions({
				scaleMargins: { top: 0.7, bottom: 0 }
			});
			if (seriesInstance) {
				seriesInstance.priceScale().applyOptions({
					scaleMargins: { top: 0.1, bottom: 0.35 }
				});
			}
		}

		indicatorSeries.set(indicator.type, series);
		activeIndicators = [
			...activeIndicators,
			{ type: indicator.type, label: indicator.label, color: indicator.color }
		];

		if (indicator.data.length > 0) {
			series.setData(indicator.data as { time: Time; value: number }[]);
		}
	}

	export function removeIndicator(type: string) {
		if (!chartInstance || !indicatorSeries.has(type)) return;

		if (type === 'volume' && seriesInstance) {
			seriesInstance.priceScale().applyOptions({
				scaleMargins: { top: 0.1, bottom: 0.1 }
			});
		}

		const series = indicatorSeries.get(type);
		if (!series) return;

		if (type === 'macd' && bottomChartInstance) {
			const s = series as MacdSeries;
			bottomChartInstance.removeSeries(s.histogram);
			bottomChartInstance.removeSeries(s.macdLine);
			bottomChartInstance.removeSeries(s.signalLine);
		} else if ((type === 'rsi' || type === 'obv') && bottomChartInstance) {
			bottomChartInstance.removeSeries(series as ISeriesApi<SeriesType>);
		} else if (type === 'bb' && chartInstance) {
			const s = series as BbSeries;
			s.middle.detachPrimitive(s.bandsPrimitive);
			chartInstance.removeSeries(s.upper);
			chartInstance.removeSeries(s.middle);
			chartInstance.removeSeries(s.lower);
		} else {
			chartInstance.removeSeries(series as ISeriesApi<SeriesType>);
		}

		indicatorSeries.delete(type);
		bottomIndicatorData.delete(type);
		activeIndicators = activeIndicators.filter((i) => i.type !== type);
		if (!activeIndicators.some((i) => i.type === 'rsi' || i.type === 'macd' || i.type === 'obv')) {
			syncedPriceScaleWidth = DEFAULT_PRICE_SCALE_MIN_WIDTH;
			chartInstance
				.priceScale('right')
				.applyOptions({ minimumWidth: DEFAULT_PRICE_SCALE_MIN_WIDTH });
		} else {
			syncPriceScaleWidths();
		}
	}

	export function updateIndicatorData(indicator: IndicatorData) {
		const series = indicatorSeries.get(indicator.type);
		if (series) {
			const currentCandles = candles && candles.length > 0 ? candles : (lastCandlesRef ?? []);
			if (indicator.type === 'rsi' || indicator.type === 'obv') {
				const paddedData = padIndicatorData(
					indicator.data as { time: Time; value: number }[],
					currentCandles
				);
				bottomIndicatorData.set(
					indicator.type,
					paddedData as ({ time: Time; value: number } | MacdDataItem)[]
				);
				if ('setData' in series && typeof series.setData === 'function') {
					(series as ISeriesApi<SeriesType>).setData(paddedData as never);
				}
			} else if (indicator.type === 'macd') {
				const paddedData = padIndicatorData(indicator.data as MacdDataItem[], currentCandles);
				bottomIndicatorData.set(
					'macd',
					paddedData as ({ time: Time; value: number } | MacdDataItem)[]
				);
				const macdSeries = series as MacdSeries;
				macdSeries.histogram.setData(
					paddedData.map((d) =>
						'histogram' in d && typeof d.histogram === 'number'
							? {
									time: d.time,
									value: d.histogram,
									color: d.histogram >= 0 ? '#26a69a80' : '#ef535080'
								}
							: { time: d.time }
					) as never
				);
				macdSeries.macdLine.setData(
					paddedData.map((d) =>
						'macd' in d && typeof d.macd === 'number'
							? { time: d.time, value: d.macd }
							: { time: d.time }
					) as never
				);
				macdSeries.signalLine.setData(
					paddedData.map((d) =>
						'signal' in d && typeof d.signal === 'number'
							? { time: d.time, value: d.signal }
							: { time: d.time }
					) as never
				);
			} else if ('setData' in series && typeof series.setData === 'function') {
				(series as ISeriesApi<SeriesType>).setData(
					indicator.data as Parameters<ISeriesApi<SeriesType>['setData']>[0]
				);
			}
			syncPriceScaleWidths();
		} else {
			addIndicator(indicator);
		}
	}

	export function clearWave(degree?: WaveDegree) {
		elliottWavesPrimitive?.clearWave(degree);
	}

	export function getSelectedWaveDegree(): WaveDegree | null {
		return elliottWavesPrimitive?.getSelectedDegree() ?? null;
	}

	export function setSelectedWaveDegree(degree: WaveDegree | null) {
		elliottWavesPrimitive?.setSelectedDegree(degree);
	}

	export function getElliottWavesPrimitive(): ElliottWavesPrimitive | null {
		return elliottWavesPrimitive;
	}

	export function clearFibonacci(tool?: FibToolType) {
		fibonacciPrimitive?.clear(tool);
	}

	export function getSelectedFibTool(): FibToolType | null {
		return fibonacciPrimitive?.getSelectedTool() ?? null;
	}

	export function setSelectedFibTool(tool: FibToolType | null) {
		fibonacciPrimitive?.setSelectedTool(tool);
	}

	export function getFibonacciPrimitive(): FibonacciPrimitive | null {
		return fibonacciPrimitive;
	}
</script>

<div class="relative flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden">
	<!-- Container dynamically scales based on whether bottom pane is active -->
	<div
		bind:this={containerRef}
		id={containerId}
		class="min-h-0 w-full overflow-hidden"
		style="height: {showBottomPane ? '70%' : '100%'}"
	></div>

	<!-- Secondary chart placeholder for oscillators like RSI and MACD -->
	<div
		bind:this={bottomContainerRef}
		class="min-h-0 w-full overflow-hidden {showBottomPane ? 'border-t border-border' : ''}"
		style="height: {showBottomPane ? '30%' : '0'}; display: {showBottomPane ? 'block' : 'none'}"
	></div>

	{#if activeIndicators.length > 0}
		<div
			class="absolute top-4 left-4 flex flex-wrap gap-2 rounded-md bg-sidebar-accent/50 p-2 backdrop-blur-sm"
		>
			{#each activeIndicators as indicator (indicator.type)}
				<div class="flex items-center gap-1.5 px-1">
					{#if indicator.color}
						<div class="h-2 w-2 rounded-full" style="background-color: {indicator.color}"></div>
					{/if}
					<span class="text-[10px] font-medium tracking-wider text-sidebar-foreground/80 uppercase">
						{indicator.label}
					</span>
				</div>
			{/each}
		</div>
	{/if}
</div>
