<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { setBrokerService } from '$lib/components/brokers/brokerService.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import { setContext } from 'svelte';
	import GlobalSearch from '$lib/components/global-search.svelte';

	let { children, data } = $props();

	setBrokerService();
	const watchlistService = setWatchlistService();

	$effect(() => {
		if (data.user) {
			watchlistService.loadWatchlists();
		}
	});

	setContext('toggleGlobalSearch', () => (globalSearchOpen = !globalSearchOpen));

	let globalSearchOpen = $state(false);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'p' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			globalSearchOpen = !globalSearchOpen;
		}
	}
</script>

<svelte:document onkeydown={handleKeydown} />

<svelte:head>
	<!-- <link rel="icon" href={favicon} /> -->
</svelte:head>

<ModeWatcher />

{@render children()}

<GlobalSearch bind:open={globalSearchOpen} />
