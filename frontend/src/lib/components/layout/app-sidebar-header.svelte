<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { resolve } from '$app/paths';
	import ChartCandlestick from '@lucide/svelte/icons/chart-candlestick';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';

	const sidebar = useSidebar();
</script>

<Sidebar.Header class="border-b py-2">
	{#if sidebar.state === 'collapsed'}
		<div class="flex items-center justify-center">
			<Sidebar.Trigger title="Toggle sidebar" />
		</div>
	{:else}
		<div class="flex items-center justify-between gap-1">
			<Sidebar.Menu class="min-w-0 flex-1">
				<Sidebar.MenuItem>
					<Sidebar.MenuButton>
						{#snippet child({ props })}
							<a href={resolve('/')} {...props}>
								<ChartCandlestick class="size-4 shrink-0" />
								<span class="truncate text-base font-semibold">Portfolio dashboard</span>
							</a>
						{/snippet}
					</Sidebar.MenuButton>
				</Sidebar.MenuItem>
			</Sidebar.Menu>
			<Sidebar.Trigger title="Toggle sidebar" class="shrink-0" />
		</div>
	{/if}
</Sidebar.Header>
