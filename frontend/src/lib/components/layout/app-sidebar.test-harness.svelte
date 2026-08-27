<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from './app-sidebar.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import type { SecuritySchema } from '$lib/api/marketService';

	import { untrack } from 'svelte';

	let {
		open = true,
		securities = []
	}: {
		open?: boolean;
		securities?: SecuritySchema[];
	} = $props();

	const watchlistService = setWatchlistService();
	watchlistService.defaultWatchlistSecurities = untrack(() => securities);
</script>

<Sidebar.Provider {open}>
	<AppSidebar />
</Sidebar.Provider>
