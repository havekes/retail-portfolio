<script lang="ts">
	import AccountsList from '@/components/accounts/accounts-list.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>Portfolio dashboard</title>
</svelte:head>

<AccountsList accounts={data.accounts}></AccountsList>
