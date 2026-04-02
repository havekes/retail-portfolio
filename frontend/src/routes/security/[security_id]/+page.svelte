<script lang="ts">
	import AppSidebar from '@/components/app-sidebar.svelte';
	import { SidebarProvider } from '$lib/components/ui/sidebar/index.js';
	import { marketService } from '@/services/marketService';
	import { convertToHeikinAshi } from '$lib/utils/heikinAshi';
	import { getDateRange } from '$lib/utils/date';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import type { Candle } from '$lib/utils/heikinAshi';
	import PageHeader from '@/components/layout/page-header.svelte';
	import type { SecuritySchema } from '@/services/marketService';

	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let haCandles = $state<Candle[]>([]);
	let SecurityChart = $state<unknown | null>(null);
	let security = $state<SecuritySchema | null>(null);

	$effect(() => {
		(async () => {
			const { security_id } = page.params;

			if (!security_id) {
				error = 'Security ID is required';
				isLoading = false;
				return;
			}

			isLoading = true;
			error = null;
			security = null;

			try {
				const { from, to } = getDateRange(1000);

				// Fetch security details and price data in parallel
				const [securityData, priceResponse] = await Promise.all([
					marketService.getSecurity(security_id),
					marketService.getPrices(security_id, from, to)
				]);

				security = securityData;

				if (!priceResponse.prices || priceResponse.prices.length === 0) {
					error = 'No price data available for this security';
					isLoading = false;
					return;
				}

				const rawCandles: Candle[] = priceResponse.prices.map((p) => ({
					time: p.date,
					open: Number(p.open),
					high: Number(p.high),
					low: Number(p.low),
					close: Number(p.close)
				}));

				haCandles = convertToHeikinAshi(rawCandles);

				const module = await import('$lib/components/charts/security-chart.svelte');
				SecurityChart = module.default;
			} catch (err) {
				error = err instanceof Error ? err.message : 'Failed to load security data';
			} finally {
				isLoading = false;
			}
		})();
	});
</script>

<svelte:head>
	<title>{security ? `${security.symbol} - Security Chart` : 'Security Chart'}</title>
</svelte:head>

<SidebarProvider>
	<AppSidebar />
	<main class="flex h-screen w-full flex-col">
		<PageHeader
			title={security?.symbol ?? ''}
			subtitle={security?.name ?? ''}
			{isLoading}
			{error}
		/>

		{#if isLoading}
			<div class="flex flex-1 items-center justify-center">
				<p class="text-gray-500">Loading chart data...</p>
			</div>
		{:else if error}
			<div class="flex flex-1 items-center justify-center">
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
		{:else if SecurityChart}
			{@const ChartComponent =
				SecurityChart as typeof import('$lib/components/charts/security-chart.svelte').default}
			<div class="flex-1">
				<ChartComponent candles={haCandles} />
			</div>
		{/if}
	</main>
</SidebarProvider>
