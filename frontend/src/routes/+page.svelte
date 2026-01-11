<script lang="ts">
	import AppSidebar from '@/components/app-sidebar.svelte';
	import { SidebarProvider } from '$lib/components/ui/sidebar/index.js';
	import AccountsList from '@/components/accounts/accounts-list.svelte';
</script>

<svelte:head>
	<title>Portfolio dashboard</title>
</svelte:head>

<SidebarProvider>
	<AppSidebar />
	<main class="w-full">
		<AccountsList></AccountsList>
	</main>
</SidebarProvider>
