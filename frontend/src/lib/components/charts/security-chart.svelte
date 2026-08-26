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
	let chartInstance = $state<IChartApi | null>(null);
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

	let {
		candles = [],
		containerId = 'main-chart',
		alerts = [],
		onAddAlert,
		onRemoveAlert,
		averagePrice = 0,
		showAveragePrice = false,
		hideLabels = false,
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
		hideLabels?: boolean;
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
	const OSCILLATOR_ORDER = ['rsi', 'macd', 'obv'] as const;

	function updatePanes() {
		if (!chartInstance || !seriesInstance) return;

		const activeOscillators = OSCILLATOR_ORDER.filter((type) => indicatorSeries.has(type));
		const count = activeOscillators.length;
		const hasVolume = indicatorSeries.has('volume');

		if (count === 0) {
			if (hasVolume) {
				const volumeSeries = indicatorSeries.get('volume') as ISeriesApi<'Histogram'> | undefined;
				volumeSeries?.priceScale().applyOptions({
					scaleMargins: { top: 0.7, bottom: 0 }
				});
				seriesInstance.priceScale().applyOptions({
					scaleMargins: { top: 0.1, bottom: 0.35 }
				});
			} else {
				seriesInstance.priceScale().applyOptions({
					scaleMargins: { top: 0.1, bottom: 0.1 }
				});
			}
			return;
		}

		// When oscillators exist, allocate vertical space
		const paneHeight = count === 1 ? 0.25 : count === 2 ? 0.18 : 0.14;
		const gap = 0.02;
		const totalOscillatorHeight = count * paneHeight + count * gap;
		const mainAreaHeight = Math.max(0.3, 1.0 - totalOscillatorHeight);

		// Configure main candlesticks and volume within [0, mainAreaHeight]
		if (hasVolume) {
			const volumeHeight = Math.round(mainAreaHeight * 0.25 * 10000) / 10000;
			const volumeTop = Math.round((mainAreaHeight - volumeHeight) * 10000) / 10000;
			const volumeBottom = Math.round((1.0 - mainAreaHeight) * 10000) / 10000;

			const volumeSeries = indicatorSeries.get('volume') as ISeriesApi<'Histogram'> | undefined;
			volumeSeries?.priceScale().applyOptions({
				scaleMargins: {
					top: volumeTop,
					bottom: volumeBottom
				}
			});

			seriesInstance.priceScale().applyOptions({
				scaleMargins: {
					top: 0.05,
					bottom: Math.round((1.0 - mainAreaHeight + volumeHeight + 0.03) * 10000) / 10000
				}
			});
		} else {
			seriesInstance.priceScale().applyOptions({
				scaleMargins: {
					top: 0.05,
					bottom: Math.round((1.0 - mainAreaHeight + 0.03) * 10000) / 10000
				}
			});
		}

		// Configure each oscillator pane
		activeOscillators.forEach((type, idx) => {
			const paneTop = Math.round((mainAreaHeight + gap + idx * (paneHeight + gap)) * 10000) / 10000;
			const paneBottom = Math.max(0, Math.round((1.0 - (paneTop + paneHeight)) * 10000) / 10000);

			chartInstance?.priceScale(type).applyOptions({
				scaleMargins: {
					top: paneTop,
					bottom: paneBottom
				}
			});
		});
	}

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
				axisLabelVisible: !hideLabels,
				title: 'Avg Price'
			});
		} else if (avgPriceLine) {
			seriesInstance.removePriceLine(avgPriceLine);
			avgPriceLine = null;
		}
	});

	$effect(() => {
		const visible = !hideLabels;
		for (const [, s] of indicatorSeries.entries()) {
			if (!s) continue;
			if ('histogram' in s && 'macdLine' in s && 'signalLine' in s) {
				s.histogram.applyOptions?.({ lastValueVisible: visible, priceLineVisible: visible });
				s.macdLine.applyOptions?.({ lastValueVisible: visible, priceLineVisible: visible });
				s.signalLine.applyOptions?.({ lastValueVisible: visible, priceLineVisible: visible });
			} else if ('upper' in s && 'middle' in s && 'lower' in s) {
				s.upper.applyOptions?.({ lastValueVisible: visible });
				s.middle.applyOptions?.({ lastValueVisible: visible });
				s.lower.applyOptions?.({ lastValueVisible: visible });
			} else if ('applyOptions' in s && typeof s.applyOptions === 'function') {
				s.applyOptions({
					lastValueVisible: visible,
					priceLineVisible: visible
				});
			}
		}
	});

	$effect(() => {
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
		if (!containerRef) return;

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

		chartInstance.timeScale().subscribeVisibleLogicalRangeChange((range) => {
			if (range && range.from <= 10 && !isLoadingMore && hasMoreData) {
				isLoadingMore = true;
				onLoadMoreData?.();
			}
		});

		seriesInstance = chartInstance.addSeries(CandlestickSeries, {
			upColor: '#26a69a',
			downColor: '#ef5350',
			borderVisible: false,
			wickUpColor: '#26a69a',
			wickDownColor: '#ef5350'
		});

		updatePanes();

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
		});

		resizeObserver.observe(containerRef);

		return () => {
			resizeObserver.disconnect();
			userAlertsPrimitive?.destroy();
			elliottWavesPrimitive?.destroy();
			fibonacciPrimitive?.destroy();
			chartInstance?.remove();
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

		if (indicator.type === 'volume') {
			const series = chartInstance.addSeries(HistogramSeries, {
				priceScaleId: 'volume',
				color: indicator.color,
				priceFormat: { type: 'volume' },
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: indicator.label
			});
			indicatorSeries.set('volume', series);
			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];
			if (indicator.data.length > 0) {
				series.setData(indicator.data as { time: Time; value: number }[]);
			}
			updatePanes();
			return;
		}

		if (indicator.type === 'rsi') {
			const series = chartInstance.addSeries(LineSeries, {
				priceScaleId: 'rsi',
				color: indicator.color,
				lineWidth: 2,
				crosshairMarkerVisible: true,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: indicator.label
			});
			indicatorSeries.set('rsi', series);
			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];
			if (indicator.data.length > 0) {
				series.setData(indicator.data as { time: Time; value: number }[]);
			}
			updatePanes();
			return;
		}

		if (indicator.type === 'macd') {
			const histogram = chartInstance.addSeries(HistogramSeries, {
				priceScaleId: 'macd',
				base: 0,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: 'MACD Hist'
			});
			const macdLineColor = indicator.color || '#2962FF';
			const macdLine = chartInstance.addSeries(LineSeries, {
				priceScaleId: 'macd',
				color: macdLineColor,
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: 'MACD'
			});
			const signalLine = chartInstance.addSeries(LineSeries, {
				priceScaleId: 'macd',
				color: '#FF6D00',
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: 'Signal'
			});

			const macdSeries: MacdSeries = { histogram, macdLine, signalLine };
			indicatorSeries.set('macd', macdSeries);
			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];

			if (indicator.data.length > 0) {
				const macdData = indicator.data as MacdDataItem[];
				histogram.setData(
					macdData.map((d) =>
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
					macdData.map((d) =>
						'macd' in d && typeof d.macd === 'number'
							? { time: d.time, value: d.macd }
							: { time: d.time }
					) as never
				);
				signalLine.setData(
					macdData.map((d) =>
						'signal' in d && typeof d.signal === 'number'
							? { time: d.time, value: d.signal }
							: { time: d.time }
					) as never
				);
			}
			updatePanes();
			return;
		}

		if (indicator.type === 'obv') {
			const series = chartInstance.addSeries(LineSeries, {
				priceScaleId: 'obv',
				color: indicator.color,
				lineWidth: 2,
				crosshairMarkerVisible: true,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: indicator.label,
				priceFormat: {
					type: 'custom',
					formatter: (val: number) => `${(val / 1_000_000).toFixed(1)}M`
				}
			});
			indicatorSeries.set('obv', series);
			activeIndicators = [
				...activeIndicators,
				{ type: indicator.type, label: indicator.label, color: indicator.color }
			];
			if (indicator.data.length > 0) {
				series.setData(indicator.data as { time: Time; value: number }[]);
			}
			updatePanes();
			return;
		}

		if (indicator.type === 'bb') {
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
				priceLineVisible: false,
				lastValueVisible: !hideLabels
			});
			const middle = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 1),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false,
				lastValueVisible: !hideLabels
			});
			const lower = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 0.5),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false,
				lastValueVisible: !hideLabels
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

		// Proceed with regular overlays (MA50, MA200, etc.)
		const series = chartInstance.addSeries(LineSeries, {
			color: indicator.color,
			lineWidth: 2,
			crosshairMarkerVisible: true,
			priceLineVisible: !hideLabels,
			lastValueVisible: !hideLabels,
			title: indicator.label
		});

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

		const series = indicatorSeries.get(type);
		if (!series) return;

		if (type === 'macd') {
			const s = series as MacdSeries;
			chartInstance.removeSeries(s.histogram);
			chartInstance.removeSeries(s.macdLine);
			chartInstance.removeSeries(s.signalLine);
		} else if (type === 'bb') {
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
		updatePanes();
	}

	export function updateIndicatorData(indicator: IndicatorData) {
		const series = indicatorSeries.get(indicator.type);
		if (series) {
			if (indicator.type === 'rsi' || indicator.type === 'obv') {
				if ('setData' in series && typeof series.setData === 'function') {
					(series as ISeriesApi<SeriesType>).setData(
						indicator.data as Parameters<ISeriesApi<SeriesType>['setData']>[0]
					);
				}
			} else if (indicator.type === 'macd') {
				const macdSeries = series as MacdSeries;
				const macdData = indicator.data as MacdDataItem[];
				macdSeries.histogram.setData(
					macdData.map((d) =>
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
					macdData.map((d) =>
						'macd' in d && typeof d.macd === 'number'
							? { time: d.time, value: d.macd }
							: { time: d.time }
					) as never
				);
				macdSeries.signalLine.setData(
					macdData.map((d) =>
						'signal' in d && typeof d.signal === 'number'
							? { time: d.time, value: d.signal }
							: { time: d.time }
					) as never
				);
			} else if (indicator.type === 'bb') {
				const s = series as BbSeries;
				const bbData = indicator.data as BbDataItem[];
				if (bbData.length > 0) {
					s.upper.setData(bbData.map((d) => ({ time: d.time, value: d.upper })));
					s.middle.setData(bbData.map((d) => ({ time: d.time, value: d.middle })));
					s.lower.setData(bbData.map((d) => ({ time: d.time, value: d.lower })));
				}
			} else if ('setData' in series && typeof series.setData === 'function') {
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
	<div
		bind:this={containerRef}
		id={containerId}
		class="h-full min-h-0 w-full overflow-hidden"
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
