<script lang="ts">
	import { onMount } from 'svelte';
	import { BrokersListState } from './brokers-list.svelte.js';
	import BrokersListItem from './brokers-list-item.svelte';
	import { Skeleton } from '../ui/skeleton/index.js';
	import * as Alert from '$lib/components/ui/alert/index.js';
	import { Button } from '../ui/button/index.js';
	import ConnectBrokerModal from './connect-broker-modal.svelte';
	import { CircleAlert } from '@lucide/svelte';

	const state = new BrokersListState();

	onMount(() => {
		state.loadUsers();
	});
</script>

<ConnectBrokerModal bind:open={state.isModalOpen} onSuccess={state.loadUsers} />

<div class="brokers-list w-full space-y-4">
	<div class="flex items-center border-b px-4 py-2">
		<h2>Connected brokers</h2>
		{#if state.users.length > 0}
			<div class="ms-auto">
				<Button onclick={state.openModal}>Connect broker</Button>
			</div>
		{/if}
	</div>

	<div class="space-y-4 px-4">
		{#if state.errorMessage}
			<Alert.Root variant="destructive">
				<Alert.Description>Error: {state.errorMessage}</Alert.Description>
			</Alert.Root>
		{/if}

		{#if state.isLoading}
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
			<Skeleton class="h-16 w-full rounded-md" />
		{:else}
			<!-- eslint-disable-next-line @typescript-eslint/no-unused-vars -->
			{#each state.users as _, i (state.users[i].id)}
				<BrokersListItem bind:brokerUser={state.users[i]} />
			{:else}
				<Alert.Root class="w-full">
					<CircleAlert />
					<Alert.Title>You have not yet connected any brokers</Alert.Title>
					<Alert.Description>
						Connect to a broker to autoatically import and sync accounts and holdings
					</Alert.Description>
				</Alert.Root>
				<div class="flex flex-col items-center py-2">
					<Button onclick={state.openModal}>Connect broker</Button>
				</div>
			{/each}
		{/if}
	</div>
</div>
