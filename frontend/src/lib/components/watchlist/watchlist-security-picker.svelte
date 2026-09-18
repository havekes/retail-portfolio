<script lang="ts">
	import * as Command from '@/components/ui/command';
	import type { MarketSearchResult } from '@/api/marketService';
	import { debounce } from '@/utils';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';

	let { watchlistId }: { watchlistId: string } = $props();

	const watchlistService = getWatchlistService();

	let query = $state('');
	let isSearching = $state(false);
	let searchError = $state<string | null>(null);
	let searchResults = $state<MarketSearchResult[]>([]);

	const search = debounce(async (value: string) => {
		const trimmed = value.trim();
		if (trimmed.length < 2) {
			searchResults = [];
			searchError = null;
			return;
		}

		isSearching = true;
		searchError = null;
		try {
			searchResults = await watchlistService.searchSecurities(trimmed);
		} catch (err) {
			searchResults = [];
			searchError = err instanceof Error ? err.message : 'Failed to search securities';
		} finally {
			isSearching = false;
		}
	}, 300);

	async function handleSelect(result: MarketSearchResult) {
		watchlistService.error = null;
		await watchlistService.addSecurity(watchlistId, result);
		if (!watchlistService.error) {
			query = '';
			searchResults = [];
		}
	}

	$effect(() => {
		search(query);
	});

	let groupedResults = $derived(
		searchResults.reduce(
			(groups, result) => {
				const type = result.security_type || 'other';
				if (!groups[type]) {
					groups[type] = [];
				}
				groups[type].push(result);
				return groups;
			},
			{} as Record<string, MarketSearchResult[]>
		)
	);
</script>

<div class="w-full max-w-md rounded-lg border">
	<Command.Root shouldFilter={false} label="Add securities">
		<Command.Input
			bind:value={query}
			aria-label="Search securities to add"
			placeholder="Search securities to add..."
		/>
		<Command.List>
			{#if isSearching}
				<Command.Loading class="px-2 py-6 text-center text-sm">Searching...</Command.Loading>
			{:else if searchError}
				<p role="alert" class="px-2 py-6 text-center text-sm text-destructive">{searchError}</p>
			{:else}
				{#if query.trim().length >= 2}
					<Command.Empty>No securities found.</Command.Empty>
				{/if}
				{#each Object.entries(groupedResults) as [type, results] (type)}
					<Command.Group heading={type}>
						{#each results as result (result.code + result.exchange)}
							<Command.Item
								value={result.code + '.' + result.exchange + ' ' + result.name}
								onSelect={() => handleSelect(result)}
								class="flex w-full items-center justify-between"
							>
								<span class="truncate">
									<strong>{result.code}.{result.exchange}</strong> - {result.name}
								</span>
							</Command.Item>
						{/each}
					</Command.Group>
				{/each}
			{/if}
		</Command.List>
	</Command.Root>
</div>
