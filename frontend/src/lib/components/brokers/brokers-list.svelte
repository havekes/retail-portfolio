<script lang="ts">
	import { onMount } from 'svelte';
	import { brokerService } from '@/services/broker/brokerService';
	import type { BrokerUser } from '@/types/broker/broker';
	import BrokersListItem from './brokers-list-item.svelte';
	import { Skeleton } from '../ui/skeleton';
	import { Alert, AlertDescription } from '../ui/alert';
	import { Button } from '../ui/button';
	import ConnectBrokerModal from './connect-broker-modal.svelte';

	let brokerUsers = $state<Promise<BrokerUser[]> | null>(null);
	let isModalOpen = $state(false);

	function loadUsers() {
		brokerUsers = brokerService.getBrokerUsers();
	}

	onMount(() => {
		loadUsers();
	});
</script>

<ConnectBrokerModal bind:open={isModalOpen} onSuccess={loadUsers} />

<div class="brokers-list w-full space-y-4">
	<div class="flex items-center border-b px-4 py-2">
		<h2>Connected brokers</h2>
		<div class="ms-auto">
			<Button onclick={() => (isModalOpen = true)}>Connect broker</Button>
		</div>
	</div>

	<div class="space-y-4 px-4">
		{#await brokerUsers}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:then users}
			{#if users}
				{#each users as user (user.id)}
					<BrokersListItem brokerUser={user} />
				{:else}
					<div class="flex flex-col items-center justify-center space-y-4 py-12">
						<Alert class="w-fit">
							<AlertDescription>No connected brokers.</AlertDescription>
						</Alert>
						<Button onclick={() => (isModalOpen = true)}>Connect broker</Button>
					</div>
				{/each}
			{/if}
		{:catch error}
			<Alert>
				<AlertDescription>Error: {error.message}</AlertDescription>
			</Alert>
		{/await}
	</div>
</div>
