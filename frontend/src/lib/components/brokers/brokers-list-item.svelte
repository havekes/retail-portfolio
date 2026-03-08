<script lang="ts">
	import { Institution } from '@/types/account';
	import type { BrokerUser } from '@/types/broker/broker';
	import { BrokersListItemState } from './brokers-list-item.svelte.js';
	import { Skeleton } from '../ui/skeleton/index.js';
	import { Button } from '../ui/button/index.js';
	import EditableTitle from '../form/editable-title.svelte';
	import SyncAccountsModal from './sync-accounts-modal.svelte';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';

	let { brokerUser = $bindable() } = $props<{ brokerUser: BrokerUser }>();

	const state = new BrokersListItemState(() => brokerUser);
</script>

<div class="brokers-list-item group flex flex-col space-y-2 rounded-lg bg-accent p-4">
	<div class="flex items-center justify-between">
		<EditableTitle
			bind:value={brokerUser.displayName}
			onSave={state.renameBrokerUser}
			textClass="font-medium"
		/>
		<div class="flex items-center text-sm text-muted-foreground">
			{#key state.fetchTrigger}
				{#await Promise.all([state.accountsPromise, state.internalAccountsPromise])}
					<Skeleton class="h-8 w-32 bg-background" />
				{:then [accounts, internalAccounts]}
					{@const syncedCount = state.getSyncedCount(accounts, internalAccounts)}
					<Button variant="outline" onclick={() => (state.isSyncModalOpen = true)}>
						<RefreshCw class="h-4 w-4" />
						<span>{syncedCount} account{syncedCount === 1 ? '' : 's'} synced</span>
					</Button>

					<SyncAccountsModal
						bind:open={state.isSyncModalOpen}
						{brokerUser}
						availableAccounts={accounts}
						{internalAccounts}
						onSave={state.handleSyncComplete}
					/>
				{:catch}
					Error loading accounts
				{/await}
			{/key}
		</div>
	</div>
	<div class="flex items-center justify-between text-sm text-muted-foreground">
		<div>
			{Institution[brokerUser.institution_id]}
		</div>
		<div>
			{#key state.fetchTrigger}
				{#await Promise.all([state.accountsPromise, state.internalAccountsPromise])}
					<Skeleton class="h-4 w-24 bg-background" />
				{:then [accounts]}
					{accounts.length} account{accounts.length === 1 ? '' : 's'} available
				{:catch}
					Error loading accounts
				{/await}
			{/key}
		</div>
	</div>
</div>
