<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { userStore } from '$lib/stores/userStore';
	import type { User } from '$lib/types/user';
	import { resolve } from '$app/paths';
	import { setBrokerService } from '$lib/components/brokers/brokerService.svelte';
	import * as Command from '@/components/ui/command';
	import { debounce } from '@/utils';
	import { marketService } from '@/services/marketService';
	import { setContext } from 'svelte';
	import type { MarketSearchResult, SecurityCreateResponse } from '@/services/marketService';

	let { children } = $props();

	setBrokerService();

	let user: User | null = $state(null);
	userStore.subscribe((authState) => (user = authState.user));

	let searchResults = $state<MarketSearchResult[]>([]);
	let isSearching = $state(false);
	let searchError = $state<string | null>(null);
	let isCreatingSecurity = $state(false);
	let creationError = $state<string | null>(null);

	setContext('toggleGlobalSearch', () => (globalSearchOpen = !globalSearchOpen));

	const shouldRedirect = () => {
		const currentPath = page.url.pathname;
		return (
			!user &&
			currentPath !== '/auth/login' &&
			currentPath !== '/auth/signup' &&
			currentPath !== '/auth/signup/confirmation' &&
			currentPath !== '/auth/verify-email'
		);
	};

	$effect(() => {
		if (shouldRedirect()) {
			goto(resolve('/auth/login'));
		}
	});

	let globalSearchOpen = $state(false);
	let globalSearchValue = $state('');
	let pendingQuery = $state<string | null>(null);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'p' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			globalSearchOpen = !globalSearchOpen;
		}
	}

	$effect(() => {
		if (globalSearchValue.length === 0) {
			searchResults = [];
			pendingQuery = null;
			isSearching = false;
		} else if (globalSearchValue !== pendingQuery) {
			pendingQuery = globalSearchValue;
			search(globalSearchValue);
		}
	});

	const search = debounce(async (query: string) => {
		isSearching = true;
		searchError = null;
		console.log('Searching for:', query);
		try {
			const results = await marketService.search(query);
			console.log('Search results received:', results, 'type:', Array.isArray(results) ? 'array' : typeof results);
			// Only update results if this query is still pending
			if (pendingQuery === query) {
				const sliced = results.slice(0, 10);
				console.log('Setting searchResults to:', sliced, 'type:', Array.isArray(sliced) ? 'array' : typeof sliced);
				searchResults = sliced;
				console.log('searchResults after assignment:', searchResults, 'type:', Array.isArray(searchResults) ? 'array' : typeof searchResults);
			}
		} catch (error) {
			console.error('Search error:', error);
			if (pendingQuery === query) {
				searchError = error instanceof Error ? error.message : 'Search failed';
			}
		} finally {
			if (pendingQuery === query) {
				isSearching = false;
			}
		}
	}, 300);

	async function handleSelection(result: MarketSearchResult) {
		isCreatingSecurity = true;
		creationError = null;

		try {
			const response: SecurityCreateResponse = await marketService.createOrUpdateSecurity({
				code: result.code,
				exchange: result.exchange,
				name: result.name,
				currency: 'USD'
			});

			globalSearchOpen = false;
			await goto(resolve(`/security/${response.security_id}`));
		} catch (error) {
			creationError = error instanceof Error ? error.message : 'Failed to create security';
		} finally {
			isCreatingSecurity = false;
		}
	}
</script>

<svelte:document onkeydown={handleKeydown} />

<svelte:head>
	<!-- <link rel="icon" href={favicon} /> -->
</svelte:head>

<ModeWatcher />

{@render children()}

<Command.Dialog bind:open={globalSearchOpen}>
	<Command.Input bind:value={globalSearchValue} placeholder="Search for a symbol..." />
	<Command.List>
		<Command.Empty>No results found.</Command.Empty>
		{#if isSearching}
			<Command.Group heading="Symbols">
				<Command.Item>Searching...</Command.Item>
			</Command.Group>
		{:else if searchError}
			<Command.Group heading="Error">
				<Command.Item>{searchError}</Command.Item>
			</Command.Group>
		{:else if searchResults.length > 0}
			<Command.Group heading="Symbols">
				{#each searchResults as result (result.code + result.exchange)}
					<Command.Item onSelect={() => handleSelection(result)}>
						<span>
							<strong>{result.code}</strong> - {result.name}
						</span>
					</Command.Item>
				{/each}
			</Command.Group>
		{/if}
		{#if isCreatingSecurity}
			<Command.Group heading="Status">
				<Command.Item>Creating security...</Command.Item>
			</Command.Group>
		{/if}
		{#if creationError}
			<Command.Group heading="Error">
				<Command.Item>{creationError}</Command.Item>
			</Command.Group>
		{/if}
	</Command.List>
</Command.Dialog>
