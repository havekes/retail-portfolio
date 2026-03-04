<script lang="ts">
	import { Institution } from '@/types/account';
	import type { BrokerUser } from '@/types/broker/broker';
	import { Button } from '@/components/ui/button';
	import BrokerAccountsModal from './broker-accounts-modal.svelte';

	let { brokerUser } = $props<{ brokerUser: BrokerUser }>();
	let showModal = $state(false);
</script>

<div class="broker-accounts-list-item group flex space-x-4 rounded-lg bg-muted p-4">
	<div class="flex-1 space-y-2">
		<div class="font-medium">{brokerUser.name}</div>
		<div class="text-sm text-muted-foreground">
			{Institution[brokerUser.institution_id]}
		</div>
	</div>
	<div class="mr-4 flex items-center text-sm text-muted-foreground">
		{brokerUser.accounts_synced}/{brokerUser.accounts_total} synced
	</div>
	<div class="flex items-center">
		<Button variant="outline" size="sm" onclick={() => (showModal = true)}>View Accounts</Button>
	</div>
</div>

<BrokerAccountsModal {brokerUser} bind:open={showModal} />
