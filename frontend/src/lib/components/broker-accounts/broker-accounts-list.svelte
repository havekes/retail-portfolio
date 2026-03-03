<script lang="ts">
	import { onMount } from 'svelte';
	import { brokerService } from '@/services/broker/brokerService';
	import type { BrokerUser } from '@/types/broker/broker';
	import BrokerAccountsListItem from './broker-accounts-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import { Alert, AlertDescription } from '../ui/alert';

	let brokerUsers = $state<Promise<BrokerUser[]> | null>(null);

	onMount(() => {
		brokerUsers = brokerService.getBrokerUsers();
	});
</script>

<div class="broker-accounts-list w-full space-y-4">
	<div class="flex items-center border-b px-4 py-2">
		<h2>Connected broker accounts</h2>
	</div>

	<div class="space-y-4 px-4">
		{#await brokerUsers}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:then users}
			{#if users}
				{#each users as user (user.id)}
					<BrokerAccountsListItem brokerUser={user} />
				{:else}
					<Alert>
						<AlertDescription>No connected broker accounts.</AlertDescription>
					</Alert>
				{/each}
			{/if}
		{:catch error}
			<div class="error">Error: {error.message}</div>
		{/await}
	</div>
</div>
