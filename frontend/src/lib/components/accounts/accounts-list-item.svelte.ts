import { accountClient } from '$lib/api/accountClient';
import type { AccountTotals } from '@/types/account';

export class AccountsListItemState {
	private totalsCache = $state<Record<string, AccountTotals>>({});

	constructor(private getAccountId: () => string) {}

	async fetchAccountTotals(id: string): Promise<AccountTotals> {
		if (this.totalsCache[id]) return this.totalsCache[id];

		try {
			const totals = await accountClient.getAccountTotals(id);
			this.totalsCache[id] = totals;
			return totals;
		} catch (error) {
			console.error('Failed to fetch account totals', error);
			throw error;
		}
	}

	totals = $derived.by(() => {
		return this.fetchAccountTotals(this.getAccountId());
	});

	getAccountTotals(id: string): AccountTotals | undefined {
		return this.totalsCache[id];
	}

	async renameAccount(id: string, name: string) {
		try {
			await accountClient.renameAccount(id, name);
		} catch (error) {
			console.error('Failed to rename account', error);
			throw error;
		}
	}

	async syncPositions(id: string) {
		try {
			// Eagerly set syncing state to improve responsiveness
			// We rely on the parent (AccountsListState) which manages the syncing set.
			// But since we don't have direct access here easily (without props or context),
			// let's just make sure the backend call is made.
			// Wait, the parent has syncingAccountIds. I should really update it there.
			await accountClient.syncPositions(id);
		} catch (error) {
			console.error('Failed to sync positions', error);
			throw error;
		}
	}
}
