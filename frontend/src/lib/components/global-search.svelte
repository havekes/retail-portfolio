<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import * as Command from '@/components/ui/command';
	import { marketService } from '@/api/marketService';
	import type { MarketSearchResult } from '@/api/marketService';
	import { debounce } from '@/utils';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import Star from '@lucide/svelte/icons/star';

	let { open = $bindable(false) } = $props();

	let query = $state('');
	let isSearching = $state(false);
	let searchResults = $state<MarketSearchResult[]>([]);

	const watchlistService = getWatchlistService();

	function getWatchlistSecurity(result: MarketSearchResult) {
		const defaultWatchlist = watchlistService?.watchlists?.find((w) => w.name === 'Default');
		if (!defaultWatchlist) return null;
		return defaultWatchlist.securities.find(
			(s) =>
				s.symbol.toLowerCase() === result.code.toLowerCase() &&
				s.exchange.toLowerCase() === result.exchange.toLowerCase()
		);
	}

	async function handleWatchlistToggle(e: MouseEvent, result: MarketSearchResult) {
		e.stopPropagation();
		e.preventDefault();

		const existing = getWatchlistSecurity(result);
		if (existing) {
			await watchlistService.toggleSecurity(existing.id);
		} else {
			try {
				const response = await marketService.createOrUpdateSecurity({
					code: result.code,
					exchange: result.exchange,
					name: result.name,
					currency: 'USD'
				});
				await watchlistService.toggleSecurity(response.security_id);
			} catch (error) {
				console.error('Failed to add security to watchlist:', error);
			}
		}
	}

	const search = debounce(async (query: string) => {
		if (query.length === 0) {
			searchResults = [];
			return;
		}

		isSearching = true;
		try {
			const results = await marketService.search(query);
			searchResults = results;
		} finally {
			isSearching = false;
		}
	}, 300);

	const onSelect = async (result: MarketSearchResult) => {
		try {
			const response = await marketService.createOrUpdateSecurity({
				code: result.code,
				exchange: result.exchange,
				name: result.name,
				currency: 'USD'
			});

			open = false;
			await goto(resolve(`/security/${response.security_id}`));
		} catch (error) {
			console.error('Failed to select security:', error);
		}
	};

	$effect(() => {
		search(query);
	});

	let groupedResults = $derived(
		searchResults.reduce(
			(groupedResults, result) => {
				const type = result.security_type || 'other';
				if (!groupedResults[type]) {
					groupedResults[type] = [];
				}
				groupedResults[type].push(result);
				return groupedResults;
			},
			{} as Record<string, MarketSearchResult[]>
		)
	);
</script>

<Command.Dialog bind:open shouldFilter={false} class="sm:max-h-f sm:max-w-xl">
	<Command.Input bind:value={query} placeholder="Search for a company or symbol..." />
	<Command.List>
		{#if isSearching}
			<Command.Loading class="px-2 py-6 text-center">Loading...</Command.Loading>
		{:else}
			<Command.Empty>No results found.</Command.Empty>
			{#each Object.entries(groupedResults) as [type, results] (type)}
				<Command.Group heading={type}>
					{#each results as result (result.code + result.exchange)}
						<Command.Item
							value={result.code + '.' + result.exchange + ' ' + result.name}
							onSelect={() => onSelect(result)}
							class="flex w-full items-center justify-between"
						>
							<span class="truncate">
								<strong>{result.code}.{result.exchange}</strong> - {result.name}
							</span>
							<button
								type="button"
								onclick={(e) => handleWatchlistToggle(e, result)}
								class="ml-2 shrink-0 rounded-sm p-1 hover:bg-muted focus:outline-hidden"
								aria-label="Toggle watchlist"
							>
								{#if getWatchlistSecurity(result)}
									<Star class="h-4 w-4 fill-amber-400 stroke-amber-500" />
								{:else}
									<Star class="h-4 w-4 text-muted-foreground hover:text-amber-500" />
								{/if}
							</button>
						</Command.Item>
					{/each}
				</Command.Group>
			{/each}
		{/if}
	</Command.List>
</Command.Dialog>
