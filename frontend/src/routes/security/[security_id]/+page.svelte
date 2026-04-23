<script lang="ts">
	import AppSidebar from '@/components/layout/app-sidebar.svelte';
	import { marketService } from '@/api/marketService';
	import { convertToHeikinAshi } from '@/utils/finance/candle';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import type { Candle } from '@/utils/finance/candle';
	import PageHeader from '@/components/layout/app-header.svelte';
	import type { SecuritySchema } from '@/api/marketService';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import IndicatorsGroup from '@/components/actions-sidebar/indicator/indicator-group.svelte';
	import PriceAlertsGroup from '@/components/actions-sidebar/price-alert/price-alert-group.svelte';
	import NotesGroup from '@/components/actions-sidebar/note/note-group.svelte';
	import DocumentsGroup from '@/components/actions-sidebar/document/document-group.svelte';
	import AIAnalysisGroup from '$lib/components/actions-sidebar/ai/ai-analysis-group.svelte';
	import type { IndicatorPreferences } from '$lib/api/indicatorsService';
	import { alertsService, type PriceAlert } from '$lib/api/alertsService';
	import { calculateSMA } from '@/utils/finance/moving-average';
	import { calculateRSI } from '@/utils/finance/rsi';
	import { calculateMACD } from '@/utils/finance/macd';
	import { calculateBollingerBands } from '@/utils/finance/bollinger-bands';
	import { calculateOBV } from '@/utils/finance/obv';
	import HoldingsGroup from '@/components/actions-sidebar/holding-group/holding-group.svelte';
	import { accountService, type AccountHoldingRead } from '@/api/accountService';

	let { data } = $props();

	let isLoading = $state(false);
	let error = $state<string | null>(null);

	let security = $state<SecuritySchema | null>(data.security);
	let haCandles = $state<Candle[]>([]);
	let securityChart = $state<unknown | null>(null);
	let chartRef = $state<any>(null);
	let alerts = $state<PriceAlert[]>([]);

	let indicatorConfigs = $state<Record<string, any>>({
		ma50: { label: '50 Day MA', color: '#3b82f6', period: 50 },
		ma200: { label: '200 Day MA', color: '#8b5cf6', period: 200 },
		ma50w: { label: '50 Week MA', color: '#10b981', period: 250 },
		ma200w: { label: '200 Week MA', color: '#f59e0b', period: 1000 },
		volume: { label: 'Volume', color: '#64748b', period: 0 },
		obv: { label: 'OBV', color: '#f59e0b', period: 0 },
		rsi: { label: 'RSI', color: '#06b6d4', period: 14 },
		macd: { label: 'MACD', color: '#ef4444', period: 0, fast: 12, slow: 26, signal: 9 },
		bb: { label: 'Bollinger Bands', color: '#8b5cf6', period: 20, stdDev: 2 },
		avgPrice: { label: 'Avg Price', color: '#f59e0b', period: 0, enabled: true }
	});

	let holdings = $state<AccountHoldingRead[]>([]);
	let averageBuyingPrice = $derived.by(() => {
		if (holdings.length === 0) return 0;
		const totalQuantity = holdings.reduce((sum, h) => sum + h.quantity, 0);
		if (totalQuantity === 0) return 0;
		const totalCost = holdings.reduce((sum, h) => sum + h.quantity * (h.average_cost ?? 0), 0);
		return totalCost / totalQuantity;
	});

	function onIndicatorConfigChange(indicatorId: string, newConfig: any) {
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
			alerts = await alertsService.getAlerts(security.id);
		} catch (err) {
			console.error('Failed to load alerts:', err);
		}
	}

	async function loadHoldings() {
		if (!security?.id) return;
		try {
			holdings = await accountService.getHoldings(security.id);
		} catch (err) {
			console.error('Failed to load holdings:', err);
		}
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

		let data;
		if (indicatorId === 'volume') {
			data = haCandles.map((c) => ({
				time: c.time,
				value: c.volume || 0,
				color: c.close >= c.open ? '#26a69a80' : '#ef535080' // Add some transparency
			}));
		} else if (indicatorId === 'obv') {
			data = calculateOBV(haCandles);
		} else if (indicatorId === 'rsi') {
			data = calculateRSI(haCandles, { period: config.period });
		} else if (indicatorId === 'macd') {
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			const mconfig = config as any;
			data = calculateMACD(haCandles, {
				fast: mconfig.fast,
				slow: mconfig.slow,
				signal: mconfig.signal
			});
		} else if (indicatorId === 'bb') {
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			const bconfig = config as any;
			data = calculateBollingerBands(haCandles, { period: bconfig.period, stdDev: bconfig.stdDev });
		} else {
			data = calculateSMA(haCandles, config.period);
		}

		chartRef.addIndicator({
			type: indicatorId,
			label: config.label,
			color: config.color,
			data: data
		});
	}

	function onPreferencesLoaded(prefs: IndicatorPreferences) {
		if (!prefs?.indicators) return;
		for (const [id, config] of Object.entries(prefs.indicators)) {
			if (config.enabled) {
				// setTimeout ensures chartRef is bound
				setTimeout(() => onIndicatorToggle(id, true), 100);
			}
		}
	}

	$effect(() => {
		(async () => {
			if (!data.prices || data.prices.length === 0) {
				error = 'No price data available for this security';
				return;
			}

			const rawCandles: Candle[] = data.prices.map((p) => ({
				time: p.date,
				open: Number(p.open),
				high: Number(p.high),
				low: Number(p.low),
				close: Number(p.close),
				volume: Number(p.volume)
			}));

			haCandles = convertToHeikinAshi(rawCandles);
			await Promise.all([loadAlerts(), loadHoldings()]);

			const module = await import('$lib/components/charts/security-chart.svelte');
			securityChart = module.default;
		})();
	});
</script>

<svelte:head>
	<title>{security ? `${security.symbol} - Security Chart` : 'Security Chart'}</title>
</svelte:head>

<Sidebar.Provider>
	<AppSidebar />
	<Sidebar.Inset class="flex h-screen">
		<div class="flex flex-1 flex-col overflow-hidden">
			<PageHeader
				title={security?.symbol ?? ''}
				subtitle={security?.name ?? ''}
				{isLoading}
				{error}
			/>

			{#if isLoading}
				<div class="flex flex-1 items-center justify-center overflow-hidden">
					<p class="text-gray-500">Loading chart data...</p>
				</div>
			{:else if error}
				<div class="flex flex-1 items-center justify-center overflow-hidden">
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
				<div class="flex flex-1 overflow-hidden">
					<div class="flex-1 overflow-hidden">
						<ChartComponent
							candles={haCandles}
							bind:this={chartRef}
							{alerts}
							onAddAlert={handleCreateAlert}
							onRemoveAlert={handleDeleteAlert}
							averagePrice={averageBuyingPrice}
							showAveragePrice={indicatorConfigs.avgPrice.enabled}
						/>
					</div>
					<div class="flex h-full w-64 flex-col border-l bg-sidebar text-sidebar-foreground">
						<Sidebar.Content class="overflow-y-auto">
							<HoldingsGroup securityId={security.id} expanded={true} />
							<IndicatorsGroup
								expanded={true}
								securityId={security.id}
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
	</Sidebar.Inset>
</Sidebar.Provider>
