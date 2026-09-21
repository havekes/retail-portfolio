<script lang="ts">
	import '../app.css';
	import { ModeWatcher } from 'mode-watcher';
	import { setBrokerService } from '$lib/components/brokers/brokerService.svelte';
	import { setSecurityService } from '$lib/components/security/securityService.svelte';
	import { setWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from '$lib/components/layout/app-sidebar.svelte';
	import { setContext, untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
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

	function isTypingTarget(target: EventTarget | null): boolean {
		if (!(target instanceof HTMLElement)) return false;
		return (
			target.tagName === 'INPUT' ||
			target.tagName === 'TEXTAREA' ||
			target.tagName === 'SELECT' ||
			target.isContentEditable
		);
	}

	function handleKeydown(e: KeyboardEvent) {
		// Sidebar shortcuts are single, modifier-free keys: ignore combos and typing.
		if (e.metaKey || e.ctrlKey || e.altKey) return;
		if (isTypingTarget(e.target)) return;

		if (e.key === '/') {
			e.preventDefault();
			globalSearchOpen = !globalSearchOpen;
			return;
		}

		if (e.key === 'w' || e.key === 'W') {
			e.preventDefault();
			void goto(resolve('/watchlists'));
			return;
		}

		if (e.key === 'h' || e.key === 'H') {
			e.preventDefault();
			void goto(resolve('/holdings'));
			return;
		}

		if (e.key >= '0' && e.key <= '9') {
			// 1-9 map to the first nine tickers, 0 to the tenth.
			const index = e.key === '0' ? 9 : Number(e.key) - 1;
			const security = watchlistService.defaultWatchlistSecurities[index];
			if (security) {
				e.preventDefault();
				void goto(resolve(`/security/${security.id}`));
			}
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
