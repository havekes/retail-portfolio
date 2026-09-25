<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Kbd from '$lib/components/ui/kbd/index.js';
	import Search from '@lucide/svelte/icons/search';
	import List from '@lucide/svelte/icons/list';
	import ChartPie from '@lucide/svelte/icons/chart-pie';
	import Briefcase from '@lucide/svelte/icons/briefcase';
	import { resolve } from '$app/paths';
	import { getContext } from 'svelte';

	const toggleGlobalSearch = getContext<() => void>('toggleGlobalSearch');
</script>

<Sidebar.Group>
	<Sidebar.Menu>
		<Sidebar.MenuItem>
			<Sidebar.MenuButton onclick={() => toggleGlobalSearch?.()} tooltipContent="Search (/)">
				<Search class="h-4 w-4 shrink-0" />
				<span class="text-base">Search</span>

				<Kbd.Group class="ml-auto group-data-[collapsible=icon]:hidden">
					<Kbd.Root>/</Kbd.Root>
				</Kbd.Group>
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
		<Sidebar.MenuItem>
			<Sidebar.MenuButton tooltipContent="Portfolios (p)">
				{#snippet child({ props })}
					<a href={resolve('/portfolios')} {...props}>
						<Briefcase class="h-4 w-4 shrink-0" />
						<span class="text-base">Portfolios</span>
						<Kbd.Group class="ml-auto group-data-[collapsible=icon]:hidden">
							<Kbd.Root>p</Kbd.Root>
						</Kbd.Group>
					</a>
				{/snippet}
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
		<Sidebar.MenuItem>
			<Sidebar.MenuButton tooltipContent="Watchlists (w)">
				{#snippet child({ props })}
					<a href={resolve('/watchlists')} {...props}>
						<List class="h-4 w-4 shrink-0" />
						<span class="truncate text-base">Watchlists</span>
						<Kbd.Group class="ml-auto group-data-[collapsible=icon]:hidden">
							<Kbd.Root>w</Kbd.Root>
						</Kbd.Group>
					</a>
				{/snippet}
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
		<Sidebar.MenuItem>
			<Sidebar.MenuButton tooltipContent="Holdings (h)">
				{#snippet child({ props })}
					<a href={resolve('/holdings')} {...props}>
						<ChartPie class="h-4 w-4 shrink-0" />
						<span class="text-base">Holdings</span>
						<Kbd.Group class="ml-auto group-data-[collapsible=icon]:hidden">
							<Kbd.Root>h</Kbd.Root>
						</Kbd.Group>
					</a>
				{/snippet}
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
	</Sidebar.Menu>
</Sidebar.Group>
