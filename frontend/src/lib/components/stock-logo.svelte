<script lang="ts" module>
	/**
	 * Compute monogram initials for a ticker symbol (e.g. AAPL -> AA, TD.TO -> TD, C -> C).
	 */
	export function getMonogram(symbol: string): string {
		if (!symbol) return '';
		const base = symbol
			.split(/[.\-_/]/)[0]
			.trim()
			.toUpperCase();
		if (base.length === 0) return symbol.trim().slice(0, 2).toUpperCase();
		return base.slice(0, 2);
	}
</script>

<script lang="ts">
	import { cn } from '$lib/utils.js';

	interface Props {
		securityId?: string | null;
		symbol: string;
		exchange?: string | null;
		size?: 'xs' | 'sm' | 'md' | 'lg';
		class?: string;
	}

	let {
		securityId = null,
		symbol,
		exchange = null,
		size = 'md',
		class: className
	}: Props = $props();

	let hasError = $state(false);
	let isLoaded = $state(false);

	$effect(() => {
		// Reset image loading states when identifier changes
		void securityId;
		void symbol;
		void exchange;
		hasError = false;
		isLoaded = false;
	});

	const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

	const sizeMap = {
		xs: 'size-6 text-[10px]',
		sm: 'size-7 text-xs',
		md: 'size-8 text-xs font-bold',
		lg: 'size-10 text-sm font-bold'
	};

	const monogram = $derived(getMonogram(symbol));

	const logoSrc = $derived.by(() => {
		if (securityId) {
			return `${apiBaseUrl}/api/v1/market/securities/${securityId}/logo`;
		}
		if (symbol && symbol.trim()) {
			const encSymbol = encodeURIComponent(symbol.trim());
			const encExchange = exchange && exchange.trim() ? encodeURIComponent(exchange.trim()) : '';
			return `${apiBaseUrl}/api/v1/market/logo?symbol=${encSymbol}${encExchange ? `&exchange=${encExchange}` : ''}`;
		}
		return null;
	});
</script>

<div
	data-testid="stock-logo"
	class={cn(
		'relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-border/50 bg-muted/60 text-muted-foreground select-none',
		sizeMap[size] ?? sizeMap.md,
		className
	)}
>
	{#if !hasError && logoSrc}
		<img
			src={logoSrc}
			alt={`${symbol} logo`}
			class={cn('h-full w-full object-contain p-0.5', !isLoaded && 'invisible')}
			onload={() => {
				isLoaded = true;
			}}
			onerror={() => {
				hasError = true;
			}}
		/>
	{/if}
	{#if hasError || !isLoaded || !logoSrc}
		<span
			data-testid="stock-logo-fallback"
			class={cn(
				'flex h-full w-full items-center justify-center font-semibold tracking-wider uppercase',
				isLoaded && !hasError && 'hidden'
			)}
		>
			{monogram}
		</span>
	{/if}
</div>
