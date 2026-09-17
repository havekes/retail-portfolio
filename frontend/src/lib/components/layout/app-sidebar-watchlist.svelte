<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { resolve } from '$app/paths';
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import type { SecuritySchema } from '$lib/api/marketService';
	import { cn } from '$lib/utils.js';

	let {
		showWatchlists = false,
		onToggleWatchlists = undefined
	}: {
		showWatchlists?: boolean;
		onToggleWatchlists?: (value: boolean) => void;
	} = $props();

	const sidebar = useSidebar();
	const watchlistService = getWatchlistService();
	const securities = $derived(watchlistService?.defaultWatchlistSecurities || []);
	const watchlists = $derived(watchlistService?.watchlists || []);

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

{#snippet watchlistToggle()}
	<Sidebar.GroupAction
		aria-label={showWatchlists ? 'Hide watchlists' : 'Show watchlists'}
		aria-pressed={showWatchlists}
		title={showWatchlists ? 'Hide watchlists' : 'Show watchlists'}
		onclick={() => onToggleWatchlists?.(!showWatchlists)}
	>
		{#if showWatchlists}
			<EyeOff class="h-4 w-4" />
		{:else}
			<Eye class="h-4 w-4" />
		{/if}
	</Sidebar.GroupAction>
{/snippet}

{#if showWatchlists}
	<Sidebar.Group>
		<Sidebar.GroupLabel>Watchlists</Sidebar.GroupLabel>
		{@render watchlistToggle()}
	</Sidebar.Group>
	{#each watchlists as watchlist (watchlist.id)}
		<Sidebar.Group>
			<Sidebar.GroupLabel class="overflow-hidden" title={watchlist.name}>
				<span class="block truncate">{watchlist.name}</span>
			</Sidebar.GroupLabel>
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
		</Sidebar.Group>
	{/each}
{:else}
	<Sidebar.Group>
		<Sidebar.GroupLabel>Watchlist</Sidebar.GroupLabel>
		{@render watchlistToggle()}
		<Sidebar.GroupContent>
			{#if securities.length > 0}
				<Sidebar.Menu>
					{#each securities as security (security.id)}
						{@render securityItem(security)}
					{/each}
				</Sidebar.Menu>
			{/if}
		</Sidebar.GroupContent>
	</Sidebar.Group>
{/if}
