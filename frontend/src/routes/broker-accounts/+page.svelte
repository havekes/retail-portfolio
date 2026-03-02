<script lang="ts">
	import AppSidebar from '@/components/app-sidebar.svelte';
	import { SidebarProvider } from '$lib/components/ui/sidebar/index.js';
	import BrokerAccountsList from '@/components/broker-accounts/broker-accounts-list.svelte';
</script>

<svelte:head>
	<title>Connected broker accounts</title>
</svelte:head>

<SidebarProvider>
	<AppSidebar />
	<main class="w-full">
		<BrokerAccountsList></BrokerAccountsList>
	</main>
</SidebarProvider>
