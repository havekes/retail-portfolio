import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/api/accountService', () => ({
	getAccountService: vi.fn()
}));

import { getAccountService, type AccountService } from '$lib/api/accountService';
import { HoldingsService, getHoldingsService } from './holdingsService.svelte';
import type { UserHolding } from '$lib/types/account';

const getUserHoldings = vi.fn();

function makeHolding(id: string, overrides: Partial<UserHolding> = {}): UserHolding {
	return {
		id,
		security_id: 'sec-aapl',
		security_symbol: 'AAPL',
		security_name: 'Apple Inc.',
		quantity: 1,
		average_cost: 100,
		total_value: 100,
		profit_loss: 0,
		currency: 'CAD',
		security_currency: 'CAD',
		unconverted_total_value: 100,
		converted_average_cost: 100,
		converted_latest_price: 100,
		unconverted_profit_loss: 0,
		account_id: 'acc-1',
		account_name: 'Account One',
		...overrides
	};
}

function makeHoldings(count: number, startIndex = 0, accountId = 'acc-1'): UserHolding[] {
	return Array.from({ length: count }, (_, index) =>
		makeHolding(`h-${startIndex + index}`, { account_id: accountId })
	);
}

const page = (items: UserHolding[], total: number, offset: number) => ({
	items,
	total,
	offset,
	limit: 50
});

describe('HoldingsService', () => {
	let service: HoldingsService;

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(getAccountService).mockReturnValue({
			getUserHoldings
		} as unknown as AccountService);
		service = new HoldingsService();
	});

	it('starts with empty, idle state and no grouping', () => {
		expect(service.rows).toEqual([]);
		expect(service.isLoading).toBe(false);
		expect(service.errorMessage).toBeNull();
		expect(service.groupBy).toBe('none');
		expect(service.groupedHoldings).toEqual([]);
	});

	it('loads a single page and toggles isLoading around the request', async () => {
		const rows = makeHoldings(2);
		let resolveFetch!: (value: unknown) => void;
		getUserHoldings.mockReturnValueOnce(
			new Promise((resolve) => {
				resolveFetch = resolve;
			})
		);

		const promise = service.load();

		expect(service.isLoading).toBe(true);

		resolveFetch(page(rows, 2, 0));
		await promise;

		expect(getUserHoldings).toHaveBeenCalledWith(0, 50, undefined);
		expect(service.isLoading).toBe(false);
		expect(service.errorMessage).toBeNull();
		expect(service.rows).toEqual(rows);
	});

	it('pages through the whole portfolio until offset reaches total', async () => {
		getUserHoldings
			.mockResolvedValueOnce(page(makeHoldings(50, 0), 120, 0))
			.mockResolvedValueOnce(page(makeHoldings(50, 50), 120, 50))
			.mockResolvedValueOnce(page(makeHoldings(20, 100), 120, 100));

		await service.load('token-abc');

		expect(getUserHoldings).toHaveBeenCalledTimes(3);
		expect(getUserHoldings.mock.calls.map((call) => call[0])).toEqual([0, 50, 100]);
		expect(getUserHoldings.mock.calls.every((call) => call[2] === 'token-abc')).toBe(true);
		expect(service.rows).toHaveLength(120);
	});

	it('stops paging when a page comes back empty (stale total guard)', async () => {
		getUserHoldings.mockResolvedValueOnce(page([], 100, 0));

		await service.load();

		expect(getUserHoldings).toHaveBeenCalledTimes(1);
		expect(service.rows).toEqual([]);
		expect(service.errorMessage).toBeNull();
	});

	it('stores the caught error message and keeps previous rows on failure', async () => {
		getUserHoldings.mockResolvedValueOnce(page(makeHoldings(1), 1, 0));
		await service.load();
		expect(service.rows).toHaveLength(1);

		getUserHoldings.mockRejectedValueOnce(new Error('Network down'));
		await service.load();

		expect(service.errorMessage).toBe('Network down');
		expect(service.rows).toHaveLength(1);
		expect(service.rows[0].id).toBe('h-0');
		expect(service.isLoading).toBe(false);
	});

	it('stringifies non-Error throws into errorMessage', async () => {
		getUserHoldings.mockRejectedValueOnce('boom');

		await service.load();

		expect(service.errorMessage).toBe('boom');
		expect(service.rows).toEqual([]);
	});

	it('clears a previous error on a successful load', async () => {
		getUserHoldings.mockRejectedValueOnce(new Error('Network down'));
		await service.load();
		expect(service.errorMessage).toBe('Network down');

		getUserHoldings.mockResolvedValueOnce(page(makeHoldings(1), 1, 0));
		await service.load();

		expect(service.errorMessage).toBeNull();
	});

	it('derives grouped holdings for both modes and reacts to setGroupBy', () => {
		service.rows = [
			makeHolding('h-1', { account_id: 'acc-1', quantity: 10 }),
			makeHolding('h-2', { account_id: 'acc-2', quantity: 5 }),
			makeHolding('h-3', { security_id: 'sec-msft', quantity: 2 })
		];

		expect(service.groupedHoldings).toHaveLength(3);
		expect(service.groupedHoldings.map((group) => group.account_count)).toEqual([1, 1, 1]);

		service.setGroupBy('company');

		expect(service.groupBy).toBe('company');
		expect(service.groupedHoldings).toHaveLength(2);
		expect(service.groupedHoldings[0].quantity).toBe(15);
		expect(service.groupedHoldings[0].account_count).toBe(2);
	});

	it('getHoldingsService(customFetch) returns an isolated service instance', () => {
		const isolated = getHoldingsService(vi.fn() as unknown as typeof fetch);
		expect(isolated).toBeInstanceOf(HoldingsService);
		expect(isolated).not.toBe(service);
		isolated.rows = [makeHolding('h-x')];
		expect(service.rows).toEqual([]);
	});
});
