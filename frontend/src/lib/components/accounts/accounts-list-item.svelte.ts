import { accountClient } from '$lib/api/accountClient';
import type { AccountTotals } from '@/types/account';

export class AccountsListItemState {
	private totalsCache = $state<Record<string, AccountTotals>>({});
	private version = $state(0);

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

	invalidateCache(id: string) {
		delete this.totalsCache[id];
		this.version++;
	}

	totals = $derived.by(() => {
		return this.version >= 0 ? this.fetchAccountTotals(this.getAccountId()) : Promise.reject();
	});

	getAccountTotals(id: string): AccountTotals | undefined {
		return this.totalsCache[id];
	}
}
