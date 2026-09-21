import { describe, it, expect, vi, beforeEach } from 'vitest';
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

	it('returns only the preferences-derived keys on success', async () => {
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
			holdings_table_config: { widths: Record<string, number>; visible: string[] };
			group_mode: string;
			elliott_waves: typeof mockWaves | null;
		};

		expect(mockGetPreferences).toHaveBeenCalledWith('test-token');
		expect(Object.keys(result).sort()).toEqual([
			'elliott_waves',
			'group_mode',
			'holdings_table_config'
		]);
		expect(result.holdings_table_config.visible).toEqual(['security_symbol', 'quantity']);
		expect(result.group_mode).toBe('stock');
		expect(result.elliott_waves).toEqual(mockWaves);
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
		};

		expect(result.holdings_table_config).toEqual(HOLDINGS_TABLE_DEFAULT_CONFIG);
		expect(result.group_mode).toBe('none');
		expect(result.elliott_waves).toBeNull();
		expect(mockGetUserHoldings).not.toHaveBeenCalled();
	});
});
