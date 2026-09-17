import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getAccountService } from './accountService';
import type { UserHolding } from '../types/account';

const makeHolding = (id: string, accountId = 'acc-1'): UserHolding => ({
	id,
	security_id: `sec-${id}`,
	security_symbol: 'AAPL',
	security_name: 'Apple Inc.',
	quantity: 10,
	average_cost: 150,
	total_value: 2000,
	profit_loss: 500,
	currency: 'CAD',
	security_currency: 'CAD',
	unconverted_total_value: 2000,
	converted_average_cost: 150,
	converted_latest_price: 200,
	unconverted_profit_loss: 500,
	account_id: accountId,
	account_name: `Account ${accountId}`
});

describe('AccountService.getUserHoldings', () => {
	let mockFetch: ReturnType<typeof vi.fn>;
	let service: ReturnType<typeof getAccountService>;

	beforeEach(() => {
		vi.clearAllMocks();
		mockFetch = vi.fn();
		service = getAccountService(mockFetch as unknown as typeof fetch);
	});

	it('requests /accounts/holdings with the given offset and limit', async () => {
		const body = { items: [makeHolding('h-1')], total: 1, offset: 10, limit: 25 };
		mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);

		const result = await service.getUserHoldings(10, 25);

		expect(result).toEqual(body);
		expect(mockFetch).toHaveBeenCalledTimes(1);
		const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
		expect(String(url)).toContain('/accounts/holdings?offset=10&limit=25');
		expect(init).toMatchObject({ method: 'GET', credentials: 'include' });
	});

	it('defaults to offset 0 and limit 50', async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ items: [], total: 0, offset: 0, limit: 50 })
		} as Response);

		await service.getUserHoldings();

		const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
		expect(String(url)).toContain('/accounts/holdings?offset=0&limit=50');
	});

	it('forwards the token as a Bearer Authorization header', async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ items: [], total: 0, offset: 0, limit: 50 })
		} as Response);

		await service.getUserHoldings(0, 50, 'token-abc');

		const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
		expect((init.headers as Record<string, string>).Authorization).toBe('Bearer token-abc');
	});

	it('omits the Authorization header when no token is provided', async () => {
		mockFetch.mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ items: [], total: 0, offset: 0, limit: 50 })
		} as Response);

		await service.getUserHoldings();

		const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
		expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
	});

	it('returns the paginated UserHolding body', async () => {
		const body = {
			items: [makeHolding('h-1', 'acc-1'), makeHolding('h-2', 'acc-2')],
			total: 2,
			offset: 0,
			limit: 50
		};
		mockFetch.mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);

		const result = await service.getUserHoldings();

		expect(result.items).toHaveLength(2);
		expect(result.items[1].account_id).toBe('acc-2');
		expect(result.items[1].account_name).toBe('Account acc-2');
	});

	it('propagates API errors with the server message', async () => {
		mockFetch.mockResolvedValue({
			ok: false,
			status: 401,
			json: async () => ({ detail: 'Not authenticated' })
		} as Response);

		await expect(service.getUserHoldings()).rejects.toThrow('Not authenticated');
	});
});
