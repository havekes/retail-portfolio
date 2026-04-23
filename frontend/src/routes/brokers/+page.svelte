<script lang="ts">
	import AppSidebar from '@/components/layout/app-sidebar.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import BrokersList from '@/components/brokers/brokers-list.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Connected brokers</title>
</svelte:head>

<Sidebar.Provider>
	<AppSidebar />
	<Sidebar.Inset>
		<BrokersList users={data.users}></BrokersList>
	</Sidebar.Inset>
</Sidebar.Provider>
