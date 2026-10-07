import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/api/accountService', () => ({
	getAccountService: vi.fn()
}));

vi.mock('$lib/api/accountClient', () => ({
	getAccountClient: vi.fn()
}));

vi.mock('$lib/api/marketService', () => ({
	getMarketService: vi.fn()
}));

import { getAccountService, type AccountService } from '$lib/api/accountService';
import { getAccountClient, type AccountClient } from '$lib/api/accountClient';
import { getMarketService, type MarketService } from '$lib/api/marketService';
import { ApiError } from '$lib/api/apiClient';
import { HoldingsService, getHoldingsService } from './holdingsService.svelte';
import type { AccountTotals, UserHolding } from '$lib/types/account';

const getUserHoldings = vi.fn();
const getValuationsBatch = vi.fn();
const getAccountTotals = vi.fn();

function makeTotals(value: number, profitLoss: number): AccountTotals {
	return {
		cost: { value: String(value - profitLoss) },
		value: { value: String(value) },
		cash: { value: '0' },
		net_deposits: null,
		profit_loss: { value: String(profitLoss) },
		return_percent: null,
		basis: 'cost'
	};
}

function makeHolding(id: string, overrides: Partial<UserHolding> = {}): UserHolding {
	const merged = {
		id,
		security_id: 'sec-aapl',
		security_symbol: 'AAPL',
		security_name: 'Apple Inc.',
		quantity: 1,
		average_cost: 100,
		total_value: 100,
		profit_loss: 0,
		currency: 'CAD',
		display_currency: 'CAD',
		security_currency: 'CAD',
		unconverted_total_value: 100,
		converted_average_cost: 100,
		converted_latest_price: 100,
		unconverted_profit_loss: 0,
		account_id: 'acc-1',
		account_name: 'Account One',
		...overrides
	};
	return { ...merged, display_total_value: overrides.display_total_value ?? merged.total_value };
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
		getAccountTotals.mockReset();
		getAccountTotals.mockResolvedValue(makeTotals(0, 0));
		vi.mocked(getAccountClient).mockReturnValue({
			getAccountTotals
		} as unknown as AccountClient);
		vi.mocked(getMarketService).mockReturnValue({
			getValuationsBatch
		} as unknown as MarketService);
		getValuationsBatch.mockResolvedValue([]);
		service = new HoldingsService();
	});

	it('starts with empty, idle state and no grouping', () => {
		expect(service.rows).toEqual([]);
		expect(service.valuations).toEqual({});
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

	it('returns null when the load succeeds so callers can skip error handling', async () => {
		getUserHoldings.mockResolvedValueOnce(page(makeHoldings(1), 1, 0));

		await expect(service.load()).resolves.toBeNull();
	});

	it('returns the caught error so callers can route a 401 through the shared seam', async () => {
		const unauthorized = new ApiError(401, 'Unauthorized');
		getUserHoldings.mockRejectedValueOnce(unauthorized);

		const result = await service.load();

		expect(result).toBe(unauthorized);
		expect(service.errorMessage).toBe('Unauthorized');
	});

	it('clears a previous error on a successful load', async () => {
		getUserHoldings.mockRejectedValueOnce(new Error('Network down'));
		await service.load();
		expect(service.errorMessage).toBe('Network down');

		getUserHoldings.mockResolvedValueOnce(page(makeHoldings(1), 1, 0));
		await service.load();

		expect(service.errorMessage).toBeNull();
	});

	it('derives grouped holdings for both stock and company modes and reacts to setGroupBy', () => {
		service.rows = [
			makeHolding('h-1', { account_id: 'acc-1', quantity: 10 }),
			makeHolding('h-2', { account_id: 'acc-2', quantity: 5 }),
			makeHolding('h-3', { security_id: 'sec-msft', quantity: 2 })
		];

		expect(service.groupedHoldings).toHaveLength(3);
		expect(service.groupedHoldings.map((group) => group.account_count)).toEqual([1, 1, 1]);

		service.setGroupBy('stock');

		expect(service.groupBy).toBe('stock');
		expect(service.groupedHoldings).toHaveLength(2);
		expect(service.groupedHoldings[0].quantity).toBe(15);
		expect(service.groupedHoldings[0].account_count).toBe(2);

		service.setGroupBy('company');
		expect(service.groupBy).toBe('company');
		expect(service.groupedHoldings).toHaveLength(2);
	});

	it('filters rows by portfolio account IDs and restores on clearFilter', () => {
		service.rows = [
			makeHolding('h-1', { account_id: 'acc-1' }),
			makeHolding('h-2', { account_id: 'acc-2' }),
			makeHolding('h-3', { account_id: 'acc-3' })
		];

		expect(service.rows).toHaveLength(3);

		service.filterByPortfolio('port-1', ['acc-1', 'acc-3']);
		expect(service.rows).toHaveLength(2);
		expect(service.rows.map((r) => r.id)).toEqual(['h-1', 'h-3']);

		service.clearFilter();
		expect(service.rows).toHaveLength(3);
	});

	it('filters rows by account ID', () => {
		service.rows = [
			makeHolding('h-1', { account_id: 'acc-1' }),
			makeHolding('h-2', { account_id: 'acc-2' }),
			makeHolding('h-3', { account_id: 'acc-3' })
		];

		service.filterByAccount('acc-2');
		expect(service.rows).toHaveLength(1);
		expect(service.rows[0].id).toBe('h-2');
	});

	it('updates groupedHoldings when active filter changes', () => {
		service.rows = [
			makeHolding('h-1', { security_id: 'sec-aapl', account_id: 'acc-1', quantity: 10 }),
			makeHolding('h-2', { security_id: 'sec-aapl', account_id: 'acc-2', quantity: 5 }),
			makeHolding('h-3', { security_id: 'sec-msft', account_id: 'acc-3', quantity: 2 })
		];

		service.setGroupBy('stock');
		expect(service.groupedHoldings).toHaveLength(2);

		service.filterByPortfolio('port-1', ['acc-1']);
		expect(service.groupedHoldings).toHaveLength(1);
		expect(service.groupedHoldings[0].security_symbol).toBe('AAPL');
		expect(service.groupedHoldings[0].quantity).toBe(10);
	});

	it('getHoldingsService(customFetch) returns an isolated service instance', () => {
		const isolated = getHoldingsService(vi.fn() as unknown as typeof fetch);
		expect(isolated).toBeInstanceOf(HoldingsService);
		expect(isolated).not.toBe(service);
		isolated.rows = [makeHolding('h-x')];
		expect(service.rows).toEqual([]);
	});

	describe('batch valuations', () => {
		it('fetches valuations in batch for distinct security_ids and maps by security_id with numeric bounds', async () => {
			getUserHoldings.mockResolvedValueOnce(
				page(
					[
						makeHolding('h-1', { security_id: 'sec-aapl' }),
						makeHolding('h-2', { security_id: 'sec-msft' }),
						makeHolding('h-3', { security_id: 'sec-aapl' })
					],
					3,
					0
				)
			);
			getValuationsBatch.mockResolvedValueOnce([
				{
					security_id: 'sec-aapl',
					lower_bound: '150.00',
					upper_bound: '220.00'
				},
				{
					security_id: 'sec-msft',
					lower_bound: 300,
					upper_bound: 400
				}
			]);

			await service.load('test-token');

			expect(getValuationsBatch).toHaveBeenCalledWith(['sec-aapl', 'sec-msft'], 'test-token');
			expect(service.valuations['sec-aapl']).toEqual({
				security_id: 'sec-aapl',
				lower_bound: 150,
				upper_bound: 220
			});
			expect(service.valuations['sec-msft']).toEqual({
				security_id: 'sec-msft',
				lower_bound: 300,
				upper_bound: 400
			});
		});

		it('gracefully falls back to empty valuations when batch valuation lookup fails without failing holdings load', async () => {
			getUserHoldings.mockResolvedValueOnce(
				page([makeHolding('h-1', { security_id: 'sec-aapl' })], 1, 0)
			);
			getValuationsBatch.mockRejectedValueOnce(new Error('Valuation service timeout'));

			const result = await service.load();

			expect(result).toBeNull();
			expect(service.rows).toHaveLength(1);
			expect(service.valuations).toEqual({});
			expect(service.errorMessage).toBeNull();
		});

		it('does not call getValuationsBatch when holdings are empty', async () => {
			getUserHoldings.mockResolvedValueOnce(page([], 0, 0));

			await service.load();

			expect(getValuationsBatch).not.toHaveBeenCalled();
			expect(service.valuations).toEqual({});
		});
	});

	describe('loadAccountTotals', () => {
		it('fetches the missing accounts in parallel and caches them by id', async () => {
			const totals1 = makeTotals(1000, 100);
			const totals2 = makeTotals(500, 50);
			getAccountTotals.mockImplementation(async (id: string) =>
				id === 'acc-1' ? totals1 : totals2
			);

			await expect(service.loadAccountTotals(['acc-1', 'acc-2'])).resolves.toBeNull();

			expect(getAccountTotals).toHaveBeenCalledTimes(2);
			expect(getAccountTotals).toHaveBeenCalledWith('acc-1', undefined);
			expect(service.accountTotals).toEqual({ 'acc-1': totals1, 'acc-2': totals2 });
		});

		it('deduplicates ids and skips accounts already cached', async () => {
			await service.loadAccountTotals(['acc-1', 'acc-1']);
			expect(getAccountTotals).toHaveBeenCalledTimes(1);

			getAccountTotals.mockClear();
			await service.loadAccountTotals(['acc-1', 'acc-2']);

			expect(getAccountTotals).toHaveBeenCalledTimes(1);
			expect(getAccountTotals).toHaveBeenCalledWith('acc-2', undefined);
		});

		it('threads the token through to the account client', async () => {
			await service.loadAccountTotals(['acc-1'], 'token-abc');

			expect(getAccountTotals).toHaveBeenCalledWith('acc-1', 'token-abc');
		});

		it('omits a failed account, keeps the successful ones and stores the error message', async () => {
			const ok = makeTotals(1000, 100);
			getAccountTotals.mockImplementation(async (id: string) => {
				if (id === 'acc-2') throw new Error('Totals service unavailable');
				return ok;
			});

			const error = await service.loadAccountTotals(['acc-1', 'acc-2']);

			expect(error).toBeInstanceOf(Error);
			expect(service.accountTotals['acc-1']).toEqual(ok);
			expect(service.accountTotals['acc-2']).toBeUndefined();
			expect(service.errorMessage).toBe('Totals service unavailable');
		});

		it('returns null without touching the error when every requested account is cached', async () => {
			await service.loadAccountTotals(['acc-1']);
			getAccountTotals.mockClear();

			await expect(service.loadAccountTotals(['acc-1'])).resolves.toBeNull();

			expect(getAccountTotals).not.toHaveBeenCalled();
		});
	});
});
