import { getContext, setContext } from 'svelte';
import { SvelteSet } from 'svelte/reactivity';
import { getAccountService, type AccountService } from '$lib/api/accountService';
import {
	getMarketService,
	type MarketService,
	type SecurityValuation
} from '$lib/api/marketService';
import type { UserHolding } from '$lib/types/account';
import {
	groupHoldings,
	type HoldingsGroup,
	type HoldingsGroupMode
} from '$lib/utils/finance/holdings-group';

const PAGE_SIZE = 50;
// Safety valve against a stale `total` from the server: never page forever.
const MAX_PAGES = 100;

export type HoldingsFilter =
	| { type: 'all' }
	| { type: 'portfolio'; portfolioId: string; accountIds: string[] }
	| { type: 'account'; accountId: string };

export class HoldingsService {
	allRows = $state<UserHolding[]>([]);
	filter = $state<HoldingsFilter>({ type: 'all' });
	valuations = $state<Record<string, SecurityValuation>>({});
	isLoading = $state(false);
	errorMessage = $state<string | null>(null);
	groupBy = $state<HoldingsGroupMode>('none');

	get rows(): UserHolding[] {
		const filter = this.filter;
		if (filter.type === 'portfolio') {
			return this.allRows.filter((r) => filter.accountIds.includes(r.account_id));
		}
		if (filter.type === 'account') {
			return this.allRows.filter((r) => r.account_id === filter.accountId);
		}
		return this.allRows;
	}

	set rows(value: UserHolding[]) {
		this.allRows = value;
	}

	groupedHoldings = $derived.by<HoldingsGroup[]>(() => groupHoldings(this.rows, this.groupBy));
	private client: AccountService;
	private marketClient: MarketService;

	constructor(customFetch?: typeof fetch) {
		this.client = getAccountService(customFetch);
		this.marketClient = getMarketService(customFetch);
	}

	setGroupBy(mode: HoldingsGroupMode) {
		this.groupBy = mode;
	}

	filterByPortfolio(portfolioId: string, accountIds: string[]) {
		this.filter = { type: 'portfolio', portfolioId, accountIds };
	}

	filterByAccount(accountId: string) {
		this.filter = { type: 'account', accountId };
	}

	clearFilter() {
		this.filter = { type: 'all' };
	}

	/**
	 * Load every page of holdings. Returns the caught error (after storing its
	 * message in `errorMessage`) so callers can route a 401 through the shared
	 * async-data seam, or `null` when the load succeeded.
	 */
	async load(token?: string | null): Promise<unknown | null> {
		this.isLoading = true;
		this.errorMessage = null;

		try {
			const collected: UserHolding[] = [];
			let offset = 0;
			let total = Infinity;

			for (let page = 0; page < MAX_PAGES && offset < total; page++) {
				const response = await this.client.getUserHoldings(offset, PAGE_SIZE, token);
				collected.push(...response.items);
				total = response.total;
				offset += PAGE_SIZE;

				if (response.items.length === 0) break;
			}

			this.rows = collected;

			const uniqueSecurityIds = Array.from(
				new SvelteSet(collected.map((h) => h.security_id).filter((id): id is string => Boolean(id)))
			);

			if (uniqueSecurityIds.length > 0) {
				try {
					const batchValuations = await this.marketClient.getValuationsBatch(
						uniqueSecurityIds,
						token
					);
					const valMap: Record<string, SecurityValuation> = {};
					for (const val of batchValuations) {
						if (val.security_id) {
							valMap[val.security_id] = {
								...val,
								lower_bound: Number(val.lower_bound),
								upper_bound: Number(val.upper_bound)
							};
						}
					}
					this.valuations = valMap;
				} catch {
					this.valuations = {};
				}
			} else {
				this.valuations = {};
			}

			return null;
		} catch (error) {
			this.errorMessage = error instanceof Error ? error.message : String(error);

			return error;
		} finally {
			this.isLoading = false;
		}
	}
}

const HOLDINGS_SERVICE_KEY = Symbol('holdings-service');

export function setHoldingsService() {
	const service = new HoldingsService();
	setContext(HOLDINGS_SERVICE_KEY, service);
	return service;
}

export function getHoldingsService(customFetch?: typeof fetch) {
	if (customFetch) {
		return new HoldingsService(customFetch);
	}
	return getContext<HoldingsService>(HOLDINGS_SERVICE_KEY);
}
