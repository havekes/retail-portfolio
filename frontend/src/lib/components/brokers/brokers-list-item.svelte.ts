import { SvelteSet } from 'svelte/reactivity';
import { getBrokerService, type BrokerService } from './brokerService.svelte';
import { accountClient } from '$lib/api/accountClient';
import type { BrokerUser } from '@/types/broker/broker';
import type { Account } from '@/types/account';
import type { BrokerAccount } from '@/api/types/broker';

export class BrokersListItemState {
	isSyncModalOpen = $state(false);
	fetchTrigger = $state(0);

	private brokerService: BrokerService;

	constructor(private getBrokerUser: () => BrokerUser) {
		this.brokerService = getBrokerService();
	}

	get accountsPromise() {
		const user = this.getBrokerUser();
		// Trigger dependency on fetchTrigger
		void this.fetchTrigger;
		return this.brokerService.getBrokerUserAccounts(user.id);
	}

	get internalAccountsPromise() {
		void this.fetchTrigger;
		return accountClient.getAccounts();
	}

	getSyncedCount = (available: BrokerAccount[], internal: Account[]) => {
		const internalExternalIds = new SvelteSet(internal.map((acc) => acc.external_id));
		return available.filter((acc) => internalExternalIds.has(acc.id)).length;
	};

	handleSyncComplete = () => {
		this.fetchTrigger += 1;
	};

	renameBrokerUser = async (val: string) => {
		const user = this.getBrokerUser();
		await this.brokerService.updateBrokerUserDisplayName(user.id, val);
	};
}
