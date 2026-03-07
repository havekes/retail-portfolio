<script lang="ts">
	import AppSidebar from '@/components/app-sidebar.svelte';
	import { SidebarProvider } from '$lib/components/ui/sidebar/index.js';
	import BrokersList from '@/components/brokers/brokers-list.svelte';
</script>

<svelte:head>
	<title>Connected brokers</title>
</svelte:head>

<SidebarProvider>
	<AppSidebar />
	<main class="w-full">
		<BrokersList></BrokersList>
	</main>
</SidebarProvider>
