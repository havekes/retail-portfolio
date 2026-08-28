<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import ChevronUp from '@lucide/svelte/icons/chevron-up';
	import CircleUser from '@lucide/svelte/icons/circle-user';
	import { resolve } from '$app/paths';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';

	const sidebar = useSidebar();
	const user = $derived($page.data.user);
</script>

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
								<span class="truncate">{user?.email}</span>
							{/if}
							<ChevronUp class="ms-auto" />
						</Sidebar.MenuButton>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content side="top" class="w-[var(--bits-dropdown-menu-anchor-width)]">
					<DropdownMenu.Item onSelect={() => goto(resolve('/brokers'))}>
						Connected brokers
					</DropdownMenu.Item>
					<DropdownMenu.Item onSelect={() => goto(resolve('/settings/security'))}>
						Security settings
					</DropdownMenu.Item>
					<form method="POST" action={resolve('/auth/logout')}>
						<button type="submit" class="w-full text-left">
							<DropdownMenu.Item>Sign out</DropdownMenu.Item>
						</button>
					</form>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</Sidebar.MenuItem>
	</Sidebar.Menu>
</Sidebar.Footer>
