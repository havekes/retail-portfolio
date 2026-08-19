<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { setBrokerService } from '$lib/components/brokers/brokerService.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import { setSidebarState } from '$lib/components/ui/sidebar/index.js';
	import { setContext } from 'svelte';
	import GlobalSearch from '$lib/components/global-search.svelte';

	let { children, data } = $props();

	setBrokerService();
	const watchlistService = setWatchlistService();
	setSidebarState(() => data.sidebar_open ?? true);

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
