import { describe, it, expect, vi, beforeEach } from 'vitest';
import { HOLDINGS_TABLE_DEFAULT_CONFIG } from '$lib/components/holdings/holdings-table-columns';
import type { Cookies } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { Portfolio } from '$lib/types/portfolio';
import type { Account } from '$lib/types/account';

const mockGetUserHoldings = vi.fn();
const mockGetPreferences = vi.fn();
const mockGetPortfolios = vi.fn();
const mockGetAccounts = vi.fn();

vi.mock('$lib/api/accountService', () => ({
	getAccountService: () => ({ getUserHoldings: mockGetUserHoldings })
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	getUserPreferencesService: () => ({ getPreferences: mockGetPreferences })
}));

vi.mock('$lib/api/portfolioClient', () => ({
	getPortfolioClient: () => ({ getPortfolios: mockGetPortfolios })
}));

vi.mock('$lib/api/accountClient', () => ({
	getAccountClient: () => ({ getAccounts: mockGetAccounts })
}));

const mockDeleteAuthCookie = vi.fn();
vi.mock('$lib/server/auth-cookie', () => ({
	deleteAuthCookie: (...args: unknown[]) => mockDeleteAuthCookie(...args)
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

function createMockEvent(
	cookies: Cookies,
	url = new URL('http://localhost/holdings')
): Parameters<typeof load>[0] {
	return {
		cookies,
		fetch: vi.fn() as unknown as typeof fetch,
		url,
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
		mockGetPortfolios.mockResolvedValue([]);
		mockGetAccounts.mockResolvedValue([]);
	});

	it('returns expected keys on success', async () => {
		const mockWaves = {
			'sec-1': {
				waves: []
			}
		};

		const mockPortfolios: Portfolio[] = [{ id: 'p1', name: 'Main', accounts: [] }];
		const mockAccounts: Account[] = [
			{
				id: 'a1',
				name: 'TFSA',
				external_id: 'e1',
				account_type_id: 1,
				institution_id: 1,
				currency: 'CAD',
				is_active: true,
				api_sync_enabled: false,
				created_at: new Date()
			}
		];

		mockGetPreferences.mockResolvedValue({
			holdings_table: {
				widths: { quantity: 150 },
				visible: ['security_symbol', 'quantity']
			},
			holdings_group: 'stock',
			elliott_waves: mockWaves
		});
		mockGetPortfolios.mockResolvedValue(mockPortfolios);
		mockGetAccounts.mockResolvedValue(mockAccounts);

		const url = new URL('http://localhost/holdings?portfolio_id=p1&account_id=a1');
		const result = (await load(createMockEvent(cookies, url))) as {
			holdings_table_config: { widths: Record<string, number>; visible: string[] };
			group_mode: string;
			elliott_waves: typeof mockWaves | null;
			portfolios: Portfolio[];
			accounts: Account[];
			portfolio_id: string | null;
			account_id: string | null;
		};

		expect(mockGetPreferences).toHaveBeenCalledWith('test-token');
		expect(mockGetPortfolios).toHaveBeenCalledWith('test-token');
		expect(mockGetAccounts).toHaveBeenCalledWith('test-token');
		expect(Object.keys(result).sort()).toEqual([
			'account_id',
			'accounts',
			'elliott_waves',
			'group_mode',
			'holdings_table_config',
			'portfolio_id',
			'portfolios'
		]);
		expect(result.holdings_table_config.visible).toEqual(['security_symbol', 'quantity']);
		expect(result.group_mode).toBe('stock');
		expect(result.elliott_waves).toEqual(mockWaves);
		expect(result.portfolios).toEqual(mockPortfolios);
		expect(result.accounts).toEqual(mockAccounts);
		expect(result.portfolio_id).toBe('p1');
		expect(result.account_id).toBe('a1');
	});

	it('never loads holdings in the server load', async () => {
		mockGetPreferences.mockResolvedValue(null);

		await load(createMockEvent(cookies));

		expect(mockGetUserHoldings).not.toHaveBeenCalled();
	});

	it('falls back gracefully to default table config, flat group mode, and null elliott_waves when preferences fail', async () => {
		mockGetPreferences.mockRejectedValue(new Error('Preferences service unavailable'));

		const result = (await load(createMockEvent(cookies))) as {
			holdings_table_config: unknown;
			group_mode: string;
			elliott_waves: unknown;
			portfolios: unknown[];
			accounts: unknown[];
		};

		expect(result.holdings_table_config).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
		expect(result.group_mode).toBe('none');
		expect(result.elliott_waves).toBeNull();
		expect(result.portfolios).toEqual([]);
		expect(result.accounts).toEqual([]);
		expect(mockGetUserHoldings).not.toHaveBeenCalled();
	});

	it('redirects to login on 401 ApiError from any service', async () => {
		mockGetPreferences.mockResolvedValue(null);
		mockGetPortfolios.mockRejectedValue(new ApiError(401, 'Unauthorized'));

		try {
			await load(createMockEvent(cookies));
			expect.unreachable('Should have thrown redirect');
		} catch (err: unknown) {
			expect(mockDeleteAuthCookie).toHaveBeenCalledWith(cookies);
			expect(err).toMatchObject({
				status: 303,
				location: '/auth/login?clear_session=true'
			});
		}
	});
});
