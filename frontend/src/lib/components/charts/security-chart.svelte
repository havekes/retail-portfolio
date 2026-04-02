<script lang="ts">
	import { CandlestickSeries, createChart } from 'lightweight-charts';
	import { onMount } from 'svelte';
	import type { Candle } from '$lib/utils/heikinAshi';

	let containerRef = $state<HTMLDivElement | null>(null);
	let chartInstance = $state<ReturnType<typeof createChart> | null>(null);
	let seriesInstance = $state<unknown | null>(null);

	const { candles = [], containerId = 'main-chart' } = $props<{
		candles?: Candle[];
		containerId?: string;
	}>();

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
			timeScale: {
				timeVisible: true,
				borderVisible: false
			}
		});

		seriesInstance = chartInstance.addSeries(CandlestickSeries, {
			upColor: '#26a69a',
			downColor: '#ef5350',
			borderVisible: false,
			wickUpColor: '#26a69a',
			wickDownColor: '#ef5350'
		});

		if (candles.length > 0) {
			// @ts-expect-error - seriesInstance type is inferred from addSeries
			seriesInstance.setData(candles);
			chartInstance.timeScale().fitContent();
		}

		const resizeObserver = new ResizeObserver(() => {
			if (containerRef && chartInstance) {
				chartInstance.applyOptions({
					width: containerRef.clientWidth,
					height: containerRef.clientHeight
				});
			}
		});

		resizeObserver.observe(containerRef);

		return () => {
			resizeObserver.disconnect();
			chartInstance?.remove();
		};
	});

	export function updateData(newCandles: Candle[]) {
		if (seriesInstance) {
			// @ts-expect-error - seriesInstance type is inferred from addSeries
			seriesInstance.setData(newCandles);
			chartInstance?.timeScale()?.fitContent();
		}
	}
</script>

<div bind:this={containerRef} id={containerId} class="h-full w-full"></div>
