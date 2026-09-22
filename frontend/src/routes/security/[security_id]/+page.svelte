<script lang="ts">
	import { untrack, onDestroy } from 'svelte';
	import type { Time, UTCTimestamp } from 'lightweight-charts';
	import { getMarketService } from '$lib/api/marketService';
	import { convertToHeikinAshi } from '@/utils/finance/candle';
	import { resolve } from '$app/paths';
	import type { Candle } from '@/utils/finance/candle';
	import PageHeader from '@/components/layout/app-header.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import IndicatorsGroup from '@/components/actions-sidebar/indicator/indicator-group.svelte';
	import PriceAlertsGroup from '@/components/actions-sidebar/price-alert/price-alert-group.svelte';
	import NotesGroup from '@/components/actions-sidebar/note/note-group.svelte';
	import DocumentsGroup from '@/components/actions-sidebar/document/document-group.svelte';
	import AIAnalysisGroup from '$lib/components/actions-sidebar/ai/ai-analysis-group.svelte';
	import type { UserPreferences } from '$lib/api/userPreferencesService';
	import { userPreferencesService, type ChartStyle } from '$lib/api/userPreferencesService';
	import { alertsService, type PriceAlert } from '$lib/api/alertsService';
	import { blendedAverageCost } from '@/utils/finance/average-cost';
	import HoldingsGroup from '@/components/actions-sidebar/holding-group/holding-group.svelte';
	import { accountService, type AccountHoldingRead } from '@/api/accountService';
	import type { IndicatorData } from '$lib/components/charts/security-chart.svelte';
	import Star from '@lucide/svelte/icons/star';
	import Settings from '@lucide/svelte/icons/settings';
	import CandlestickIcon from '$lib/components/icons/candlestick-icon.svelte';
	import HeikinAshiIcon from '$lib/components/icons/heikin-ashi-icon.svelte';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import {
		displayCandlesFor,
		shouldForceRefetch,
		parseCandleTime,
		mergeCandles,
		shouldFetchMoreData
	} from '$lib/chart-preferences';
	import {
		indicatorsService,
		type IndicatorSpec,
		type IndicatorCandle,
		type IndicatorComputeRequest
	} from '$lib/api/indicatorsService';
	import { createIndicatorConfigs, type IndicatorDefault } from '$lib/chart/indicator-defaults';
	import { getChartDateWindow } from '$lib/utils/date';
	import type { WaveSettings } from '$lib/utils/finance/elliott-wave';
	import { DEFAULT_WAVE_SETTINGS } from '$lib/utils/finance/elliott-wave';
	import { computeWaveAlertLevels, reconcileWaveAlerts } from '$lib/utils/finance/wave-alerts';
	import ChartSettingsModal from '$lib/components/charts/chart-settings-modal.svelte';
	import FibWidthModal from '$lib/components/charts/fib-width-modal.svelte';
	import DrawingToolbar from '$lib/components/charts/drawing-toolbar.svelte';
	import type { FibToolType } from '$lib/utils/finance/fibonacci';
	import type { SecurityDrawings } from '$lib/utils/finance/drawings';
	import RewindTimeline from '$lib/components/charts/rewind-timeline.svelte';
	import { sliceCandlesBefore } from '$lib/components/charts/rewind-timeline';
	import {
		setChartDrawingsService,
		ChartDrawingsService,
		type ChartInstance
	} from '$lib/services/ChartDrawingsService.svelte';
	import { redirectOn401 } from '$lib/api/async-data';
	import { SecurityPageDataService } from './page-data.svelte';

	let { data } = $props();

	const watchlistService = getWatchlistService();

	// The page owns its service instance (SSR "no global instances" rule) and owns
	// the post-navigation data wave: identity + `1d` series resolve after the shell
	// has already rendered.
	const pageData = new SecurityPageDataService();

	// Timeframe switches own their own failure message; the service owns the
	// initial load's. Both surface in the same "Failed to Load Chart" card.
	let timeframeError = $state<string | null>(null);
	const error = $derived(pageData.error ?? timeframeError);

	// Instant titlebar: shortcut navigation resolves the id from the already-loaded
	// default watchlist, so identity renders before the fetch lands. Direct loads
	// fall back to the app-header skeleton until the service resolves.
	const instantSecurity = $derived(
		watchlistService.defaultWatchlistSecurities.find((s) => s.id === data.security_id) ?? null
	);
	let security = $derived(pageData.security ?? instantSecurity);
	const isLoading = $derived(!security && !error);

	let haCandles = $state<Candle[]>([]);
	let selectedInterval = $state('1d');
	let chartStyle = $state<ChartStyle>('heikin_ashi');
	let rawCandles = $state<Candle[]>([]);
	let allDisplayCandles = $derived(displayCandlesFor(chartStyle, rawCandles, haCandles));
	let isChangingTimeframe = $state(false);
	let hasMoreData = $state(true);
	let isLoadingMore = $state(false);

	let userPreferences = $state<UserPreferences | null>(null);
	let isChartSettingsOpen = $state(false);
	let isFibWidthModalOpen = $state(false);
	let modalFibTool = $state<FibToolType>('retracement');

	const drawingsService = setChartDrawingsService(
		new ChartDrawingsService({
			securityId: untrack(() => security?.id),
			userPreferences: untrack(() => userPreferences),
			getChartRef: () => chartRef,
			onWaveAlertsReconcile: () => scheduleWaveAlertsReconcile(),
			onPreferencesChanged: (prefs: UserPreferences) => {
				userPreferences = prefs;
			},
			onChartSettingsOpen: () => {
				isChartSettingsOpen = true;
			}
		})
	);

	let isRewound = $derived(drawingsService.isRewound);
	let displayCandles = $derived(
		isRewound
			? sliceCandlesBefore(allDisplayCandles, drawingsService.timelinePosition)
			: allDisplayCandles
	);
	let timelineNow = $derived(
		allDisplayCandles.length > 0
			? parseCandleTime(allDisplayCandles[allDisplayCandles.length - 1].time)
			: new Date()
	);

	$effect(() => {
		drawingsService.setDisplayCandles(displayCandles);
	});

	$effect(() => {
		drawingsService.setSecurity(security?.id ?? null);
	});

	/**
	 * Accessor for the new-tool drawings currently in effect: the active rewind
	 * snapshot's drawings while rewound, otherwise the live per-security drawings
	 * from user preferences. Exposed for SECDTL-T04–T06 plugin consumption and tests.
	 */
	export function getEffectiveSecurityDrawings(): SecurityDrawings {
		return drawingsService.getEffectiveSecurityDrawings();
	}

	$effect(() => {
		void drawingsService.timelinePosition;
		untrack(() => {
			refreshActiveIndicators();
		});
	});

	onDestroy(() => {
		drawingsService.destroy();
	});

	async function updateChartPreferences(partial: Partial<UserPreferences>) {
		await userPreferencesService.patchPreferences(partial);
	}

	async function changeTimeframe(
		interval: string,
		{ persist = true, force = false }: { persist?: boolean; force?: boolean } = {}
	) {
		if (
			!security?.id ||
			isChangingTimeframe ||
			!shouldForceRefetch(selectedInterval, interval, force)
		)
			return;
		selectedInterval = interval;
		isChangingTimeframe = true;
		hasMoreData = true;
		isLoadingMore = false;

		let fetchOk = false;
		try {
			const isIntraday = interval === '1h' || interval === '4h';
			const { from, to } = getChartDateWindow(new Date(), interval);

			const marketService = getMarketService();
			const priceResponse = await marketService.getPrices(security.id, from, to, interval);

			if (!priceResponse.items || priceResponse.items.length === 0) {
				timeframeError = 'No price data available for this timeframe';
				return;
			}
			timeframeError = null;

			const mappedCandles: Candle[] = priceResponse.items.map((p) => {
				const timeVal =
					isIntraday && p.timestamp
						? (Math.floor(new Date(p.timestamp).getTime() / 1000) as UTCTimestamp)
						: ((p.date ?? '') as Time);
				return {
					time: timeVal,
					open: Number(p.open),
					high: Number(p.high),
					low: Number(p.low),
					close: Number(p.close),
					volume: Number(p.volume)
				};
			});

			mappedCandles.sort((a, b) => {
				if (typeof a.time === 'number' && typeof b.time === 'number') {
					return a.time - b.time;
				}
				return String(a.time).localeCompare(String(b.time));
			});

			rawCandles = mappedCandles;
			haCandles = convertToHeikinAshi(mappedCandles);

			refreshActiveIndicators();

			fetchOk = true;
		} catch (err) {
			console.error('Failed to change timeframe:', err);
		} finally {
			isChangingTimeframe = false;
		}

		// Persist outside the fetch try/catch so save failures don't obscure fetch errors
		// and isChangingTimeframe isn't held during the extra PUT.
		if (persist && fetchOk) {
			try {
				await updateChartPreferences({ timeframe: interval });
			} catch (err) {
				console.error('Failed to persist timeframe preference:', err);
			}
		}
	}

	async function handleLoadMoreData() {
		if (isRewound) return;
		const securityId = security?.id;
		if (
			!securityId ||
			!shouldFetchMoreData(isLoadingMore, hasMoreData, securityId, rawCandles.length)
		) {
			return;
		}

		isLoadingMore = true;
		try {
			const oldestCandle = rawCandles[0];
			const oldestDate = parseCandleTime(oldestCandle.time);
			const { from, to } = getChartDateWindow(oldestDate, selectedInterval);

			const marketService = getMarketService();
			const priceResponse = await marketService.getPrices(securityId, from, to, selectedInterval);

			if (!priceResponse.items || priceResponse.items.length === 0) {
				hasMoreData = false;
				return;
			}

			const isIntraday = selectedInterval === '1h' || selectedInterval === '4h';
			const mappedCandles: Candle[] = priceResponse.items.map((p) => {
				const timeVal =
					isIntraday && p.timestamp
						? (Math.floor(new Date(p.timestamp).getTime() / 1000) as UTCTimestamp)
						: ((p.date ?? '') as Time);
				return {
					time: timeVal,
					open: Number(p.open),
					high: Number(p.high),
					low: Number(p.low),
					close: Number(p.close),
					volume: Number(p.volume)
				};
			});

			mappedCandles.sort((a, b) => {
				if (typeof a.time === 'number' && typeof b.time === 'number') {
					return a.time - b.time;
				}
				return String(a.time).localeCompare(String(b.time));
			});

			const { merged, addedCount } = mergeCandles(rawCandles, mappedCandles);

			if (addedCount === 0) {
				hasMoreData = false;
				return;
			}

			rawCandles = merged;
			haCandles = convertToHeikinAshi(rawCandles);

			refreshActiveIndicators();
		} catch (err) {
			console.error('Failed to load more chart data:', err);
		} finally {
			isLoadingMore = false;
		}
	}
	let securityChart = $state<unknown | null>(null);
	let chartRef = $state<ChartInstance | null>(null);
	let alerts = $state<PriceAlert[]>([]);

	let indicatorConfigs = $state<Record<string, IndicatorDefault>>(createIndicatorConfigs());
	let sequenceCounter = 0;
	let activeRefreshSeq = 0;
	let indicatorSeq: Record<string, number> = {};
	let isLoadingIndicators = $state(false);

	let holdings = $state<AccountHoldingRead[]>([]);
	let averageBuyingPrice = $derived(blendedAverageCost(holdings));

	function buildIndicatorSpec(id: string, config: IndicatorDefault): IndicatorSpec {
		const spec: IndicatorSpec = {
			id,
			type: id,
			settings: config.settings
		};
		if (config.period != null && config.period > 0) {
			spec.period = config.period;
		}
		if (config.fast != null && config.fast > 0) {
			spec.fast = config.fast;
		}
		if (config.slow != null && config.slow > 0) {
			spec.slow = config.slow;
		}
		if (config.signal != null && config.signal > 0) {
			spec.signal = config.signal;
		}
		if (config.stdDev != null && config.stdDev > 0) {
			spec.stdDev = config.stdDev;
		}
		return spec;
	}

	function getRewoundCandlesPayload(): IndicatorCandle[] | undefined {
		if (!isRewound || !drawingsService.timelinePosition) {
			return undefined;
		}
		const sliced = sliceCandlesBefore(rawCandles, drawingsService.timelinePosition);
		return sliced.map((c) => ({
			time: c.time as number | string,
			open: c.open,
			high: c.high,
			low: c.low,
			close: c.close,
			volume: c.volume ?? 0
		}));
	}

	async function refreshActiveIndicators() {
		if (!chartRef || !security?.id) return;

		const seq = ++sequenceCounter;
		activeRefreshSeq = seq;

		// Synchronize all active technical indicators' indicatorSeq
		for (const [id, config] of Object.entries(indicatorConfigs)) {
			if (id === 'avgPrice') continue;
			if (config.enabled) {
				indicatorSeq[id] = seq;
			}
		}

		// Re-render volume locally if enabled
		if (indicatorConfigs.volume?.enabled) {
			const volData = displayCandles.map((c) => ({
				time: c.time,
				value: c.volume || 0,
				color: c.close >= c.open ? '#26a69a80' : '#ef535080'
			}));
			chartRef.removeIndicator('volume');
			chartRef.addIndicator({
				type: 'volume',
				label: indicatorConfigs.volume.label,
				color: indicatorConfigs.volume.color,
				data: volData as IndicatorData['data']
			});
		}

		// Collect all active technical indicator configs into an array of IndicatorSpec
		const activeSpecs: IndicatorSpec[] = [];
		for (const [id, config] of Object.entries(indicatorConfigs)) {
			if (id === 'avgPrice' || id === 'volume') continue;
			if (config.enabled) {
				activeSpecs.push(buildIndicatorSpec(id, config));
			}
		}

		if (activeSpecs.length === 0) {
			return;
		}

		const candlesPayload = getRewoundCandlesPayload();
		const request: IndicatorComputeRequest = {
			interval: selectedInterval,
			chart_style: chartStyle,
			indicators: activeSpecs,
			...(candlesPayload ? { candles: candlesPayload } : {})
		};

		isLoadingIndicators = true;
		try {
			const res = await indicatorsService.computeIndicators(security.id, request);
			if (seq !== activeRefreshSeq) return;
			if (!chartRef) return;

			for (const spec of activeSpecs) {
				const id = spec.id ?? spec.type;
				if (indicatorConfigs[id]?.enabled && indicatorSeq[id] === seq) {
					const seriesData = res.indicators[id] ?? res.indicators[spec.type] ?? [];
					chartRef.removeIndicator(id);
					chartRef.addIndicator({
						type: id,
						label: indicatorConfigs[id].label,
						color: indicatorConfigs[id].color,
						data: seriesData as IndicatorData['data']
					});
				}
			}
		} catch (err) {
			console.error('Failed to refresh indicators:', err);
		} finally {
			if (seq === activeRefreshSeq) {
				isLoadingIndicators = false;
			}
		}
	}

	function onIndicatorConfigChange(
		indicatorId: string,
		newConfig: Partial<IndicatorDefault>,
		reRender = true
	) {
		indicatorConfigs[indicatorId] = { ...indicatorConfigs[indicatorId], ...newConfig };
		// Handle avgPrice specifically since it's a prop not a generic indicator
		if (indicatorId === 'avgPrice') return;

		// Trigger an async refresh for enabled indicators if currently on chart
		if (chartRef && reRender && indicatorConfigs[indicatorId]?.enabled) {
			void onIndicatorToggle(indicatorId, true);
		}
	}

	async function loadAlerts() {
		if (!security?.id) return;
		try {
			const res = await alertsService.getAlerts(security.id);
			alerts = res.items;
		} catch (err) {
			console.error('Failed to load alerts:', err);
		}
	}

	async function loadHoldings() {
		if (!security?.id) return;
		try {
			const res = await accountService.getHoldings(security.id);
			holdings = res.items;
		} catch (err) {
			console.error('Failed to load holdings:', err);
		}
	}

	// Serialized reconcile chain — `onWaveChange` fires per point while drawing, and concurrent
	// reconciles reading stale `alerts` would double-create. Chaining onto a single promise keeps
	// every run sequential so each sees the previous run's applied state.
	let waveAlertsReconcileSeq: Promise<void> = Promise.resolve();

	function scheduleWaveAlertsReconcile() {
		if (isRewound) return waveAlertsReconcileSeq;
		waveAlertsReconcileSeq = waveAlertsReconcileSeq
			.then(() => reconcileWaveAlertsForSecurity())
			.catch(() => {});
		return waveAlertsReconcileSeq;
	}

	async function reconcileWaveAlertsForSecurity() {
		if (isRewound) return;
		if (!security?.id) return;
		const settings = userPreferences?.wave_settings ?? DEFAULT_WAVE_SETTINGS;
		const lastCandle = displayCandles[displayCandles.length - 1];
		const currentPrice = lastCandle?.close;
		const desired = computeWaveAlertLevels(
			settings,
			drawingsService.securityElliottWaves,
			currentPrice
		);
		const { toCreate, toDelete } = reconcileWaveAlerts(alerts, desired);
		try {
			await Promise.all(toDelete.map((alert) => alertsService.deleteAlert(security.id, alert.id)));
			await Promise.all(
				toCreate.map((level) =>
					alertsService.createAlert(security.id, {
						target_price: level.level,
						condition: level.condition,
						source: 'wave'
					})
				)
			);
			if (toDelete.length > 0 || toCreate.length > 0) {
				await loadAlerts();
			}
		} catch (err) {
			// Never break drawing on reconcile failure — self-heals via the next reconcile.
			console.error('Failed to reconcile wave target alerts:', err);
		}
	}

	async function handleChartHideLabelsChange(hideLabels: boolean) {
		userPreferences = {
			...(userPreferences ?? {}),
			chart_hide_labels: hideLabels
		};
		try {
			await userPreferencesService.patchPreferences({ chart_hide_labels: hideLabels });
		} catch (err) {
			console.error('Failed to persist chart hide labels preference:', err);
		}
	}

	async function handlePaneHeightsChange(heights: Record<string, number> | null) {
		// PATCH replaces the whole `indicator_pane_heights` key — always send the full object.
		userPreferences = {
			...(userPreferences ?? {}),
			indicator_pane_heights: heights
		};
		try {
			await userPreferencesService.patchPreferences({ indicator_pane_heights: heights });
		} catch (err) {
			console.error('Failed to persist indicator pane heights:', err);
		}
	}

	function applySavedPaneHeights(prefs: UserPreferences | null | undefined) {
		const heights = prefs?.indicator_pane_heights;
		if (!heights || Object.keys(heights).length === 0) return;
		// setTimeout ensures chartRef is bound before the restore call.
		setTimeout(() => chartRef?.setPaneHeights?.(heights), 100);
	}

	async function handleWaveSettingsChange(settings: WaveSettings) {
		userPreferences = {
			...(userPreferences ?? {}),
			wave_settings: settings
		};
		try {
			// PATCH replaces the whole key — always send the full object.
			await userPreferencesService.patchPreferences({ wave_settings: settings });
		} catch (err) {
			console.error('Failed to persist wave settings:', err);
		}
		scheduleWaveAlertsReconcile();
	}

	async function handleCreateAlert(price: number, condition: 'above' | 'below') {
		if (!security?.id) return;
		try {
			await alertsService.createAlert(security.id, { target_price: price, condition });
			await loadAlerts();
		} catch (err) {
			console.error('Failed to create alert:', err);
		}
	}

	async function handleDeleteAlert(alertId: number) {
		if (!security?.id) return;
		try {
			await alertsService.deleteAlert(security.id, alertId);
			await loadAlerts();
		} catch (err) {
			console.error('Failed to delete alert:', err);
		}
	}

	async function onIndicatorToggle(indicatorId: string, enabled: boolean) {
		if (indicatorId === 'avgPrice') {
			indicatorConfigs.avgPrice.enabled = enabled;
			return;
		}

		if (indicatorConfigs[indicatorId]) {
			indicatorConfigs[indicatorId].enabled = enabled;
		}

		if (!chartRef) return;

		if (!enabled) {
			chartRef.removeIndicator(indicatorId);
			indicatorSeq[indicatorId] = ++sequenceCounter;
			return;
		}

		if (indicatorId === 'volume') {
			const volData = displayCandles.map((c) => ({
				time: c.time,
				value: c.volume || 0,
				color: c.close >= c.open ? '#26a69a80' : '#ef535080'
			}));
			chartRef.removeIndicator('volume');
			chartRef.addIndicator({
				type: 'volume',
				label: indicatorConfigs.volume.label,
				color: indicatorConfigs.volume.color,
				data: volData as IndicatorData['data']
			});
			return;
		}

		const config = indicatorConfigs[indicatorId];
		if (!config || !security?.id) return;

		indicatorSeq[indicatorId] = ++sequenceCounter;
		const currentSeq = indicatorSeq[indicatorId];

		const spec = buildIndicatorSpec(indicatorId, config);
		const candlesPayload = getRewoundCandlesPayload();

		const request: IndicatorComputeRequest = {
			interval: selectedInterval,
			chart_style: chartStyle,
			indicators: [spec],
			...(candlesPayload ? { candles: candlesPayload } : {})
		};

		isLoadingIndicators = true;
		try {
			const res = await indicatorsService.computeIndicators(security.id, request);
			if (indicatorSeq[indicatorId] !== currentSeq) return;
			if (!indicatorConfigs[indicatorId]?.enabled) return;
			if (!chartRef) return;

			const seriesData = res.indicators[indicatorId] ?? res.indicators[spec.type] ?? [];
			chartRef.removeIndicator(indicatorId);
			chartRef.addIndicator({
				type: indicatorId,
				label: config.label,
				color: config.color,
				data: seriesData as IndicatorData['data']
			});
		} catch (err) {
			console.error(`Failed to compute indicator ${indicatorId}:`, err);
		} finally {
			if (indicatorSeq[indicatorId] === currentSeq) {
				isLoadingIndicators = false;
			}
		}
	}

	async function onPreferencesLoaded(prefs: UserPreferences) {
		userPreferences = prefs;
		applySavedPaneHeights(prefs);
		drawingsService.setPreferences(prefs);

		// (a) Apply chart style
		chartStyle = (prefs.chart_style as ChartStyle | undefined) ?? 'heikin_ashi';

		// (b) Apply saved timeframe — no persist on load
		if (prefs.timeframe && prefs.timeframe !== selectedInterval) {
			await changeTimeframe(prefs.timeframe, { persist: false });
		}

		// (c) Apply indicator preferences
		if (!prefs?.indicators) return;
		for (const [id, config] of Object.entries(prefs.indicators)) {
			if (id === 'avgPrice') {
				indicatorConfigs.avgPrice.enabled = config.enabled;
				if (config.enabled) {
					setTimeout(() => onIndicatorToggle(id, true), 100);
				}
			} else if (indicatorConfigs[id]) {
				indicatorConfigs[id].enabled = config.enabled;
				if (config.color) indicatorConfigs[id].color = config.color;
				if (config.settings) {
					const s = config.settings;
					if ('period' in s) indicatorConfigs[id].period = s.period as number;
					if ('stdDev' in s) indicatorConfigs[id].stdDev = s.stdDev as number;
					if ('fast' in s) indicatorConfigs[id].fast = s.fast as number;
					if ('slow' in s) indicatorConfigs[id].slow = s.slow as number;
					if ('signal' in s) indicatorConfigs[id].signal = s.signal as number;
				}
				if (config.enabled) {
					// setTimeout ensures chartRef is bound
					setTimeout(() => onIndicatorToggle(id, true), 100);
				}
			}
		}
	}

	// The route shell (titlebar + chart region) renders instantly; the security
	// identity and its `1d` price series are fetched after navigation. `$effect`
	// never runs during SSR, so this mount-time trigger is browser-only and fires
	// once per security — soft navigation re-runs it via `data.security_id`.
	$effect(() => {
		const securityId = data.security_id;

		untrack(() => {
			// Reset drawing mode and pagination state on route transition / security change.
			drawingsService.resetToolState();
			timeframeError = null;
			hasMoreData = true;
			isLoadingMore = false;
			securityChart = null;

			void (async () => {
				const loadError = await pageData.load(securityId);

				// A newer navigation superseded this load; its own effect run owns the init.
				if (data.security_id !== securityId) return;

				if (loadError !== null) {
					// 401s leave through the shared async-data seam; any other failure is
					// already surfaced by `pageData.error` in the "Failed to Load Chart" card.
					await redirectOn401(loadError);
					return;
				}

				const items = pageData.items;
				if (!items) return;

				try {
					if (!userPreferences) {
						try {
							const prefs = await userPreferencesService.getPreferences();
							userPreferences = prefs;
							applySavedPaneHeights(prefs);
							drawingsService.setPreferences(prefs);
						} catch (err) {
							console.error('Failed to load user preferences:', err);
						}
					} else {
						drawingsService.setPreferences(userPreferences);
					}

					// Convert to lightweight-charts format and sort properly (oldest to newest)
					const mappedCandles: Candle[] = items.map((p) => ({
						time: p.timestamp
							? (Math.floor(new Date(p.timestamp).getTime() / 1000) as UTCTimestamp)
							: ((p.date ?? '') as Time),
						open: Number(p.open),
						high: Number(p.high),
						low: Number(p.low),
						close: Number(p.close),
						volume: Number(p.volume)
					}));

					hasMoreData = true;
					isLoadingMore = false;
					rawCandles = mappedCandles;
					haCandles = convertToHeikinAshi(mappedCandles);
					await Promise.all([loadAlerts(), loadHoldings(), drawingsService.loadSnapshots()]);

					// Initial-load reconcile: gated on preferences being loaded so a failed fetch never
					// mass-deletes wave alerts. Soft navigation re-runs the effect per security.
					if (userPreferences !== null) {
						scheduleWaveAlertsReconcile();
					}

					const module = await import('$lib/components/charts/security-chart.svelte');
					securityChart = module.default;

					// Soft-navigation reconcile: the async load always fetches the '1d' series; if
					// we're on a different timeframe, force-refetch to keep the displayed series in
					// sync with the active timeframe for the new security. Gate on
					// !isChangingTimeframe to avoid a redundant refetch when a saved timeframe ≠ 1d
					// (onPreferencesLoaded is still running).
					if (!isChangingTimeframe && selectedInterval !== '1d') {
						await changeTimeframe(selectedInterval, { persist: false, force: true });
					}
				} catch (err) {
					// `load()` never throws; this keeps a failure in the init chain (dynamic
					// import, preferences, snapshots) from surfacing as an unhandled rejection.
					console.error('Failed to initialise security chart:', err);
				}
			})();
		});
	});
	function handleKeyDown(event: KeyboardEvent) {
		drawingsService.handleKeyDown(event, chartRef);
	}
</script>

<svelte:window onkeydown={handleKeyDown} />

<svelte:head>
	<title>{security ? `${security.symbol} - Security Chart` : 'Security Chart'}</title>
</svelte:head>

<div class="flex h-svh max-h-svh min-h-0 flex-1 flex-col overflow-hidden">
	<PageHeader {isLoading} {error}>
		{#snippet titleSlot()}
			<div class="flex items-center gap-2">
				<h2 class="text-lg font-semibold">{security?.symbol ?? ''}</h2>
				{#if security}
					{@const currentSecurity = security}
					<p class="text-sm text-muted-foreground">{currentSecurity.name}</p>
					<button
						type="button"
						onclick={() => watchlistService.toggleSecurity(currentSecurity.id)}
						class="rounded-sm p-1 hover:bg-muted focus:outline-hidden"
						aria-label="Toggle watchlist"
					>
						{#if watchlistService.hasSecurity(currentSecurity.id)}
							<Star class="h-4 w-4 fill-amber-400 stroke-amber-500" />
						{:else}
							<Star class="h-4 w-4 text-muted-foreground hover:text-amber-500" />
						{/if}
					</button>
				{/if}
			</div>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="flex min-h-0 flex-1 items-center justify-center overflow-hidden">
			<div
				class="card error-card w-full max-w-md rounded-lg border border-red-200 bg-white p-8 shadow-lg dark:border-red-800 dark:bg-gray-800"
			>
				<div class="text-center">
					<div class="mb-4 text-4xl">⚠️</div>
					<h2 class="mb-2 text-xl font-semibold text-gray-900 dark:text-gray-100">
						Failed to Load Chart
					</h2>
					<p class="mb-4 text-gray-600 dark:text-gray-400">{error}</p>
					<a
						href={resolve('/')}
						class="inline-block rounded-md bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700"
					>
						Back to Dashboard
					</a>
				</div>
			</div>
		</div>
	{:else if securityChart && security}
		{@const ChartComponent =
			securityChart as typeof import('$lib/components/charts/security-chart.svelte').default}
		<div class="flex min-h-0 flex-1 overflow-hidden">
			<div class="flex min-h-0 flex-1 flex-col overflow-hidden">
				<div
					class="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-sidebar/50 px-4 py-2"
				>
					<div class="flex items-center gap-1">
						{#each ['1h', '4h', '1d', '1w', '1m'] as tf (tf)}
							<button
								type="button"
								onclick={() => changeTimeframe(tf)}
								disabled={isChangingTimeframe}
								class="rounded px-2.5 py-1 text-xs font-medium transition-colors {selectedInterval ===
								tf
									? 'bg-primary text-primary-foreground shadow-sm'
									: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
							>
								{tf.toUpperCase()}
							</button>
						{/each}
						{#if isLoadingIndicators}
							<div
								class="ml-2 size-3 animate-spin rounded-full border-2 border-primary border-t-transparent"
								data-testid="loading-indicators-spinner"
								title="Loading indicators..."
							></div>
						{/if}
					</div>
					<Tooltip.Provider>
						<div class="flex items-center gap-1">
							<Tooltip.Root>
								<Tooltip.Trigger>
									{#snippet child({ props })}
										<button
											type="button"
											{...props}
											onclick={async () => {
												chartStyle = 'candlestick';
												refreshActiveIndicators();
												try {
													await updateChartPreferences({ chart_style: 'candlestick' });
												} catch (err) {
													console.error('Failed to persist chart style:', err);
												}
											}}
											disabled={isChangingTimeframe}
											class="rounded p-1.5 transition-colors {chartStyle === 'candlestick'
												? 'bg-primary text-primary-foreground shadow-sm'
												: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
											aria-label="Candlestick"
											title="Candlestick"
										>
											<CandlestickIcon class="h-4 w-4" />
										</button>
									{/snippet}
								</Tooltip.Trigger>
								<Tooltip.Content side="bottom">
									<p>Candlestick</p>
								</Tooltip.Content>
							</Tooltip.Root>
							<Tooltip.Root>
								<Tooltip.Trigger>
									{#snippet child({ props })}
										<button
											type="button"
											{...props}
											onclick={async () => {
												chartStyle = 'heikin_ashi';
												refreshActiveIndicators();
												try {
													await updateChartPreferences({ chart_style: 'heikin_ashi' });
												} catch (err) {
													console.error('Failed to persist chart style:', err);
												}
											}}
											disabled={isChangingTimeframe}
											class="rounded p-1.5 transition-colors {chartStyle === 'heikin_ashi'
												? 'bg-primary text-primary-foreground shadow-sm'
												: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
											aria-label="Heikin-Ashi"
											title="Heikin-Ashi"
										>
											<HeikinAshiIcon class="h-4 w-4" />
										</button>
									{/snippet}
								</Tooltip.Trigger>
								<Tooltip.Content side="bottom">
									<p>Heikin-Ashi</p>
								</Tooltip.Content>
							</Tooltip.Root>
							<Tooltip.Root>
								<Tooltip.Trigger>
									{#snippet child({ props })}
										<button
											type="button"
											{...props}
											onclick={() => (isChartSettingsOpen = true)}
											class="rounded p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
											aria-label="Open chart settings"
											title="Chart Settings (Ctrl+, / ⌘,)"
										>
											<Settings class="h-4 w-4" />
										</button>
									{/snippet}
								</Tooltip.Trigger>
								<Tooltip.Content side="bottom">
									<p>Chart Settings (Ctrl+, / ⌘,)</p>
								</Tooltip.Content>
							</Tooltip.Root>
						</div>
					</Tooltip.Provider>
				</div>
				<div class="flex min-h-0 flex-1 overflow-hidden">
					<DrawingToolbar service={drawingsService} />
					<div class="flex min-h-0 flex-1 flex-col">
						<div class="min-h-0 flex-1 overflow-hidden">
							<ChartComponent
								candles={displayCandles}
								bind:this={chartRef}
								hideLabels={Boolean(userPreferences?.chart_hide_labels)}
								{alerts}
								onAddAlert={handleCreateAlert}
								onRemoveAlert={handleDeleteAlert}
								averagePrice={averageBuyingPrice}
								showAveragePrice={indicatorConfigs.avgPrice.enabled}
								hasMoreData={!isRewound && hasMoreData}
								{isLoadingMore}
								onLoadMoreData={handleLoadMoreData}
								elliottWaves={drawingsService.effectiveElliottWaves}
								activeDegree={drawingsService.activeWaveDegree}
								activeWaveType={drawingsService.activeWaveType}
								isDrawingWave={drawingsService.isDrawingWaveEffective}
								bind:selectedWaveDegree={drawingsService.selectedWaveDegree}
								snapToWicks={userPreferences?.wave_settings?.snap_to_wicks ?? false}
								onWaveChange={drawingsService.handleWaveChange}
								onDrawingModeChange={drawingsService.setDrawingWaveMode}
								onDegreeChange={(degree) => (drawingsService.activeWaveDegree = degree)}
								onWaveTypeChange={(type) => (drawingsService.activeWaveType = type)}
								onWaveSelect={drawingsService.selectWave}
								fibonacciTools={drawingsService.effectiveFibonacciTools}
								activeFibTool={drawingsService.activeFibTool}
								isDrawingFib={drawingsService.isDrawingFibEffective}
								bind:selectedFibTool={drawingsService.selectedFibTool}
								onFibChange={drawingsService.handleFibChange}
								onFibDrawingModeChange={drawingsService.setDrawingFibMode}
								onFibToolChange={(tool) => {
									if (tool) drawingsService.activeFibTool = tool;
								}}
								onFibSelect={drawingsService.selectFib}
								onFibDoubleClick={(tool) => {
									modalFibTool = tool;
									isFibWidthModalOpen = true;
								}}
								securityDrawings={drawingsService.effectiveSecurityDrawings}
								isDrawingMeasure={drawingsService.isDrawingMeasureEffective}
								bind:selectedMeasureId={drawingsService.selectedMeasureId}
								onMeasureChange={drawingsService.handleMeasureChange}
								onMeasureDrawingModeChange={drawingsService.setDrawingMeasureMode}
								onMeasureSelect={drawingsService.selectMeasure}
								isDrawingHorizontalLine={drawingsService.isDrawingHorizontalLineEffective}
								bind:selectedHorizontalLineId={drawingsService.selectedHorizontalLineId}
								onHorizontalLineChange={drawingsService.handleHorizontalLineChange}
								onHorizontalLineDrawingModeChange={drawingsService.setDrawingHorizontalLineMode}
								onHorizontalLineSelect={drawingsService.selectHorizontalLine}
								isDrawingLine={drawingsService.isDrawingLineEffective}
								bind:selectedLineId={drawingsService.selectedLineId}
								onLineChange={drawingsService.handleLineChange}
								onLineDrawingModeChange={drawingsService.setDrawingLineMode}
								onLineSelect={drawingsService.selectLine}
								onDrawingDragStart={drawingsService.handleDrawingDragStart}
								onDrawingDragEnd={drawingsService.handleDrawingDragEnd}
								onPaneHeightsChange={handlePaneHeightsChange}
							/>
							<ChartSettingsModal
								bind:open={isChartSettingsOpen}
								chartHideLabels={Boolean(userPreferences?.chart_hide_labels)}
								onSaveChartHideLabels={handleChartHideLabelsChange}
								waveSettings={userPreferences?.wave_settings}
								onSaveWaveSettings={handleWaveSettingsChange}
								activeTool={drawingsService.activeFibTool}
								retracementLevels={drawingsService.effectiveFibonacciTools?.retracement?.levels}
								extensionLevels={drawingsService.effectiveFibonacciTools?.extension?.levels}
								retracementWidthMultiplier={drawingsService.effectiveFibonacciTools?.retracement
									?.widthMultiplier}
								extensionWidthMultiplier={drawingsService.effectiveFibonacciTools?.extension
									?.widthMultiplier}
								retracementExtendLines={drawingsService.effectiveFibonacciTools?.retracement
									?.extendLines}
								extensionExtendLines={drawingsService.effectiveFibonacciTools?.extension
									?.extendLines}
								hasActiveDrawing={Boolean(
									drawingsService.effectiveFibonacciTools?.retracement ||
									drawingsService.effectiveFibonacciTools?.extension
								)}
								onFibLevelsChange={drawingsService.handleFibLevelsChange}
								onFibWidthChange={drawingsService.handleFibWidthSave}
							/>
							<FibWidthModal
								bind:open={isFibWidthModalOpen}
								tool={modalFibTool}
								drawing={modalFibTool === 'retracement'
									? drawingsService.effectiveFibonacciTools?.retracement
									: drawingsService.effectiveFibonacciTools?.extension}
								onSave={drawingsService.handleFibWidthSave}
							/>
						</div>
						{#if drawingsService.isTimelineVisible}
							<RewindTimeline
								snapshots={drawingsService.snapshots}
								now={timelineNow}
								bind:position={drawingsService.timelinePosition}
							/>
						{/if}
					</div>
				</div>
			</div>
			<div class="flex h-full min-h-0 w-64 flex-col border-l bg-sidebar text-sidebar-foreground">
				<Sidebar.Content class="min-h-0 flex-1 overflow-y-auto">
					<HoldingsGroup securityId={security.id} {security} candles={rawCandles} expanded={true} />
					<IndicatorsGroup
						expanded={true}
						{indicatorConfigs}
						{onIndicatorToggle}
						{onPreferencesLoaded}
						{onIndicatorConfigChange}
					/>
					<PriceAlertsGroup {security} expanded={true} {alerts} />
					<NotesGroup securityId={security.id} expanded={true} />
					<DocumentsGroup securityId={security.id} expanded={true} />
					<AIAnalysisGroup securityId={security.id} expanded={true} />
				</Sidebar.Content>
			</div>
		</div>
	{:else}
		<div class="flex min-h-0 flex-1 items-center justify-center overflow-hidden">
			<p class="text-gray-500">Loading chart data...</p>
		</div>
	{/if}
</div>
