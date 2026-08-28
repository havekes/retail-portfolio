<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { resolve } from '$app/paths';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
	import { cn } from '$lib/utils.js';

	const sidebar = useSidebar();
	const watchlistService = getWatchlistService();
	const securities = $derived(watchlistService?.defaultWatchlistSecurities || []);

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

{#if securities.length > 0}
	<Sidebar.Group>
		<Sidebar.GroupLabel>Watchlist</Sidebar.GroupLabel>
		<Sidebar.GroupContent>
			<Sidebar.Menu>
				{#each securities as security (security.id)}
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
				{/each}
			</Sidebar.Menu>
		</Sidebar.GroupContent>
	</Sidebar.Group>
{/if}
