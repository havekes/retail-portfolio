<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from './app-sidebar.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import type { WatchlistRead, WatchlistSecuritySchema } from '$lib/api/marketService';
	import { setContext, untrack } from 'svelte';

	let {
		open = true,
		securities = [],
		watchlists = undefined,
		initialCollapsedWatchlistIds = undefined,
		initialWatchlistOrder = undefined,
		onToggleGlobalSearch = undefined
	}: {
		open?: boolean;
		securities?: WatchlistSecuritySchema[];
		watchlists?: WatchlistRead[];
		initialCollapsedWatchlistIds?: string[];
		initialWatchlistOrder?: string[];
		onToggleGlobalSearch?: () => void;
	} = $props();

	setContext('toggleGlobalSearch', () => onToggleGlobalSearch?.());
	const initialCollapsed = untrack(() => initialCollapsedWatchlistIds);
	if (initialCollapsed !== undefined) {
		setContext('initialCollapsedWatchlistIds', initialCollapsed);
	}
	const initialOrder = untrack(() => initialWatchlistOrder);
	if (initialOrder !== undefined) {
		setContext('initialWatchlistOrder', initialOrder);
	}

	const watchlistService = setWatchlistService();
	watchlistService.watchlists = untrack(
		() =>
			watchlists ?? [
				{
					id: 'default-watchlist',
					user_id: 'u1',
					name: 'Default',
					sort: 'custom',
					securities
				}
			]
	);
</script>

<Sidebar.Provider {open}>
	<AppSidebar />
</Sidebar.Provider>
