import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from '$lib/api/apiClient';
import { HOLDINGS_TABLE_DEFAULT_CONFIG } from '$lib/components/holdings/holdings-table-columns';
import type { Cookies } from '@sveltejs/kit';

const mockGetUserHoldings = vi.fn();
const mockGetPreferences = vi.fn();

vi.mock('$lib/api/accountService', () => ({
	getAccountService: () => ({ getUserHoldings: mockGetUserHoldings })
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	getUserPreferencesService: () => ({ getPreferences: mockGetPreferences })
}));

import { load } from './+page.server';

function createMockCookies(token?: string): Cookies {
	const store = new Map<string, string>();
	if (token) {
		store.set('auth_token', token);
	}
	return {
		get: vi.fn((key: string) => store.get(key)),
		set: vi.fn(),
		delete: vi.fn((key: string) => store.delete(key)),
		getAll: vi.fn(() => []),
		serialize: vi.fn()
	} as unknown as Cookies;
}

function createMockEvent(cookies: Cookies): Parameters<typeof load>[0] {
	return {
		cookies,
		fetch: vi.fn() as unknown as typeof fetch,
		url: new URL('http://localhost/holdings'),
		params: {},
		route: { id: '/holdings' },
		locals: {},
		isDataRequest: false,
		setHeaders: vi.fn(),
		getClientAddress: vi.fn(),
		platform: undefined
	} as unknown as Parameters<typeof load>[0];
}

describe('Holdings +page.server.ts load', () => {
	let cookies: Cookies;

	beforeEach(() => {
		vi.clearAllMocks();
		cookies = createMockCookies('test-token');
	});

	it('returns holdings, holdings_table_config, group_mode, and elliott_waves on success', async () => {
		const holdingItem = {
			id: 'holding-1',
			security_id: 'sec-1',
			security_symbol: 'AAPL',
			account_id: 'acc-1',
			account_name: 'TFSA',
			quantity: 10,
			average_cost: 150,
			latest_price: 175,
			total_value: 1750,
			profit_loss: 250,
			profit_loss_percent: 16.67
		};

		mockGetUserHoldings.mockResolvedValue({
			items: [holdingItem],
			total: 1
		});

		const mockWaves = {
			'sec-1': {
				waves: []
			}
		};

		mockGetPreferences.mockResolvedValue({
			holdings_table: {
				widths: { quantity: 150 },
				visible: ['security_symbol', 'quantity']
			},
			holdings_group: 'stock',
			elliott_waves: mockWaves
		});

		const result = (await load(createMockEvent(cookies))) as {
			holdings: unknown[];
			holdings_table_config: { widths: Record<string, number>; visible: string[] };
			group_mode: string;
			elliott_waves: typeof mockWaves | null;
		};

		expect(mockGetUserHoldings).toHaveBeenCalledWith(0, 50, 'test-token');
		expect(mockGetPreferences).toHaveBeenCalledWith('test-token');
		expect(result.holdings).toEqual([holdingItem]);
		expect(result.holdings_table_config.visible).toEqual(['security_symbol', 'quantity']);
		expect(result.group_mode).toBe('stock');
		expect(result.elliott_waves).toEqual(mockWaves);
	});

	it('paginates holdings until all items are loaded', async () => {
		const firstPageItems = Array.from({ length: 50 }, (_, i) => ({
			id: `h-${i}`,
			security_id: `s-${i}`
		}));
		const secondPageItems = [{ id: 'h-50', security_id: 's-50' }];

		mockGetUserHoldings
			.mockResolvedValueOnce({ items: firstPageItems, total: 51 })
			.mockResolvedValueOnce({ items: secondPageItems, total: 51 });

		mockGetPreferences.mockResolvedValue(null);

		const result = (await load(createMockEvent(cookies))) as { holdings: unknown[] };

		expect(mockGetUserHoldings).toHaveBeenCalledTimes(2);
		expect(mockGetUserHoldings).toHaveBeenNthCalledWith(1, 0, 50, 'test-token');
		expect(mockGetUserHoldings).toHaveBeenNthCalledWith(2, 50, 50, 'test-token');
		expect(result.holdings).toEqual([...firstPageItems, ...secondPageItems]);
	});

	it('falls back gracefully to default table config, flat group mode, and null elliott_waves when preferences fail', async () => {
		mockGetUserHoldings.mockResolvedValue({
			items: [],
			total: 0
		});
		mockGetPreferences.mockRejectedValue(new Error('Preferences service unavailable'));

		const result = (await load(createMockEvent(cookies))) as {
			holdings: unknown[];
			holdings_table_config: unknown;
			group_mode: string;
			elliott_waves: unknown;
		};

		expect(result.holdings).toEqual([]);
		expect(result.holdings_table_config).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
		expect(result.group_mode).toBe('none');
		expect(result.elliott_waves).toBeNull();
	});

	it('clears auth cookie and redirects to login when getUserHoldings throws 401 ApiError', async () => {
		mockGetUserHoldings.mockRejectedValue(new ApiError(401, 'Unauthorized'));

		await expect(load(createMockEvent(cookies))).rejects.toMatchObject({
			status: 303,
			location: '/auth/login?clear_session=true'
		});
		expect(cookies.delete).toHaveBeenCalledWith('auth_token', expect.any(Object));
	});

	it('propagates non-401 ApiError as Kit error', async () => {
		mockGetUserHoldings.mockRejectedValue(new ApiError(503, 'Service Unavailable'));

		await expect(load(createMockEvent(cookies))).rejects.toMatchObject({
			status: 503
		});
	});

	it('propagates unexpected errors as 500 Kit error', async () => {
		mockGetUserHoldings.mockRejectedValue(new Error('Network failure'));

		await expect(load(createMockEvent(cookies))).rejects.toMatchObject({
			status: 500
		});
	});
});
