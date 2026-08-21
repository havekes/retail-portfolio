<script lang="ts">
	import { untrack } from 'svelte';
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
	import { AVG_PRICE_LINE_COLOR } from '$lib/components/charts/colors';
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
		shouldFetchMoreData,
		computeIndicatorData
	} from '$lib/chart-preferences';
	import { getChartDateWindow } from '$lib/utils/date';
	import type {
		DegreeWaveCount,
		SecurityElliottWaves,
		WaveDegree,
		WaveSettings
	} from '$lib/utils/finance/elliott-wave';
	import {
		updateSecurityElliottWaves,
		DEFAULT_WAVE_SETTINGS
	} from '$lib/utils/finance/elliott-wave';
	import { computeWaveAlertLevels, reconcileWaveAlerts } from '$lib/utils/finance/wave-alerts';
	import ChartSettingsModal from '$lib/components/charts/chart-settings-modal.svelte';
	import DrawingToolbar from '$lib/components/charts/drawing-toolbar.svelte';
	import {
		type FibToolType,
		type FibLevelConfig,
		type SecurityFibonacciTools,
		updateSecurityFibonacciTools
	} from '$lib/utils/finance/fibonacci';

	let { data } = $props();

	const watchlistService = getWatchlistService();

	let isLoading = $state(false);
	let error = $state<string | null>(null);

	let security = $derived(data.security);
	let haCandles = $state<Candle[]>([]);
	let selectedInterval = $state('1d');
	let chartStyle = $state<ChartStyle>('heikin_ashi');
	let rawCandles = $state<Candle[]>([]);
	let displayCandles = $derived(displayCandlesFor(chartStyle, rawCandles, haCandles));
	let isChangingTimeframe = $state(false);
	let hasMoreData = $state(true);
	let isLoadingMore = $state(false);

	let userPreferences = $state<UserPreferences | null>(null);
	let activeWaveDegree = $state<WaveDegree>('cycle');
	let isDrawingWave = $state(false);
	let selectedWaveDegree = $state<WaveDegree | null>(null);
	let securityElliottWaves = $derived<SecurityElliottWaves>(
		(security?.id && userPreferences?.elliott_waves?.[security.id]) || {}
	);

	let activeFibTool = $state<FibToolType>('retracement');
	let isDrawingFib = $state(false);
	let isChartSettingsOpen = $state(false);
	let securityFibonacciTools = $derived<SecurityFibonacciTools>(
		(security?.id && userPreferences?.fibonacci_tools?.[security.id]) || {}
	);

	function handleKeyDown(event: KeyboardEvent) {
		const target = event.target as HTMLElement | null;
		if (
			target &&
			typeof target.closest === 'function' &&
			(target.tagName === 'INPUT' ||
				target.tagName === 'TEXTAREA' ||
				target.isContentEditable ||
				target.closest('input, textarea, [contenteditable="true"]'))
		) {
			return;
		}

		if (event.key === 'Delete' || event.key === 'Backspace') {
			if (selectedWaveDegree) {
				event.preventDefault();
				const degreeToClear = selectedWaveDegree;
				selectedWaveDegree = null;
				handleClearWave(degreeToClear);
			}
		} else if (event.key === 'Escape') {
			if (selectedWaveDegree) {
				selectedWaveDegree = null;
			}
			if (isDrawingWave) {
				isDrawingWave = false;
			}
			if (isDrawingFib) {
				isDrawingFib = false;
			}
		}
	}

	async function updateChartPreferences(partial: Partial<UserPreferences>) {
		await userPreferencesService.patchPreferences(partial);
	}

	async function handleWaveChange(degree: WaveDegree, waveCount: DegreeWaveCount | null) {
		if (!security?.id) return;
		const updatedAllWaves = updateSecurityElliottWaves(
			userPreferences?.elliott_waves,
			security.id,
			degree,
			waveCount
		);
		userPreferences = {
			...(userPreferences ?? {}),
			elliott_waves: updatedAllWaves
		};
		try {
			await userPreferencesService.patchPreferences({
				elliott_waves: updatedAllWaves
			});
		} catch (err) {
			console.error('Failed to persist elliott waves preference:', err);
		}
		scheduleWaveAlertsReconcile();
	}

	async function handleClearWave(degree: WaveDegree) {
		if (selectedWaveDegree === degree) {
			selectedWaveDegree = null;
		}
		await handleWaveChange(degree, null);
	}

	async function handleFibChange(drawings: SecurityFibonacciTools) {
		if (!security?.id) return;
		const updatedAllTools = updateSecurityFibonacciTools(
			userPreferences?.fibonacci_tools,
			security.id,
			drawings
		);
		userPreferences = {
			...(userPreferences ?? {}),
			fibonacci_tools: updatedAllTools
		};
		try {
			await userPreferencesService.patchPreferences({
				fibonacci_tools: updatedAllTools
			});
		} catch (err) {
			console.error('Failed to persist fibonacci tools preference:', err);
		}
	}

	async function handleFibLevelsChange(tool: FibToolType, levels: FibLevelConfig[]) {
		if (!security?.id) return;
		const currentTools = userPreferences?.fibonacci_tools?.[security.id];
		let updatedSecurityTools: SecurityFibonacciTools;
		if (tool === 'retracement') {
			const currentDrawing = currentTools?.retracement;
			updatedSecurityTools = {
				...currentTools,
				retracement: currentDrawing ? { ...currentDrawing, levels } : null
			};
		} else {
			const currentDrawing = currentTools?.extension;
			updatedSecurityTools = {
				...currentTools,
				extension: currentDrawing ? { ...currentDrawing, levels } : null
			};
		}
		const updatedAllTools = updateSecurityFibonacciTools(
			userPreferences?.fibonacci_tools,
			security.id,
			updatedSecurityTools
		);
		userPreferences = {
			...(userPreferences ?? {}),
			fibonacci_tools: updatedAllTools
		};
		try {
			await userPreferencesService.patchPreferences({
				fibonacci_tools: updatedAllTools
			});
		} catch (err) {
			console.error('Failed to persist fibonacci tools preference:', err);
		}
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
				error = 'No price data available for this timeframe';
				return;
			}
			error = null;

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
		if (!shouldFetchMoreData(isLoadingMore, hasMoreData, security?.id, rawCandles.length)) {
			return;
		}

		isLoadingMore = true;
		try {
			const oldestCandle = rawCandles[0];
			const oldestDate = parseCandleTime(oldestCandle.time);
			const { from, to } = getChartDateWindow(oldestDate, selectedInterval);

			const marketService = getMarketService();
			const priceResponse = await marketService.getPrices(security.id, from, to, selectedInterval);

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

	interface LocalIndicatorConfig {
		label: string;
		color: string;
		period: number;
		enabled: boolean;
		fast?: number;
		slow?: number;
		signal?: number;
		stdDev?: number;
		settings: Record<string, unknown>;
	}

	interface ChartInstance {
		addIndicator: (indicator: IndicatorData) => void;
		removeIndicator: (indicatorId: string) => void;
	}

	let chartRef = $state<ChartInstance | null>(null);
	let alerts = $state<PriceAlert[]>([]);

	let indicatorConfigs = $state<Record<string, LocalIndicatorConfig>>({
		ma50: { label: '50 Day MA', color: '#3b82f6', period: 50, enabled: false, settings: {} },
		ma200: { label: '200 Day MA', color: '#8b5cf6', period: 200, enabled: false, settings: {} },
		ma50w: { label: '50 Week MA', color: '#10b981', period: 50, enabled: false, settings: {} },
		ma200w: { label: '200 Week MA', color: '#f59e0b', period: 200, enabled: false, settings: {} },
		volume: { label: 'Volume', color: '#64748b', period: 0, enabled: false, settings: {} },
		obv: { label: 'OBV', color: '#f59e0b', period: 0, enabled: false, settings: {} },
		rsi: { label: 'RSI', color: '#06b6d4', period: 14, enabled: false, settings: {} },
		macd: {
			label: 'MACD',
			color: '#ef4444',
			period: 0,
			fast: 12,
			slow: 26,
			signal: 9,
			enabled: false,
			settings: {}
		},
		bb: {
			label: 'Bollinger Bands',
			color: '#8b5cf6',
			period: 20,
			stdDev: 2,
			enabled: false,
			settings: {}
		},
		avgPrice: {
			label: 'Avg Price',
			color: AVG_PRICE_LINE_COLOR,
			period: 0,
			enabled: true,
			settings: {}
		}
	});

	let holdings = $state<AccountHoldingRead[]>([]);
	let averageBuyingPrice = $derived(blendedAverageCost(holdings));

	function refreshActiveIndicators() {
		if (!chartRef) return;
		setTimeout(() => {
			if (!chartRef) return;
			for (const [id, config] of Object.entries(indicatorConfigs)) {
				if (config.enabled && id !== 'avgPrice') {
					chartRef.removeIndicator(id);
					onIndicatorToggle(id, true);
				}
			}
		}, 20);
	}

	function onIndicatorConfigChange(indicatorId: string, newConfig: Partial<LocalIndicatorConfig>) {
		indicatorConfigs[indicatorId] = { ...indicatorConfigs[indicatorId], ...newConfig };
		// Handle avgPrice specifically since it's a prop not a generic indicator
		if (indicatorId === 'avgPrice') return;

		// Trigger a re-render by removing and re-adding if it's currently on chart
		if (chartRef) {
			chartRef.removeIndicator(indicatorId);
			// setTimeout to give chartRef time to process removal before adding it back
			setTimeout(() => {
				onIndicatorToggle(indicatorId, true);
			}, 10);
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
		waveAlertsReconcileSeq = waveAlertsReconcileSeq
			.then(() => reconcileWaveAlertsForSecurity())
			.catch(() => {});
		return waveAlertsReconcileSeq;
	}

	async function reconcileWaveAlertsForSecurity() {
		if (!security?.id) return;
		const settings = userPreferences?.wave_settings ?? DEFAULT_WAVE_SETTINGS;
		const lastCandle = displayCandles[displayCandles.length - 1];
		const currentPrice = lastCandle?.close;
		const desired = computeWaveAlertLevels(settings, securityElliottWaves, currentPrice);
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

	function onIndicatorToggle(indicatorId: string, enabled: boolean) {
		if (indicatorId === 'avgPrice') {
			indicatorConfigs.avgPrice.enabled = enabled;
			return;
		}

		if (!chartRef) return;

		if (!enabled) {
			chartRef.removeIndicator(indicatorId);
			return;
		}

		const config = indicatorConfigs[indicatorId as keyof typeof indicatorConfigs];
		if (!config) return;

		const data = computeIndicatorData(indicatorId, config, displayCandles, selectedInterval);

		chartRef.addIndicator({
			type: indicatorId,
			label: config.label,
			color: config.color,
			data: data as IndicatorData['data']
		});
	}

	async function onPreferencesLoaded(prefs: UserPreferences) {
		userPreferences = prefs;

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

	$effect(() => {
		const items = data.items;
		void security?.id;

		if (!items || items.length === 0) {
			error = 'No price data available for this security';
			return;
		}

		untrack(() => {
			// Reset drawing mode on route transition / security change
			isDrawingWave = false;
			isDrawingFib = false;
			selectedWaveDegree = null;

			(async () => {
				if (!userPreferences) {
					try {
						const prefs = await userPreferencesService.getPreferences();
						userPreferences = prefs;
					} catch (err) {
						console.error('Failed to load user preferences:', err);
					}
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
				await Promise.all([loadAlerts(), loadHoldings()]);

				// Initial-load reconcile: gated on preferences being loaded so a failed fetch never
				// mass-deletes wave alerts. Soft navigation re-runs the effect per security.
				if (userPreferences !== null) {
					scheduleWaveAlertsReconcile();
				}

				const module = await import('$lib/components/charts/security-chart.svelte');
				securityChart = module.default;

				// Soft-navigation reconcile: server always loads '1d' series; if we're on a different
				// timeframe, force-refetch to keep the displayed series in sync with the active
				// timeframe for the new security. Gate on !isChangingTimeframe to avoid a
				// redundant refetch when a saved timeframe ≠ 1d (onPreferencesLoaded is still running).
				if (!isChangingTimeframe && selectedInterval !== '1d') {
					await changeTimeframe(selectedInterval, { persist: false, force: true });
				}
			})();
		});
	});
</script>

<svelte:window onkeydown={handleKeyDown} />

<svelte:head>
	<title>{security ? `${security.symbol} - Security Chart` : 'Security Chart'}</title>
</svelte:head>

<div class="flex h-svh max-h-svh min-h-0 flex-1 flex-col overflow-hidden">
	<PageHeader {isLoading} {error} subtitle={security?.name ?? ''}>
		{#snippet titleSlot()}
			<div class="flex items-center gap-2">
				<h2 class="text-lg font-semibold">{security?.symbol ?? ''}</h2>
				{#if security}
					{@const currentSecurity = security}
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

	{#if isLoading}
		<div class="flex min-h-0 flex-1 items-center justify-center overflow-hidden">
			<p class="text-gray-500">Loading chart data...</p>
		</div>
	{:else if error}
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
											title="Chart Settings"
										>
											<Settings class="h-4 w-4" />
										</button>
									{/snippet}
								</Tooltip.Trigger>
								<Tooltip.Content side="bottom">
									<p>Chart Settings</p>
								</Tooltip.Content>
							</Tooltip.Root>
						</div>
					</Tooltip.Provider>
				</div>
				<div class="flex min-h-0 flex-1 overflow-hidden">
					<DrawingToolbar
						{activeWaveDegree}
						{isDrawingWave}
						{activeFibTool}
						{isDrawingFib}
						onSelectWaveDegree={(degree) => {
							activeWaveDegree = degree;
							isDrawingWave = true;
							isDrawingFib = false;
						}}
						onToggleFib={(tool) => {
							if (isDrawingFib && activeFibTool === tool) {
								isDrawingFib = false;
							} else {
								activeFibTool = tool;
								isDrawingFib = true;
								isDrawingWave = false;
							}
						}}
					/>
					<div class="min-h-0 flex-1 overflow-hidden">
						<ChartComponent
							candles={displayCandles}
							bind:this={chartRef}
							{alerts}
							onAddAlert={handleCreateAlert}
							onRemoveAlert={handleDeleteAlert}
							averagePrice={averageBuyingPrice}
							showAveragePrice={indicatorConfigs.avgPrice.enabled}
							{hasMoreData}
							{isLoadingMore}
							onLoadMoreData={handleLoadMoreData}
							elliottWaves={securityElliottWaves}
							activeDegree={activeWaveDegree}
							{isDrawingWave}
							bind:selectedWaveDegree
							snapToWicks={userPreferences?.wave_settings?.snap_to_wicks ?? false}
							onWaveChange={handleWaveChange}
							onDrawingModeChange={(isDrawing) => {
								isDrawingWave = isDrawing;
								if (isDrawing) isDrawingFib = false;
							}}
							onDegreeChange={(degree) => (activeWaveDegree = degree)}
							onWaveSelect={(degree) => (selectedWaveDegree = degree)}
							fibonacciTools={securityFibonacciTools}
							{activeFibTool}
							{isDrawingFib}
							onFibChange={handleFibChange}
							onFibDrawingModeChange={(isDrawing) => {
								isDrawingFib = isDrawing;
								if (isDrawing) isDrawingWave = false;
							}}
							onFibToolChange={(tool) => {
								if (tool) activeFibTool = tool;
							}}
						/>
						<ChartSettingsModal
							bind:open={isChartSettingsOpen}
							waveSettings={userPreferences?.wave_settings}
							onSaveWaveSettings={handleWaveSettingsChange}
							activeTool={activeFibTool}
							retracementLevels={securityFibonacciTools?.retracement?.levels}
							extensionLevels={securityFibonacciTools?.extension?.levels}
							hasActiveDrawing={Boolean(
								securityFibonacciTools?.retracement || securityFibonacciTools?.extension
							)}
							onFibLevelsChange={handleFibLevelsChange}
						/>
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
	{/if}
</div>
