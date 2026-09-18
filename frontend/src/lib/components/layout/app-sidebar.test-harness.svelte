<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from './app-sidebar.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import type { SecuritySchema, WatchlistRead } from '$lib/api/marketService';
	import { setContext, untrack } from 'svelte';
	import { WATCHLIST_SIDEBAR_PREF, type WatchlistSidebarPref } from './watchlist-sidebar-pref.js';

	let {
		open = true,
		securities = [],
		watchlists = undefined,
		showWatchlists = false,
		onToggleGlobalSearch = undefined,
		onToggleWatchlists = undefined
	}: {
		open?: boolean;
		securities?: SecuritySchema[];
		watchlists?: WatchlistRead[];
		showWatchlists?: boolean;
		onToggleGlobalSearch?: () => void;
		onToggleWatchlists?: (value: boolean) => void;
	} = $props();

	setContext('toggleGlobalSearch', () => onToggleGlobalSearch?.());

	let show = $state(untrack(() => showWatchlists));

	function applyShow(value: boolean) {
		show = value;
		onToggleWatchlists?.(value);
	}

	setContext<WatchlistSidebarPref>(WATCHLIST_SIDEBAR_PREF, {
		get show() {
			return show;
		},
		setShow: applyShow
	});

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

<button onclick={() => applyShow(!show)}>Toggle harness watchlists</button>
