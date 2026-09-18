<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { setBrokerService } from '$lib/components/brokers/brokerService.svelte';
	import { setSecurityService } from '$lib/components/security/securityService.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from '$lib/components/layout/app-sidebar.svelte';
	import { setContext, untrack } from 'svelte';
	import GlobalSearch from '$lib/components/global-search.svelte';
	import { userPreferencesService } from '$lib/api/userPreferencesService.js';
	import { Toaster } from '$lib/components/ui/toast/index.js';
	import type { WatchlistRead } from '$lib/api/marketService';

	let { children, data } = $props();

	setBrokerService();
	setSecurityService();
	const watchlistService = setWatchlistService();

	let sidebarOpen = $state(untrack(() => data.sidebar_open ?? true));

	function handleSidebarOpenChange(open: boolean) {
		if (data.user) {
			userPreferencesService.patchPreferences({ sidebar_open: open }).catch(console.error);
		}
	}

	$effect(() => {
		if (data.user) {
			watchlistService.loadWatchlists();
		}
	});

	let globalSearchOpen = $state(false);
	let globalSearchTargetWatchlist = $state<WatchlistRead | null>(null);

	setContext('toggleGlobalSearch', () => (globalSearchOpen = !globalSearchOpen));
	setContext('openGlobalSearch', (watchlist?: WatchlistRead | null) => {
		globalSearchTargetWatchlist = watchlist ?? null;
		globalSearchOpen = true;
	});

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

{#if data.user}
	<Sidebar.Provider
		class="overflow-hidden"
		bind:open={sidebarOpen}
		onOpenChange={handleSidebarOpenChange}
	>
		<AppSidebar />
		<Sidebar.Inset>
			{@render children()}
		</Sidebar.Inset>
	</Sidebar.Provider>
{:else}
	{@render children()}
{/if}

<GlobalSearch bind:open={globalSearchOpen} bind:targetWatchlist={globalSearchTargetWatchlist} />
<Toaster />
