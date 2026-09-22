import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Cookies } from '@sveltejs/kit';

const mockGetSecurity = vi.fn();
const mockGetPrices = vi.fn();

vi.mock('$lib/api/marketService', () => ({
	getMarketService: () => ({
		getSecurity: mockGetSecurity,
		getPrices: mockGetPrices
	})
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

function createMockEvent(params: Record<string, string>): Parameters<typeof load>[0] {
	return {
		cookies: createMockCookies('test-token'),
		fetch: vi.fn() as unknown as typeof fetch,
		url: new URL('http://localhost/security/sec-1'),
		params,
		route: { id: '/security/[security_id]' },
		locals: {},
		isDataRequest: false,
		setHeaders: vi.fn(),
		getClientAddress: vi.fn(),
		platform: undefined
	} as unknown as Parameters<typeof load>[0];
}

describe('Security +page.server.ts load', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('returns only the route identity so the shell can render instantly', async () => {
		const result = (await load(createMockEvent({ security_id: 'sec-1' }))) as {
			security_id: string;
		};

		expect(Object.keys(result)).toEqual(['security_id']);
		expect(result.security_id).toBe('sec-1');
	});

	it('never loads the security or its prices in the server load', async () => {
		await load(createMockEvent({ security_id: 'sec-1' }));

		expect(mockGetSecurity).not.toHaveBeenCalled();
		expect(mockGetPrices).not.toHaveBeenCalled();
	});

	it('throws a 400 when the security_id param is missing', async () => {
		await expect(load(createMockEvent({}))).rejects.toMatchObject({
			status: 400,
			body: { message: 'Security ID is required' }
		});
	});
});
