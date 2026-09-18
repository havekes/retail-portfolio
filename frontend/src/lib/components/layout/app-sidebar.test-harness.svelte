<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from './app-sidebar.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import type { SecuritySchema, WatchlistRead } from '$lib/api/marketService';
	import { setContext, untrack } from 'svelte';

	let {
		open = true,
		securities = [],
		watchlists = undefined,
		initialCollapsedWatchlistIds = undefined,
		onToggleGlobalSearch = undefined
	}: {
		open?: boolean;
		securities?: SecuritySchema[];
		watchlists?: WatchlistRead[];
		initialCollapsedWatchlistIds?: string[];
		onToggleGlobalSearch?: () => void;
	} = $props();

	setContext('toggleGlobalSearch', () => onToggleGlobalSearch?.());
	const initialCollapsed = untrack(() => initialCollapsedWatchlistIds);
	if (initialCollapsed !== undefined) {
		setContext('initialCollapsedWatchlistIds', initialCollapsed);
	}

	const watchlistService = setWatchlistService();
	watchlistService.watchlists = untrack(
		() =>
			watchlists ?? [
				{
					id: 'default-watchlist',
					user_id: 'u1',
					name: 'Default',
					securities
				}
			]
	);
</script>

<Sidebar.Provider {open}>
	<AppSidebar />
</Sidebar.Provider>
