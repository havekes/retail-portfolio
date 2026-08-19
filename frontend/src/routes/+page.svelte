<script lang="ts">
	import AppSidebar from '@/components/layout/app-sidebar.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AccountsList from '@/components/accounts/accounts-list.svelte';
	import { getSidebarState } from '$lib/components/ui/sidebar/index.js';

	let { data } = $props();
	const sidebarState = getSidebarState();
</script>

<svelte:head>
	<title>Portfolio dashboard</title>
</svelte:head>

<Sidebar.Provider bind:open={sidebarState.open} onOpenChange={sidebarState.setOpen}>
	<AppSidebar />
	<Sidebar.Inset>
		<AccountsList accounts={data.accounts}></AccountsList>
	</Sidebar.Inset>
</Sidebar.Provider>
