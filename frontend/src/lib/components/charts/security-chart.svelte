<script lang="ts">
	import {
		CandlestickSeries,
		createChart,
		CrosshairMode,
		LineSeries,
		HistogramSeries
	} from 'lightweight-charts';
	import type { Time, IChartApi, ISeriesApi, IPriceLine, SeriesType } from 'lightweight-charts';
	import { onMount } from 'svelte';
	import type { Candle } from '@/utils/finance/candle';
	import { formatLocalTime, formatLocalTickMark } from '@/utils/date';
	import { generateFutureWhitespace, DEFAULT_FUTURE_BARS } from './plugins/helpers/time/time';
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
	import { areSecurityElliottWavesEqual, normalizeWaveIds } from '$lib/utils/finance/elliott-wave';
	import { FibonacciPrimitive } from './plugins/fibonacci/fibonacci-primitive';
	import type { FibToolType, SecurityFibonacciTools } from '$lib/utils/finance/fibonacci';
	import {
		areFibonacciToolsEqual,
		getActiveFibLevelPrices,
		normalizeSecurityFibonacciTools
	} from '$lib/utils/finance/fibonacci';
	import {
		computePaneBandHeights,
		computePaneScaleMargins,
		MAX_PANE_FRACTION,
		MIN_PANE_FRACTION,
		MAIN_PANE_ID,
		OSCILLATOR_PANE_IDS,
		VOLUME_PANE_ID
	} from '$lib/chart/indicator-pane-layout';
	import type { PaneHeights } from '$lib/chart/indicator-pane-layout';

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
		onFibSelect,
		onFibDoubleClick,
		futureBars = DEFAULT_FUTURE_BARS,
		onPaneHeightsChange
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
		onWaveChange?: (
			degree: WaveDegree,
			waveCount: DegreeWaveCount | null,
			allWaves?: SecurityElliottWaves
		) => void;
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
		onFibDoubleClick?: (tool: FibToolType) => void;
		futureBars?: number;
		onPaneHeightsChange?: (heights: PaneHeights | null) => void;
	}>();

	let avgPriceLine: IPriceLine | null = null;
	let previousFirstCandleTime: Time | null = null;
	let lastCandlesRef: Candle[] | null = null;
	let currentWhitespaceCount = DEFAULT_FUTURE_BARS;
	let isUpdatingWhitespace = false;

	// Prices of every enabled/drawn Fib level on this chart. Pushed into the Elliott wave
	// primitive so wave points can snap to them (financed from utils, never a sibling plugin).
	const fibSnapPrices = $derived(getActiveFibLevelPrices(fibonacciTools));
	let appliedFibSnapPricesSignature: string | null = null;

	function checkAndExpandWhitespace(range?: { from: number; to: number } | null) {
		if (isUpdatingWhitespace || !seriesInstance || !chartInstance || candles.length === 0) {
			return;
		}

		const logicalRange = range ?? chartInstance.timeScale().getVisibleLogicalRange();
		const lastCandleIndex = candles.length - 1;
		const currentEndIndex = lastCandleIndex + currentWhitespaceCount;

		let neededWhitespace = currentWhitespaceCount;

		if (logicalRange) {
			const threshold = Math.max(lastCandleIndex + 1, currentEndIndex - 30);
			if (logicalRange.to >= threshold) {
				const rangeNeeded = Math.ceil(logicalRange.to - lastCandleIndex) + 100;
				if (rangeNeeded > neededWhitespace) {
					neededWhitespace = rangeNeeded;
				}
			}
		}

		if (containerRef && containerRef.clientWidth > 0) {
			const widthBars = Math.ceil(containerRef.clientWidth / 4) + 100;
			if (widthBars > neededWhitespace) {
				neededWhitespace = widthBars;
			}
		}

		if (neededWhitespace > currentWhitespaceCount) {
			isUpdatingWhitespace = true;
			try {
				const savedRange = logicalRange ?? chartInstance.timeScale().getVisibleLogicalRange();
				currentWhitespaceCount = neededWhitespace;
				const whitespace = generateFutureWhitespace(candles, currentWhitespaceCount);
				seriesInstance.setData([...candles, ...whitespace]);
				if (savedRange) {
					chartInstance.timeScale().setVisibleLogicalRange(savedRange);
				}
			} finally {
				isUpdatingWhitespace = false;
			}
		}
	}

	const DEFAULT_PRICE_SCALE_MIN_WIDTH = 75;

	/** User-customised pane band heights, or null when the default layout is used. */
	let customPaneHeights = $state<PaneHeights | null>(null);

	/**
	 * Ordered pane ids currently rendered. Kept in explicit state (rather than
	 * derived from `indicatorSeries`) so it reliably updates when indicators are
	 * added/removed imperatively through the exported API.
	 */
	let orderedPaneIds = $state<string[]>([MAIN_PANE_ID]);

	function getOrderedPaneIds(): string[] {
		const ids: string[] = [MAIN_PANE_ID];
		if (indicatorSeries.has(VOLUME_PANE_ID)) ids.push(VOLUME_PANE_ID);
		for (const type of OSCILLATOR_PANE_IDS) {
			if (indicatorSeries.has(type)) ids.push(type);
		}
		return ids;
	}

	function refreshOrderedPaneIds() {
		const next = getOrderedPaneIds();
		if (next.length !== orderedPaneIds.length || next.some((id, i) => id !== orderedPaneIds[i])) {
			orderedPaneIds = next;
		}
	}

	const paneLayout = $derived(computePaneScaleMargins(orderedPaneIds, customPaneHeights));
	const paneLayoutCustom = $derived.by(() => {
		const custom = customPaneHeights;
		if (custom === null) return false;
		return orderedPaneIds.some((id) => id in custom);
	});

	interface PaneBoundary {
		key: string;
		upperId: string;
		lowerId: string;
		fraction: number;
	}

	const paneBoundaries = $derived.by(() => {
		const ids = orderedPaneIds;
		const margins = paneLayout;
		const boundaries: PaneBoundary[] = [];
		for (let i = 0; i < ids.length - 1; i++) {
			const upperId = ids[i];
			const lowerId = ids[i + 1];
			const upperEnd = 1 - (margins[upperId]?.bottom ?? 0);
			const lowerStart = margins[lowerId]?.top ?? 0;
			boundaries.push({
				key: `${upperId}-${lowerId}`,
				upperId,
				lowerId,
				fraction: (upperEnd + lowerStart) / 2
			});
		}
		return boundaries;
	});

	function applyPaneMargins() {
		if (!chartInstance || !seriesInstance) return;
		refreshOrderedPaneIds();
		const paneIds = orderedPaneIds;
		const margins = computePaneScaleMargins(paneIds, customPaneHeights);
		for (const id of paneIds) {
			const scaleMargins = margins[id];
			if (!scaleMargins) continue;
			if (id === MAIN_PANE_ID) {
				seriesInstance.priceScale().applyOptions({ scaleMargins });
			} else {
				chartInstance.priceScale(id).applyOptions({ scaleMargins });
			}
		}
	}

	function updatePanes() {
		applyPaneMargins();
	}

	interface PaneDragState {
		upperId: string;
		lowerId: string;
		startY: number;
		startHeights: PaneHeights;
	}

	let paneDragState = $state<PaneDragState | null>(null);

	function clampPaneFraction(value: number): number {
		return Math.min(MAX_PANE_FRACTION, Math.max(MIN_PANE_FRACTION, value));
	}

	function handlePaneDragStart(event: PointerEvent, upperId: string, lowerId: string) {
		if (!chartInstance || !seriesInstance) return;
		event.preventDefault();
		event.stopPropagation();
		if (typeof (event.currentTarget as HTMLElement)?.setPointerCapture === 'function') {
			try {
				(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
			} catch {
				// ignore — jsdom and unsupported browsers
			}
		}
		paneDragState = {
			upperId,
			lowerId,
			startY: event.clientY,
			startHeights: computePaneBandHeights(getOrderedPaneIds(), customPaneHeights)
		};
	}

	function handlePaneDragMove(event: PointerEvent) {
		const drag = paneDragState;
		if (!drag) return;
		const containerHeight = containerRef?.clientHeight ?? 0;
		if (containerHeight <= 0) return;

		const delta = (event.clientY - drag.startY) / containerHeight;
		const sum = (drag.startHeights[drag.upperId] ?? 0) + (drag.startHeights[drag.lowerId] ?? 0);

		let upper = clampPaneFraction((drag.startHeights[drag.upperId] ?? 0) + delta);
		let lower = sum - upper;
		if (lower < MIN_PANE_FRACTION) {
			lower = MIN_PANE_FRACTION;
			upper = clampPaneFraction(sum - MIN_PANE_FRACTION);
		} else if (lower > MAX_PANE_FRACTION) {
			lower = MAX_PANE_FRACTION;
			upper = clampPaneFraction(sum - MAX_PANE_FRACTION);
		}

		customPaneHeights = {
			...drag.startHeights,
			[drag.upperId]: upper,
			[drag.lowerId]: lower
		};
		updatePanes();
	}

	function handlePaneDragEnd() {
		if (!paneDragState) return;
		paneDragState = null;
		if (customPaneHeights) {
			onPaneHeightsChange?.({ ...customPaneHeights });
		}
	}

	function handleResetPaneHeights() {
		customPaneHeights = null;
		updatePanes();
		onPaneHeightsChange?.(null);
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
		for (const [type, s] of indicatorSeries.entries()) {
			if (!s) continue;
			const indInfo = activeIndicators.find((i) => i.type === type);
			const label = indInfo?.label ?? type.toUpperCase();

			if ('histogram' in s && 'macdLine' in s && 'signalLine' in s) {
				s.histogram.applyOptions?.({
					lastValueVisible: visible,
					priceLineVisible: visible,
					title: visible ? 'MACD Hist' : ''
				});
				s.macdLine.applyOptions?.({
					lastValueVisible: visible,
					priceLineVisible: visible,
					title: visible ? 'MACD' : ''
				});
				s.signalLine.applyOptions?.({
					lastValueVisible: visible,
					priceLineVisible: visible,
					title: visible ? 'Signal' : ''
				});
			} else if ('upper' in s && 'middle' in s && 'lower' in s) {
				s.upper.applyOptions?.({
					lastValueVisible: visible,
					title: visible ? `${label} Upper` : ''
				});
				s.middle.applyOptions?.({
					lastValueVisible: visible,
					title: visible ? label : ''
				});
				s.lower.applyOptions?.({
					lastValueVisible: visible,
					title: visible ? `${label} Lower` : ''
				});
			} else if ('applyOptions' in s && typeof s.applyOptions === 'function') {
				s.applyOptions({
					lastValueVisible: visible,
					priceLineVisible: visible,
					title: visible ? label : ''
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
		const currentWaves: SecurityElliottWaves = {
			waves: elliottWavesPrimitive.getAllWaves()
		};
		// Legacy persisted anchors may be date strings/BusinessDay; normalize to epoch on feed-in.
		const nextWaves: SecurityElliottWaves = {
			waves: normalizeWaveIds(elliottWaves?.waves ?? [])
		};

		if (!areSecurityElliottWavesEqual(currentWaves, nextWaves)) {
			elliottWavesPrimitive.setWaves(nextWaves.waves);
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
		if (!chartInstance) return;
		const isDrawing = Boolean(isDrawingWave || isDrawingFib);
		chartInstance.applyOptions({
			handleScroll: {
				pressedMouseMove: !isDrawing
			}
		});
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
		// Legacy persisted anchors may be date strings/BusinessDay; normalize to epoch on feed-in.
		const nextDrawings: SecurityFibonacciTools = normalizeSecurityFibonacciTools(
			fibonacciTools ?? {
				retracement: null,
				extension: null
			}
		);

		if (!areFibonacciToolsEqual(currentDrawings, nextDrawings)) {
			fibonacciPrimitive.setDrawings(nextDrawings);
		}
	});

	$effect(() => {
		if (!elliottWavesPrimitive) return;
		// Cheap signature guard: `fibSnapPrices` is a fresh array whenever the tools change,
		// so compare contents before pushing to avoid update churn on unrelated fib edits.
		const signature = `${fibSnapPrices.length}:${fibSnapPrices.join(',')}`;
		if (signature === appliedFibSnapPricesSignature) return;
		appliedFibSnapPricesSignature = signature;
		elliottWavesPrimitive.setFibLevelPrices(fibSnapPrices);
	});

	$effect(() => {
		if (seriesInstance && candles) {
			if (candles.length === 0) {
				if (candles === lastCandlesRef) {
					return;
				}
				lastCandlesRef = candles;
				currentWhitespaceCount = futureBars;
				seriesInstance.setData([]);
				elliottWavesPrimitive?.setCandles([]);
				fibonacciPrimitive?.setCandles([]);
				previousFirstCandleTime = null;
				isLoadingMore = false;
				return;
			}

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
			} else if (previousFirstCandleTime === null) {
				currentWhitespaceCount = futureBars;
				if (containerRef && containerRef.clientWidth > 0) {
					const widthBars = Math.ceil(containerRef.clientWidth / 4) + 100;
					if (widthBars > currentWhitespaceCount) {
						currentWhitespaceCount = widthBars;
					}
				}
			}

			const whitespace = generateFutureWhitespace(candles, currentWhitespaceCount);
			seriesInstance.setData([...candles, ...whitespace]);
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
					chartInstance.timeScale().setVisibleLogicalRange({
						from: Math.max(0, candles.length - visibleDays),
						to: candles.length - 1
					});
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
			crosshair: {
				mode: CrosshairMode.Normal
			},
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
				tickMarkFormatter: formatLocalTickMark,
				ignoreWhitespaceIndices: false
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
			if (range) {
				checkAndExpandWhitespace(range);
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
			waves: normalizeWaveIds(elliottWaves?.waves ?? []),
			snapToWicks,
			selectedDegree: selectedWaveDegree
		});
		if (isDrawingWave) {
			elliottWavesPrimitive.setDrawingMode(isDrawingWave);
		}
		seriesInstance.attachPrimitive(elliottWavesPrimitive);

		elliottWavesPrimitive.wavePointsChanged().subscribe(({ degree, waveCount }) => {
			const fullWaves: SecurityElliottWaves = {
				waves: elliottWavesPrimitive?.getAllWaves() ?? []
			};
			onWaveChange?.(degree, waveCount, fullWaves);
		});

		elliottWavesPrimitive.drawingModeChanged().subscribe((isDrawing) => {
			if (!isDrawing && !isDrawingFib && chartInstance) {
				chartInstance.applyOptions({ handleScroll: { pressedMouseMove: true } });
			}
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
			drawings: fibonacciTools ? normalizeSecurityFibonacciTools(fibonacciTools) : undefined,
			isDrawingMode: isDrawingFib,
			selectedTool: selectedFibTool
		});
		seriesInstance.attachPrimitive(fibonacciPrimitive);

		fibonacciPrimitive.drawingsChanged().subscribe((drawings) => {
			onFibChange?.(drawings);
		});

		fibonacciPrimitive.drawingModeChanged().subscribe((isDrawing) => {
			if (!isDrawing && !isDrawingWave && chartInstance) {
				chartInstance.applyOptions({ handleScroll: { pressedMouseMove: true } });
			}
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

		fibonacciPrimitive.doubleClicked().subscribe((tool) => {
			onFibDoubleClick?.(tool);
		});

		const handleWheel = (event: WheelEvent) => {
			if (!containerRef || !chartInstance || !seriesInstance) return;
			const rect = containerRef.getBoundingClientRect();
			const x = event.clientX - rect.left;
			const priceScale = seriesInstance.priceScale();
			const priceScaleWidth =
				(priceScale && typeof priceScale.width === 'function' ? priceScale.width() : 0) ||
				DEFAULT_PRICE_SCALE_MIN_WIDTH;

			if (x >= containerRef.clientWidth - priceScaleWidth) {
				event.preventDefault();
				event.stopPropagation();

				const currentRange = priceScale.getVisibleRange?.();
				if (!currentRange || currentRange.to <= currentRange.from) return;

				const delta = event.deltaY;
				if (delta === 0) return;

				const factor = delta > 0 ? 1.025 : 0.975;
				const span = currentRange.to - currentRange.from;
				const newSpan = span * factor;
				const mid = (currentRange.from + currentRange.to) / 2;
				const from = mid - newSpan / 2;
				const to = mid + newSpan / 2;

				if (to > from) {
					priceScale.setVisibleRange?.({ from, to });
				}
			}
		};

		const container = containerRef;
		container.addEventListener('wheel', handleWheel, { capture: true, passive: false });

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
				const range = chartInstance.timeScale().getVisibleLogicalRange();
				checkAndExpandWhitespace(range);
			}
		});

		resizeObserver.observe(containerRef);

		return () => {
			container.removeEventListener('wheel', handleWheel, { capture: true });
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
			if (containerRef && containerRef.clientWidth > 0) {
				const widthBars = Math.ceil(containerRef.clientWidth / 4) + 100;
				if (widthBars > currentWhitespaceCount) {
					currentWhitespaceCount = widthBars;
				}
			}
			const whitespace = generateFutureWhitespace(newCandles, currentWhitespaceCount);
			seriesInstance.setData([...newCandles, ...whitespace]);

			if (newCandles.length > 0) {
				const visibleDays = 250;
				chartInstance?.timeScale()?.setVisibleLogicalRange({
					from: Math.max(0, newCandles.length - visibleDays),
					to: newCandles.length - 1
				});
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
				title: hideLabels ? '' : indicator.label
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
				title: hideLabels ? '' : indicator.label
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
				title: hideLabels ? '' : 'MACD Hist'
			});
			const macdLineColor = indicator.color || '#2962FF';
			const macdLine = chartInstance.addSeries(LineSeries, {
				priceScaleId: 'macd',
				color: macdLineColor,
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: hideLabels ? '' : 'MACD'
			});
			const signalLine = chartInstance.addSeries(LineSeries, {
				priceScaleId: 'macd',
				color: '#FF6D00',
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: !hideLabels,
				lastValueVisible: !hideLabels,
				title: hideLabels ? '' : 'Signal'
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
				title: hideLabels ? '' : indicator.label,
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
				lastValueVisible: !hideLabels,
				title: hideLabels ? '' : `${indicator.label} Upper`
			});
			const middle = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 1),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false,
				lastValueVisible: !hideLabels,
				title: hideLabels ? '' : indicator.label
			});
			const lower = chartInstance.addSeries(LineSeries, {
				color: hexToRgba(color, 0.5),
				lineWidth: 1,
				crosshairMarkerVisible: true,
				priceLineVisible: false,
				lastValueVisible: !hideLabels,
				title: hideLabels ? '' : `${indicator.label} Lower`
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
			title: hideLabels ? '' : indicator.label
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
		if (customPaneHeights && type in customPaneHeights) {
			const nextHeights = { ...customPaneHeights };
			delete nextHeights[type];
			customPaneHeights = Object.keys(nextHeights).length > 0 ? nextHeights : null;
		}
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

	export function clearWave(waveIdOrDegree?: string | WaveDegree) {
		elliottWavesPrimitive?.clearWave(waveIdOrDegree);
	}

	export function getSelectedWaveDegree(): WaveDegree | null {
		return elliottWavesPrimitive?.getSelectedDegree() ?? null;
	}

	export function setSelectedWaveDegree(degree: WaveDegree | null) {
		elliottWavesPrimitive?.setSelectedDegree(degree);
	}

	export function getSelectedWaveId(): string | null {
		return elliottWavesPrimitive?.getSelectedWaveId() ?? null;
	}

	export function setSelectedWaveId(waveId: string | null) {
		elliottWavesPrimitive?.setSelectedWaveId(waveId);
	}

	/** Current custom pane heights, or null when the default layout is active. */
	export function getPaneHeights(): PaneHeights | null {
		return customPaneHeights ? { ...customPaneHeights } : null;
	}

	/** Restore a persisted pane-height layout (no change callback fired). */
	export function setPaneHeights(heights: PaneHeights | null | undefined) {
		if (!heights || Object.keys(heights).length === 0) {
			customPaneHeights = null;
		} else {
			customPaneHeights = { ...heights };
		}
		updatePanes();
	}

	/** Clear custom pane heights and notify the owner so the change persists. */
	export function resetPaneHeights() {
		handleResetPaneHeights();
	}

	export function getAllWaves(): DegreeWaveCount[] {
		return elliottWavesPrimitive?.getAllWaves() ?? [];
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

	{#if paneBoundaries.length > 0}
		{#each paneBoundaries as boundary (boundary.key)}
			<button
				type="button"
				class="absolute right-0 left-0 z-10 flex -translate-y-1/2 cursor-row-resize items-center justify-center border-0 bg-transparent px-0 py-1.5"
				style="top: {boundary.fraction * 100}%"
				data-testid={`pane-resize-handle-${boundary.upperId}-${boundary.lowerId}`}
				aria-label={`Resize ${boundary.upperId} and ${boundary.lowerId} panes`}
				onpointerdown={(event) => handlePaneDragStart(event, boundary.upperId, boundary.lowerId)}
			>
				<span class="h-1 w-full rounded-full bg-border/70 transition-colors hover:bg-primary"
				></span>
			</button>
		{/each}
	{/if}

	{#if paneLayoutCustom}
		<button
			type="button"
			class="absolute top-2 right-24 z-20 rounded border bg-background/80 px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground"
			data-testid="reset-pane-heights"
			onclick={handleResetPaneHeights}
		>
			Reset pane sizes
		</button>
	{/if}
</div>

<svelte:window
	onpointermove={handlePaneDragMove}
	onpointerup={handlePaneDragEnd}
	onpointercancel={handlePaneDragEnd}
/>
