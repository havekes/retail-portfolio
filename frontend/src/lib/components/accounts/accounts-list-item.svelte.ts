import { accountClient } from '$lib/api/accountClient';
import type { AccountTotals, Holding } from '@/types/account';

export class AccountsListItemState {
	private totalsCache = $state<Record<string, AccountTotals>>({});
	private holdingsCache = $state<Record<string, Holding[]>>({});
	private version = $state(0);

	isExpanded = $state(false);
	holdingsPromise = $state<Promise<Holding[]> | null>(null);

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

	async fetchAccountHoldings(id: string): Promise<Holding[]> {
		if (this.holdingsCache[id]) return this.holdingsCache[id];

		try {
			const res = await accountClient.getAccountHoldings(id);
			const items = res?.items ?? [];
			this.holdingsCache[id] = items;
			return items;
		} catch (error) {
			console.error('Failed to fetch account holdings', error);
			throw error;
		}
	}

	toggleExpanded() {
		this.isExpanded = !this.isExpanded;
		if (this.isExpanded) {
			const id = this.getAccountId();
			if (this.holdingsCache[id]) {
				this.holdingsPromise = Promise.resolve(this.holdingsCache[id]);
			} else {
				this.holdingsPromise = this.fetchAccountHoldings(id);
			}
		}
	}

	invalidateCache(id: string) {
		delete this.totalsCache[id];
		delete this.holdingsCache[id];
		this.version++;
		if (this.isExpanded) {
			this.holdingsPromise = this.fetchAccountHoldings(id);
		}
	}

	totals = $derived.by(() => {
		return this.version >= 0 ? this.fetchAccountTotals(this.getAccountId()) : Promise.reject();
	});

	getAccountTotals(id: string): AccountTotals | undefined {
		return this.totalsCache[id];
	}

	getAccountHoldings(id: string): Holding[] | undefined {
		return this.holdingsCache[id];
	}
}
