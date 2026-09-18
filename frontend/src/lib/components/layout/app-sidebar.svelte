<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import ChevronLeft from '@lucide/svelte/icons/chevron-left';
	import ChevronRight from '@lucide/svelte/icons/chevron-right';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';
	import AppSidebarHeader from './app-sidebar-header.svelte';
	import AppSidebarActions from './app-sidebar-actions.svelte';
	import AppSidebarWatchlist from './app-sidebar-watchlist.svelte';
	import AppSidebarProfile from './app-sidebar-profile.svelte';

	const sidebar = useSidebar();
</script>

<Sidebar.Root collapsible="icon">
	<AppSidebarHeader />
	<Sidebar.Content>
		<AppSidebarActions />
		<AppSidebarWatchlist />
	</Sidebar.Content>
	<AppSidebarProfile />
	<Sidebar.Rail class="group/rail">
		<div
			class="pointer-events-none absolute top-1/2 left-1/2 z-50 flex h-6 w-6 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-sidebar-border bg-background text-foreground opacity-0 shadow-sm transition-all group-hover/rail:opacity-100 hover:scale-110"
		>
			{#if sidebar.state === 'expanded'}
				<ChevronLeft class="h-4 w-4" />
			{:else}
				<ChevronRight class="h-4 w-4" />
			{/if}
		</div>
	</Sidebar.Rail>
</Sidebar.Root>
