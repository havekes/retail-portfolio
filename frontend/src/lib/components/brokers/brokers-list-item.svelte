<script lang="ts">
	import { Institution } from '@/types/account';
	import type { BrokerUser } from '@/types/broker/broker';
	import type { Account } from '@/types/account';
	import { brokerService } from '@/services/broker/brokerService';
	import { accountService } from '@/services/accountService';
	import { Skeleton } from '../ui/skeleton';
	import { Button } from '../ui/button';
	import EditableTitle from '../form/editable-title.svelte';
	import SyncAccountsModal from './sync-accounts-modal.svelte';
	import RefreshCw from '@lucide/svelte/icons/refresh-cw';

	let { brokerUser } = $props<{ brokerUser: BrokerUser }>();

	let accountsPromise = $derived(
		brokerService.getBrokerUserAccounts(brokerUser.institution_id, brokerUser.id)
	);

	let internalAccountsPromise = $derived(accountService.getAccounts());

	let isSyncModalOpen = $state(false);

	// Ensure re-rendering when sync completes
	let fetchTrigger = $state(0);

	function getSyncedCount(available: any[], internal: Account[]) {
		const internalExternalIds = new Set(internal.map((acc) => acc.external_id));
		return available.filter((acc) => internalExternalIds.has(acc.id)).length;
	}

	function handleSyncComplete() {
		fetchTrigger += 1;
	}
</script>

<div class="brokers-list-item group flex space-x-4 rounded-lg bg-muted p-4">
	<div class="flex-1 space-y-2">
		<EditableTitle
			bind:value={brokerUser.name}
			onSave={(val) =>
				brokerService.renameBrokerUser(brokerUser.institution_id, brokerUser.id, val)}
			textClass="font-medium"
		/>
		<div class="text-sm text-muted-foreground">
			{Institution[brokerUser.institution_id]}
		</div>
	</div>
	<div class="flex items-center text-sm text-muted-foreground">
		{#key fetchTrigger}
			{#await Promise.all([accountsPromise, internalAccountsPromise])}
				<Skeleton class="h-4 w-28" />
			{:then [accounts, internalAccounts]}
				{@const syncedCount = getSyncedCount(accounts, internalAccounts)}
				<Button
					variant="ghost"
					size="sm"
					class="flex items-center space-x-2"
					onclick={() => (isSyncModalOpen = true)}
				>
					<RefreshCw class="h-4 w-4" />
					<span>{syncedCount} account{syncedCount === 1 ? '' : 's'} synced</span>
				</Button>

				<SyncAccountsModal
					bind:open={isSyncModalOpen}
					{brokerUser}
					availableAccounts={accounts}
					{internalAccounts}
					onSave={handleSyncComplete}
				/>
			{:catch}
				Error loading accounts
			{/await}
		{/key}
	</div>
</div>
