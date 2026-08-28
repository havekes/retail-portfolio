// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SignJWT } from 'jose';
import type { Cookies, RequestEvent } from '@sveltejs/kit';
import { AUTH_COOKIE_OPTS } from '$lib/server/auth-cookie';

const TEST_SECRET_STR = 'test-secret-key-12345678901234567890';
const TEST_SECRET = new TextEncoder().encode(TEST_SECRET_STR);
const OTHER_SECRET = new TextEncoder().encode('wrong-secret-key-09876543210987654321');

vi.mock('$env/static/private', () => ({
	JWT_SECRET: 'test-secret-key-12345678901234567890'
}));

import { handle } from './hooks.server';

function createMockCookies(initialCookies: Record<string, string> = {}): Cookies {
	const store = new Map<string, string>(Object.entries(initialCookies));
	return {
		get: vi.fn((key: string) => store.get(key)),
		set: vi.fn((key: string, value: string) => store.set(key, value)),
		delete: vi.fn((key: string) => store.delete(key)),
		getAll: vi.fn(() => Array.from(store.entries()).map(([name, value]) => ({ name, value }))),
		serialize: vi.fn()
	} as unknown as Cookies;
}

function createMockEvent(
	pathname: string,
	cookies: Cookies,
	searchParams: string = ''
): RequestEvent {
	const url = new URL(`http://localhost${pathname}${searchParams ? `?${searchParams}` : ''}`);
	return {
		url,
		cookies,
		locals: { user: null },
		request: new Request(url),
		params: {},
		route: { id: pathname },
		isDataRequest: false,
		isSubRequest: false,
		fetch: vi.fn()
	} as unknown as RequestEvent;
}

async function createSignedToken(
	payload: Record<string, unknown>,
	options: { exp?: string | number; sub?: string; secret?: Uint8Array } = {}
): Promise<string> {
	let jwt = new SignJWT(payload)
		.setProtectedHeader({ alg: 'HS256' })
		.setSubject(options.sub ?? 'user@example.com');

	if (options.exp !== undefined) {
		jwt = jwt.setExpirationTime(options.exp);
	} else {
		jwt = jwt.setExpirationTime('2h');
	}

	return jwt.sign(options.secret ?? TEST_SECRET);
}

describe('hooks.server.ts handle', () => {
	const mockResolve = vi.fn().mockImplementation(async () => {
		return new Response('OK', { status: 200 });
	});

	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('Scope verification (ARCH-T09)', () => {
		it('rejects mfa_pending tokens, deletes cookie, and leaves locals.user as null', async () => {
			const mfaToken = await createSignedToken({
				user_id: 'user-123',
				scope: 'mfa_pending'
			});

			const cookies = createMockCookies({ auth_token: mfaToken });
			const event = createMockEvent('/dashboard', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(event.locals.user).toBeNull();
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
		});

		it('allows access-scope tokens and populates locals.user', async () => {
			const accessToken = await createSignedToken(
				{
					user_id: 'user-123',
					scope: 'access'
				},
				{ sub: 'test@example.com' }
			);

			const cookies = createMockCookies({ auth_token: accessToken });
			const event = createMockEvent('/dashboard', cookies);

			const response = await handle({ event, resolve: mockResolve });

			expect(response.status).toBe(200);
			expect(event.locals.user).toEqual({
				id: 'user-123',
				email: 'test@example.com'
			});
			expect(cookies.delete).not.toHaveBeenCalled();
			expect(mockResolve).toHaveBeenCalledWith(event);
		});

		it('rejects tokens with missing scope or arbitrary scopes', async () => {
			const noScopeToken = await createSignedToken({
				user_id: 'user-123'
			});

			const cookies = createMockCookies({ auth_token: noScopeToken });
			const event = createMockEvent('/dashboard', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(event.locals.user).toBeNull();
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
		});

		it('rejects tokens with refresh or invalid scope strings', async () => {
			const refreshScopeToken = await createSignedToken({
				user_id: 'user-123',
				scope: 'refresh'
			});

			const cookies = createMockCookies({ auth_token: refreshScopeToken });
			const event = createMockEvent('/dashboard', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(event.locals.user).toBeNull();
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
		});
	});

	describe('Expiration and validity verification', () => {
		it('clears cookie and redirects when token is expired', async () => {
			const expiredToken = await createSignedToken(
				{
					user_id: 'user-123',
					scope: 'access'
				},
				{ exp: '-10s' }
			);

			const cookies = createMockCookies({ auth_token: expiredToken });
			const event = createMockEvent('/dashboard', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(event.locals.user).toBeNull();
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
		});

		it('clears cookie and redirects when token is signed with a different secret', async () => {
			const invalidSecretToken = await createSignedToken(
				{
					user_id: 'user-123',
					scope: 'access'
				},
				{ secret: OTHER_SECRET }
			);

			const cookies = createMockCookies({ auth_token: invalidSecretToken });
			const event = createMockEvent('/dashboard', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(event.locals.user).toBeNull();
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
		});

		it('clears cookie and redirects on malformed token strings', async () => {
			const cookies = createMockCookies({ auth_token: 'not-a-valid-jwt-token' });
			const event = createMockEvent('/dashboard', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(event.locals.user).toBeNull();
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
		});
	});

	describe('Route guard and navigation rules', () => {
		it('redirects unauthenticated users to /auth/login on protected routes', async () => {
			const cookies = createMockCookies();
			const event = createMockEvent('/settings/profile', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/auth/login'
			});

			expect(mockResolve).not.toHaveBeenCalled();
		});

		it('allows unauthenticated users to access /auth/* routes without redirect', async () => {
			const cookies = createMockCookies();
			const event = createMockEvent('/auth/login', cookies);

			const response = await handle({ event, resolve: mockResolve });

			expect(response.status).toBe(200);
			expect(mockResolve).toHaveBeenCalledWith(event);
		});

		it('redirects authenticated users away from /auth/login to /', async () => {
			const accessToken = await createSignedToken({
				user_id: 'user-123',
				scope: 'access'
			});

			const cookies = createMockCookies({ auth_token: accessToken });
			const event = createMockEvent('/auth/login', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/'
			});
		});

		it('redirects authenticated users away from /auth/signup to /', async () => {
			const accessToken = await createSignedToken({
				user_id: 'user-123',
				scope: 'access'
			});

			const cookies = createMockCookies({ auth_token: accessToken });
			const event = createMockEvent('/auth/signup', cookies);

			await expect(handle({ event, resolve: mockResolve })).rejects.toMatchObject({
				status: 303,
				location: '/'
			});
		});

		it('clears session when clear_session=true query parameter is present on login page', async () => {
			const accessToken = await createSignedToken({
				user_id: 'user-123',
				scope: 'access'
			});

			const cookies = createMockCookies({ auth_token: accessToken });
			const event = createMockEvent('/auth/login', cookies, 'clear_session=true');

			const response = await handle({ event, resolve: mockResolve });

			expect(response.status).toBe(200);
			expect(cookies.delete).toHaveBeenCalledWith('auth_token', AUTH_COOKIE_OPTS);
			expect(event.locals.user).toBeNull();
			expect(mockResolve).toHaveBeenCalledWith(event);
		});
	});
});
