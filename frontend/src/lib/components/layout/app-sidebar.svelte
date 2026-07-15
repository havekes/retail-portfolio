<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Kbd from '$lib/components/ui/kbd/index.js';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { getContext } from 'svelte';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import CircleUser from '@lucide/svelte/icons/circle-user';
	import { resolve } from '$app/paths';
	import ChartCandlestick from '@lucide/svelte/icons/chart-candlestick';
	import Search from '@lucide/svelte/icons/search';
	import Star from '@lucide/svelte/icons/star';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';
	import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';

	const toggleGlobalSearch = getContext<() => void>('toggleGlobalSearch');
	const sidebar = useSidebar();
	const user = $derived($page.data.user);
	const watchlistService = getWatchlistService();
	const defaultWatchlist = $derived(
		watchlistService?.watchlists?.find((w) => w.name === 'Default')
	);
	const securities = $derived(defaultWatchlist?.securities || []);
</script>

<Sidebar.Root collapsible="icon">
	<Sidebar.Header class="border-b py-2">
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<Sidebar.MenuButton>
					{#snippet child({ props })}
						<a href={resolve('/')} {...props}>
							<ChartCandlestick />
							<span class="text-base font-semibold">Portfolio dashboard</span>
						</a>
					{/snippet}
				</Sidebar.MenuButton>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Header>
	<Sidebar.Content>
		<Sidebar.Group>
			<Sidebar.Menu>
				<Sidebar.MenuItem>
					<Sidebar.MenuButton>
						{#snippet child({ props })}
							<button onclick={() => toggleGlobalSearch?.()} {...props}>
								<Search class="h-4 w-4" />
								<span class="text-base">Search</span>

								<Kbd.Group class="ml-auto">
									<Kbd.Root>⌘</Kbd.Root>
									<Kbd.Root>P</Kbd.Root>
								</Kbd.Group>
							</button>
						{/snippet}
					</Sidebar.MenuButton>
				</Sidebar.MenuItem>
			</Sidebar.Menu>
		</Sidebar.Group>

		{#if securities.length > 0}
			<Sidebar.Group>
				<Sidebar.GroupLabel>Watchlist</Sidebar.GroupLabel>
				<Sidebar.GroupContent>
					<Sidebar.Menu>
						{#each securities as security (security.id)}
							<Sidebar.MenuItem>
								<Sidebar.MenuButton tooltipContent={`${security.symbol} - ${security.name}`}>
									{#snippet child({ props })}
										<a href={resolve(`/security/${security.id}`)} {...props}>
											<Star class="h-4 w-4 shrink-0 fill-amber-400 stroke-amber-500" />
											<span>{security.symbol}</span>
											<span class="ml-1 truncate text-xs font-normal text-muted-foreground"
												>{security.name}</span
											>
										</a>
									{/snippet}
								</Sidebar.MenuButton>
							</Sidebar.MenuItem>
						{/each}
					</Sidebar.Menu>
				</Sidebar.GroupContent>
			</Sidebar.Group>
		{/if}
	</Sidebar.Content>
	<Sidebar.Footer>
		<Sidebar.Menu>
			<Sidebar.MenuItem>
				<DropdownMenu.Root>
					<DropdownMenu.Trigger>
						{#snippet child({ props })}
							<Sidebar.MenuButton
								{...props}
								class="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
							>
								{#if sidebar.state === 'collapsed'}
									<CircleUser class="h-4 w-4" />
								{:else}
									{user?.email}
								{/if}
								<ChevronUp class="ms-auto" />
							</Sidebar.MenuButton>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content side="top" class="w-(--bits-dropdown-menu-anchor-width)">
						<DropdownMenu.Item onSelect={() => goto(resolve('/brokers'))}>
							Connected brokers
						</DropdownMenu.Item>
						<form method="POST" action={resolve('/auth/logout')}>
							<button type="submit" class="w-full">
								<DropdownMenu.Item>Sign out</DropdownMenu.Item>
							</button>
						</form>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Footer>
	<Sidebar.Rail class="group/rail">
		<div
			class="absolute top-1/2 left-1/2 z-50 flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-sidebar-border bg-background text-foreground opacity-0 shadow-sm transition-all group-hover/rail:opacity-100 hover:scale-110"
		>
			{#if sidebar.state === 'expanded'}
				<ChevronLeft class="h-4 w-4" />
			{:else}
				<ChevronRight class="h-4 w-4" />
			{/if}
		</div>
	</Sidebar.Rail>
</Sidebar.Root>
