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
		size?: 'xs' | 'sm' | 'md' | 'lg';
		class?: string;
	}

	let { securityId = null, symbol, size = 'md', class: className }: Props = $props();

	let hasError = $state(false);
	let isLoaded = $state(false);

	$effect(() => {
		// Reset image loading states when securityId changes
		void securityId;
		hasError = false;
		isLoaded = false;
	});

	const sizeMap = {
		xs: 'size-4 text-[9px]',
		sm: 'size-5 text-[10px]',
		md: 'size-6 text-xs',
		lg: 'size-8 text-sm'
	};

	const monogram = $derived(getMonogram(symbol));
</script>

<div
	data-testid="stock-logo"
	class={cn(
		'relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border border-border/50 bg-muted/60 text-muted-foreground select-none',
		sizeMap[size] ?? sizeMap.md,
		className
	)}
>
	{#if !hasError && securityId}
		<img
			src={`/api/v1/market/securities/${securityId}/logo`}
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
	{#if hasError || !isLoaded || !securityId}
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
