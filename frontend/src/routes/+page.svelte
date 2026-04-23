<script lang="ts">
	import AppSidebar from '@/components/layout/app-sidebar.svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AccountsList from '@/components/accounts/accounts-list.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Portfolio dashboard</title>
</svelte:head>

<Sidebar.Provider>
	<AppSidebar />
	<Sidebar.Inset>
		<AccountsList accounts={data.accounts}></AccountsList>
	</Sidebar.Inset>
</Sidebar.Provider>
