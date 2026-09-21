import { getContext, setContext } from 'svelte';
import { getAccountService, type AccountService } from '$lib/api/accountService';
import type { UserHolding } from '$lib/types/account';
import {
	groupHoldings,
	type HoldingsGroup,
	type HoldingsGroupMode
} from '$lib/utils/finance/holdings-group';

const PAGE_SIZE = 50;
// Safety valve against a stale `total` from the server: never page forever.
const MAX_PAGES = 100;

export class HoldingsService {
	rows = $state<UserHolding[]>([]);
	isLoading = $state(false);
	errorMessage = $state<string | null>(null);
	groupBy = $state<HoldingsGroupMode>('none');
	groupedHoldings = $derived.by<HoldingsGroup[]>(() => groupHoldings(this.rows, this.groupBy));
	private client: AccountService;

	constructor(customFetch?: typeof fetch) {
		this.client = getAccountService(customFetch);
	}

	setGroupBy(mode: HoldingsGroupMode) {
		this.groupBy = mode;
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
