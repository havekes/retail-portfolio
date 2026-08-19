<script lang="ts">
	import BrokersList from '@/components/brokers/brokers-list.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Connected brokers</title>
</svelte:head>

<BrokersList users={data.users}></BrokersList>
