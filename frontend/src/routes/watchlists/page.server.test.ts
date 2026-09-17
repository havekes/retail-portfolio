import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from '$lib/api/apiClient';
import type { Cookies } from '@sveltejs/kit';

const mockGetWatchlists = vi.fn();

vi.mock('$lib/api/marketService', () => ({
	getMarketService: () => ({ getWatchlists: mockGetWatchlists })
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
		url: new URL('http://localhost/watchlists'),
		params: {},
		route: { id: '/watchlists' },
		locals: {},
		isDataRequest: false,
		setHeaders: vi.fn(),
		getClientAddress: vi.fn(),
		platform: undefined
	} as unknown as Parameters<typeof load>[0];
}

describe('Watchlists +page.server.ts load', () => {
	let cookies: Cookies;

	beforeEach(() => {
		vi.clearAllMocks();
		cookies = createMockCookies('token-1');
	});

	it('returns the watchlists for the signed-in user', async () => {
		const watchlists = [
			{ id: 'wl-1', user_id: 'user-1', name: 'Default', securities: [] },
			{ id: 'wl-2', user_id: 'user-1', name: 'Tech', securities: [] }
		];
		mockGetWatchlists.mockResolvedValue(watchlists);

		const result = await load(createMockEvent(cookies));

		expect(mockGetWatchlists).toHaveBeenCalledWith('token-1');
		expect(result).toEqual({ watchlists });
	});

	it('clears the auth cookie and redirects to login on 401', async () => {
		mockGetWatchlists.mockRejectedValue(new ApiError(401, 'Unauthorized'));

		await expect(load(createMockEvent(cookies))).rejects.toMatchObject({
			status: 303,
			location: '/auth/login?clear_session=true'
		});
		expect(cookies.delete).toHaveBeenCalledWith('auth_token', expect.any(Object));
	});

	it('surfaces other API errors with their status', async () => {
		mockGetWatchlists.mockRejectedValue(new ApiError(409, 'Watchlist already exists'));

		await expect(load(createMockEvent(cookies))).rejects.toMatchObject({ status: 409 });
	});

	it('returns a 500 for unexpected failures', async () => {
		mockGetWatchlists.mockRejectedValue(new Error('boom'));

		await expect(load(createMockEvent(cookies))).rejects.toMatchObject({ status: 500 });
	});
});
