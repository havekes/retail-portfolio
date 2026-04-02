<script lang="ts">
	import AppSidebar from '@/components/app-sidebar.svelte';
	import { SidebarProvider } from '$lib/components/ui/sidebar/index.js';

	import { CandlestickSeries, createChart } from 'lightweight-charts';
	import { onMount } from 'svelte';
	import { marketService } from '@/services/marketService';
	import { convertToHeikinAshi } from '$lib/utils/heikinAshi';
	import { getDateRange } from '$lib/utils/date';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import type { Candle } from '$lib/utils/heikinAshi';

	let isLoading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		const { security_id } = page.params;

		if (!security_id) {
			error = 'Security ID is required';
			isLoading = false;
			return;
		}

		try {
			const { from, to } = getDateRange(30);

			const response = await marketService.getPrices(security_id, from, to);

			if (!response.prices || response.prices.length === 0) {
				error = 'No price data available for this security';
				isLoading = false;
				return;
			}

			const rawCandles: Candle[] = response.prices.map((p) => ({
				time: p.date,
				open: Number(p.open),
				high: Number(p.high),
				low: Number(p.low),
				close: Number(p.close)
			}));

			const haCandles = convertToHeikinAshi(rawCandles);

			// Show the chart container
			const chartContainer = document.getElementById('main-chart');
			if (chartContainer) {
				chartContainer.classList.remove('hidden');
			}

			// Create chart
			const chart = createChart('main-chart');

			const candlestickSeries = chart.addSeries(CandlestickSeries, {
				upColor: '#26a69a',
				downColor: '#ef5350',
				borderVisible: false,
				wickUpColor: '#26a69a',
				wickDownColor: '#ef5350'
			});

			candlestickSeries.setData(haCandles);
			chart.timeScale().fitContent();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load security data';
		} finally {
			isLoading = false;
		}
	});
</script>

<svelte:head>
	<title>Security Chart</title>
</svelte:head>

<SidebarProvider>
	<AppSidebar />
	<main class="relative h-screen w-full">
		<div id="main-chart" class="hidden h-full w-full"></div>
		{#if isLoading}
			<div class="flex h-full items-center justify-center">
				<p class="text-gray-500">Loading...</p>
			</div>
		{:else if error}
			<div class="flex h-full items-center justify-center">
				<div
					class="card error-card w-full max-w-md rounded-lg border border-red-200 bg-white p-8 shadow-lg dark:border-red-800 dark:bg-gray-800"
				>
					<div class="text-center">
						<div class="mb-4 text-4xl">⚠️</div>
						<h2 class="mb-2 text-xl font-semibold text-gray-900 dark:text-gray-100">
							Security Not Found
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
		{/if}
	</main>
</SidebarProvider>
