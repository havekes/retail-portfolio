<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import * as Command from '@/components/ui/command';
	import { marketService } from '@/api/marketService';
	import type { MarketSearchResult } from '@/api/marketService';
	import { debounce } from '@/utils';

	let { open = $bindable(false) } = $props();

	let query = $state('');
	let isSearching = $state(false);
	let searchResults = $state<MarketSearchResult[]>([]);

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
						>
							<span>
								<strong>{result.code}.{result.exchange}</strong> - {result.name}
							</span>
						</Command.Item>
					{/each}
				</Command.Group>
			{/each}
		{/if}
	</Command.List>
</Command.Dialog>
