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
		WaveDegree
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
		isDrawingWave = false,
		onWaveChange,
		onDrawingModeChange,
		onDegreeChange,
		fibonacciTools = null,
		activeFibTool = 'retracement',
		isDrawingFib = false,
		onFibChange,
		onFibDrawingModeChange,
		onFibToolChange
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
		isDrawingWave?: boolean;
		onWaveChange?: (degree: WaveDegree, waveCount: DegreeWaveCount | null) => void;
		onDrawingModeChange?: (isDrawing: boolean) => void;
		onDegreeChange?: (degree: WaveDegree) => void;
		fibonacciTools?: SecurityFibonacciTools | null;
		activeFibTool?: FibToolType | null;
		isDrawingFib?: boolean;
		onFibChange?: (tools: SecurityFibonacciTools) => void;
		onFibDrawingModeChange?: (isDrawing: boolean) => void;
		onFibToolChange?: (tool: FibToolType | null) => void;
	}>();

	let avgPriceLine: IPriceLine | null = null;
	let previousFirstCandleTime: Time | null = null;
	let lastCandlesRef: Candle[] | null = null;

	function getTimeValue(t: Time): string | number {
		if (typeof t === 'string' || typeof t === 'number') return t;
		if (typeof t === 'object' && t !== null && 'year' in t) {
			return `${t.year}-${String(t.month).padStart(2, '0')}-${String(t.day).padStart(2, '0')}`;
		}
		return String(t);
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
				const range = chartInstance.timeScale().getVisibleLogicalRange();
				if (range) bottomChartInstance.timeScale().setVisibleLogicalRange(range);
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
		if (isDrawingWave !== undefined && elliottWavesPrimitive.isDrawingMode() !== isDrawingWave) {
			elliottWavesPrimitive.setDrawingMode(isDrawingWave);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		const currentCycle = elliottWavesPrimitive.getWaveCount('cycle');
		const currentPrimary = elliottWavesPrimitive.getWaveCount('primary');
		const nextCycle = elliottWaves?.cycle ?? null;
		const nextPrimary = elliottWaves?.primary ?? null;

		if (!areWaveCountsEqual(currentCycle, nextCycle)) {
			elliottWavesPrimitive.setWaveCount('cycle', nextCycle);
		}
		if (!areWaveCountsEqual(currentPrimary, nextPrimary)) {
			elliottWavesPrimitive.setWaveCount('primary', nextPrimary);
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
			}
		});

		chartInstance.timeScale().subscribeVisibleLogicalRangeChange((range) => {
			if (showBottomPane && bottomChartInstance && range) {
				bottomChartInstance.timeScale().setVisibleLogicalRange(range);
			}
			if (range && range.from <= 10 && !isLoadingMore && hasMoreData) {
				isLoadingMore = true;
				onLoadMoreData?.();
			}
		});

		bottomChartInstance.timeScale().subscribeVisibleLogicalRangeChange((range) => {
			if (showBottomPane && chartInstance && range) {
				chartInstance.timeScale().setVisibleLogicalRange(range);
			}
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
			waves: {
				cycle: elliottWaves?.cycle ?? null,
				primary: elliottWaves?.primary ?? null
			}
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

		fibonacciPrimitive = new FibonacciPrimitive({
			activeTool: activeFibTool,
			drawings: fibonacciTools ?? undefined,
			isDrawingMode: isDrawingFib
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
			}
		});

		resizeObserver.observe(containerRef);
		resizeObserver.observe(bottomContainerRef);

		return () => {
			resizeObserver.disconnect();
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

		if (isBottomPane && bottomChartInstance) {
			let series;
			if (indicator.type === 'rsi') {
				series = bottomChartInstance.addSeries(LineSeries, {
					color: indicator.color,
					lineWidth: 2
				});
				indicatorSeries.set('rsi', series);
				if (indicator.data.length > 0) series.setData(indicator.data);
			} else if (indicator.type === 'macd') {
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

				if (indicator.data.length > 0) {
					histogram.setData(
						(indicator.data as MacdDataItem[]).map((d) => ({
							time: d.time,
							value: d.histogram,
							color: d.histogram >= 0 ? '#26a69a80' : '#ef535080'
						}))
					);
					macdLine.setData(
						(indicator.data as MacdDataItem[]).map((d) => ({ time: d.time, value: d.macd }))
					);
					signalLine.setData(
						(indicator.data as MacdDataItem[]).map((d) => ({ time: d.time, value: d.signal }))
					);
				}
			} else if (indicator.type === 'obv') {
				series = bottomChartInstance.addSeries(LineSeries, {
					color: indicator.color,
					lineWidth: 2,
					priceScaleId: 'left'
				});
				indicatorSeries.set('obv', series);
				if (indicator.data.length > 0) series.setData(indicator.data);
				bottomChartInstance.priceScale('left').applyOptions({ visible: true });
			}

			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];
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
			if (type === 'obv') {
				bottomChartInstance.priceScale('left').applyOptions({ visible: false });
			}
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
		activeIndicators = activeIndicators.filter((i) => i.type !== type);
	}

	export function updateIndicatorData(indicator: IndicatorData) {
		const series = indicatorSeries.get(indicator.type);
		if (series) {
			if ('setData' in series && typeof series.setData === 'function') {
				(series as ISeriesApi<SeriesType>).setData(
					indicator.data as Parameters<ISeriesApi<SeriesType>['setData']>[0]
				);
			}
		} else {
			addIndicator(indicator);
		}
	}

	export function clearWave(degree?: WaveDegree) {
		elliottWavesPrimitive?.clearWave(degree);
	}

	export function getElliottWavesPrimitive(): ElliottWavesPrimitive | null {
		return elliottWavesPrimitive;
	}

	export function clearFibonacci(tool?: FibToolType) {
		fibonacciPrimitive?.clear(tool);
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
