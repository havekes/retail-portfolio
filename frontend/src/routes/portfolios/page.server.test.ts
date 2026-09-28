import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Cookies } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { Portfolio } from '$lib/types/portfolio';

const mockGetPortfolios = vi.fn();

vi.mock('$lib/api/portfolioClient', () => ({
	getPortfolioClient: () => ({
		getPortfolios: mockGetPortfolios
	})
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

function createMockEvent(cookies: Cookies): Parameters<typeof load>[0] {
	return {
		cookies,
		fetch: vi.fn() as unknown as typeof fetch,
		url: new URL('http://localhost/portfolios'),
		params: {},
		route: { id: '/portfolios' },
		locals: {},
		isDataRequest: false,
		setHeaders: vi.fn(),
		getClientAddress: vi.fn(),
		platform: undefined
	} as unknown as Parameters<typeof load>[0];
}

describe('/portfolios +page.server.ts load', () => {
	let cookies: Cookies;

	beforeEach(() => {
		vi.clearAllMocks();
		cookies = createMockCookies('test-token');
	});

	it('returns portfolios on successful load', async () => {
		const mockPortfolios: Portfolio[] = [
			{
				id: 'port-1',
				name: 'Retirement',
				accounts: [],
				created_at: '2026-01-01T00:00:00Z'
			}
		];
		mockGetPortfolios.mockResolvedValueOnce(mockPortfolios);

		const result = (await load(createMockEvent(cookies))) as { portfolios: Portfolio[] };

		expect(mockGetPortfolios).toHaveBeenCalledWith('test-token');
		expect(result).toEqual({ portfolios: mockPortfolios });
	});

	it('deletes auth cookie and redirects on 401 ApiError', async () => {
		mockGetPortfolios.mockRejectedValueOnce(new ApiError(401, 'Unauthorized'));

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

	it('throws HttpError with status and message on non-401 ApiError', async () => {
		mockGetPortfolios.mockRejectedValueOnce(new ApiError(403, 'Forbidden'));

		try {
			await load(createMockEvent(cookies));
			expect.unreachable('Should have thrown error');
		} catch (err: unknown) {
			expect(err).toMatchObject({
				status: 403,
				body: { message: 'Forbidden' }
			});
		}
	});

	it('throws 500 HttpError on unexpected error', async () => {
		mockGetPortfolios.mockRejectedValueOnce(new Error('Database exploded'));

		try {
			await load(createMockEvent(cookies));
			expect.unreachable('Should have thrown error');
		} catch (err: unknown) {
			expect(err).toMatchObject({
				status: 500,
				body: { message: 'Internal Server Error' }
			});
		}
	});
});
