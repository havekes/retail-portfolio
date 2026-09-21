<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import { userPreferencesService } from '$lib/api/userPreferencesService.js';
	import type { SecuritySchema } from '$lib/api/marketService';
	import { sortWatchlistsByOrder } from '$lib/components/watchlist/watchlist-utils';
	import { cn } from '$lib/utils.js';
	import { getContext } from 'svelte';
	import { SvelteSet } from 'svelte/reactivity';

	const sidebar = useSidebar();
	const watchlistService = getWatchlistService();

	const contextWatchlistOrder = getContext<string[] | undefined>('initialWatchlistOrder');
	const watchlistOrder = $derived(
		contextWatchlistOrder ?? ($page?.data?.watchlist_order as string[] | undefined) ?? null
	);
	const watchlists = $derived(
		sortWatchlistsByOrder(watchlistService?.watchlists || [], watchlistOrder)
	);
	const defaultWatchlistId = $derived(watchlistService?.defaultWatchlist?.id ?? null);

	const contextCollapsedIds = getContext<string[] | undefined>('initialCollapsedWatchlistIds');
	const initialIds =
		contextCollapsedIds ?? ($page?.data?.collapsed_watchlist_ids as string[] | undefined) ?? [];
	let collapsedIds = new SvelteSet<string>(initialIds);

	function toggleCollapsed(watchlistId: string) {
		if (collapsedIds.has(watchlistId)) {
			collapsedIds.delete(watchlistId);
		} else {
			collapsedIds.add(watchlistId);
		}
		userPreferencesService
			.patchPreferences({ collapsed_watchlist_ids: Array.from(collapsedIds) })
			.catch(console.error);
	}

	function getTickerFontSize(symbol: string): string {
		const len = symbol.length;
		if (len <= 2) {
			return 'text-xs';
		}
		if (len <= 4) {
			return 'text-[10px]';
		}
		return 'text-[8.5px]';
	}
</script>

{#snippet securityItem(security: SecuritySchema)}
	<Sidebar.MenuItem>
		<Sidebar.MenuButton
			class="group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:p-0! group-data-[collapsible=icon]:[&>span:last-child]:overflow-visible group-data-[collapsible=icon]:[&>span:last-child]:text-clip"
			tooltipContent={`${security.symbol} - ${security.name}`}
		>
			{#snippet child({ props })}
				<a href={resolve(`/security/${security.id}`)} {...props}>
					{#if sidebar.state === 'collapsed'}
						<span
							class={cn(
								'flex h-full w-full items-center justify-center overflow-visible text-center leading-none font-semibold tracking-tight whitespace-nowrap',
								getTickerFontSize(security.symbol)
							)}
						>
							{security.symbol}
						</span>
					{:else}
						<span>{security.symbol}</span>
						<span class="ml-1 truncate text-xs font-normal text-muted-foreground">
							{security.name}
						</span>
					{/if}
				</a>
			{/snippet}
		</Sidebar.MenuButton>
	</Sidebar.MenuItem>
{/snippet}

<Sidebar.Group class="group-data-[collapsible=icon]:hidden!">
	<Sidebar.GroupLabel>Watchlists</Sidebar.GroupLabel>
</Sidebar.Group>
{#each watchlists as watchlist (watchlist.id)}
	{@const isDefaultWatchlist = watchlist.id === defaultWatchlistId}
	<Sidebar.Group class={cn(!isDefaultWatchlist && 'group-data-[collapsible=icon]:hidden!')}>
		<Sidebar.GroupLabel
			class="h-auto! min-h-8 overflow-visible group-data-[collapsible=icon]:hidden!"
			title={watchlist.name}
		>
			<span class="block break-words whitespace-normal">
				{watchlist.name}
			</span>
		</Sidebar.GroupLabel>
		<Sidebar.GroupAction
			aria-label={`Toggle ${watchlist.name}`}
			title={`Toggle ${watchlist.name}`}
			onclick={() => toggleCollapsed(watchlist.id)}
		>
			{#if collapsedIds.has(watchlist.id)}
				<ChevronRight />
			{:else}
				<ChevronDown />
			{/if}
		</Sidebar.GroupAction>
		{#if !collapsedIds.has(watchlist.id)}
			<Sidebar.GroupContent>
				<Sidebar.Menu>
					{#each watchlist.securities as security (security.id)}
						{@render securityItem(security)}
					{:else}
						<Sidebar.MenuItem>
							<span
								class="flex h-8 items-center px-2 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden"
							>
								No securities
							</span>
						</Sidebar.MenuItem>
					{/each}
				</Sidebar.Menu>
			</Sidebar.GroupContent>
		{/if}
	</Sidebar.Group>
{/each}
