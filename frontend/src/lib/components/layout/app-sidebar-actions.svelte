<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Kbd from '$lib/components/ui/kbd/index.js';
	import Search from '@lucide/svelte/icons/search';
	import { getContext } from 'svelte';

	const toggleGlobalSearch = getContext<() => void>('toggleGlobalSearch');
</script>

<Sidebar.Group>
	<Sidebar.Menu>
		<Sidebar.MenuItem>
			<Sidebar.MenuButton onclick={() => toggleGlobalSearch?.()} tooltipContent="Search (⌘P)">
				<Search class="h-4 w-4 shrink-0" />
				<span class="text-base">Search</span>

				<Kbd.Group class="ml-auto">
					<Kbd.Root>⌘</Kbd.Root>
					<Kbd.Root>P</Kbd.Root>
				</Kbd.Group>
			</Sidebar.MenuButton>
		</Sidebar.MenuItem>
	</Sidebar.Menu>
</Sidebar.Group>
