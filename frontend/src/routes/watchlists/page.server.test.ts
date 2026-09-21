import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Cookies } from '@sveltejs/kit';

const mockGetWatchlists = vi.fn();

vi.mock('$lib/api/marketService', () => ({
	getMarketService: () => ({ getWatchlists: mockGetWatchlists })
}));

import { load } from './+page.server';
import type { PageServerLoad } from './$types';

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

function createMockEvent(cookies: Cookies): Parameters<PageServerLoad>[0] {
	return {
		cookies,
		fetch: vi.fn() as unknown as typeof fetch,
		url: new URL('http://localhost/watchlists'),
		params: {},
		route: { id: '/watchlists' },
		locals: {},
		isDataRequest: false,
		setHeaders: vi.fn(),
		getClientAddress: vi.fn(),
		platform: undefined
	} as unknown as Parameters<PageServerLoad>[0];
}

describe('Watchlists +page.server.ts load', () => {
	let cookies: Cookies;

	beforeEach(() => {
		vi.clearAllMocks();
		cookies = createMockCookies('token-1');
	});

	it('returns an empty watchlist list and never fetches, so the shell renders instantly', async () => {
		const event = createMockEvent(cookies);

		const result = await load(event);

		expect(result).toEqual({ watchlists: [] });
		expect(mockGetWatchlists).not.toHaveBeenCalled();
		expect(event.fetch).not.toHaveBeenCalled();
	});

	it('does not read or delete the auth cookie (no server-side auth handling left)', async () => {
		await load(createMockEvent(cookies));

		expect(cookies.get).not.toHaveBeenCalled();
		expect(cookies.delete).not.toHaveBeenCalled();
	});
});
