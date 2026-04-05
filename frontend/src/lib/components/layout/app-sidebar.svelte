<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Kbd from '$lib/components/ui/kbd/index.js';
	import { goto } from '$app/navigation';
	import { userStore } from '@/stores/userStore';
	import type { User } from '@/types/user';
	import { getContext } from 'svelte';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import { resolve } from '$app/paths';
	import ChartCandlestick from '@lucide/svelte/icons/chart-candlestick';
	import Search from '@lucide/svelte/icons/search';

	let user: User | null = $state(null);
	userStore.subscribe((authState) => (user = authState.user));

	const toggleGlobalSearch = getContext<() => void>('toggleGlobalSearch');
</script>

<Sidebar.Root>
	<Sidebar.Header class="border-b py-2.5">
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
								{user?.email}
								<ChevronUp class="ms-auto" />
							</Sidebar.MenuButton>
						{/snippet}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content side="top" class="w-(--bits-dropdown-menu-anchor-width)">
						<DropdownMenu.Item onSelect={() => goto(resolve('/brokers'))}>
							Connected brokers
						</DropdownMenu.Item>
						<DropdownMenu.Item onSelect={() => goto(resolve('/auth/logout'))}>
							Sign out
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			</Sidebar.MenuItem>
		</Sidebar.Menu>
	</Sidebar.Footer>
</Sidebar.Root>
