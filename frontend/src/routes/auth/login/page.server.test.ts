import { describe, it, expect, vi, beforeEach } from 'vitest';
import { actions } from './+page.server';
import { ApiError } from '$lib/api/apiClient';
import type { Cookies } from '@sveltejs/kit';
import type { RequestEvent } from './$types';

const mockLogin = vi.fn();
const mockLoginVerify2Fa = vi.fn();
const mockVerifyPasskeyAuth = vi.fn();

vi.mock('$lib/api/authService', () => {
	class MockAuthService {
		login = mockLogin;
		loginVerify2Fa = mockLoginVerify2Fa;
		verifyPasskeyAuth = mockVerifyPasskeyAuth;
	}
	return {
		AuthService: MockAuthService
	};
});

function createMockCookies(): Cookies {
	const store = new Map<string, { value: string; opts: Record<string, unknown> }>();
	return {
		set: vi.fn((key: string, value: string, opts: Record<string, unknown>) => {
			store.set(key, { value, opts });
		}),
		get: vi.fn((key: string) => store.get(key)?.value),
		delete: vi.fn((key: string) => store.delete(key)),
		getAll: vi.fn(() => []),
		serialize: vi.fn()
	} as unknown as Cookies;
}

function createMockRequest(formDataMap: Record<string, string>): Request {
	const formData = new FormData();
	for (const [k, v] of Object.entries(formDataMap)) {
		formData.append(k, v);
	}
	return {
		formData: vi.fn().mockResolvedValue(formData)
	} as unknown as Request;
}

function createMockEvent(request: Request, cookies: Cookies, fetchFn: typeof fetch): RequestEvent {
	return {
		request,
		cookies,
		fetch: fetchFn,
		url: new URL('http://localhost/auth/login'),
		params: {},
		route: { id: '/auth/login' },
		locals: {},
		isDataRequest: false,
		setHeaders: vi.fn(),
		getClientAddress: vi.fn(),
		platform: undefined
	} as unknown as RequestEvent;
}

describe('Login +page.server.ts actions', () => {
	let cookies: Cookies;
	const mockFetch = vi.fn() as unknown as typeof fetch;

	beforeEach(() => {
		vi.clearAllMocks();
		cookies = createMockCookies();
	});

	describe('login action', () => {
		it('returns fail(400) when email or password is missing', async () => {
			const req = createMockRequest({ email: '', password: '' });
			const event = createMockEvent(req, cookies, mockFetch);
			const result = await actions.login(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 400,
					data: expect.objectContaining({
						message: 'Email and password are required'
					})
				})
			);
			expect(mockLogin).not.toHaveBeenCalled();
		});

		it('sets auth_token cookie and redirects on successful single-factor password login', async () => {
			mockLogin.mockResolvedValue({
				access_token: 'access-token-123',
				token_type: 'bearer',
				user: { id: 'u1', email: 'test@example.com' }
			});

			const req = createMockRequest({ email: 'test@example.com', password: 'password123' });
			const event = createMockEvent(req, cookies, mockFetch);

			await expect(actions.login(event)).rejects.toMatchObject({
				status: 303,
				location: '/'
			});

			expect(cookies.set).toHaveBeenCalledWith(
				'auth_token',
				'access-token-123',
				expect.objectContaining({
					path: '/',
					httpOnly: true,
					sameSite: 'lax'
				})
			);
		});

		it('returns requires2fa response when login requires 2FA challenge', async () => {
			mockLogin.mockResolvedValue({
				requires_2fa: true,
				mfa_token: 'mfa-session-token-abc'
			});

			const req = createMockRequest({ email: '2fa-user@example.com', password: 'password123' });
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.login(event);

			expect(result).toEqual({
				requires2fa: true,
				mfaToken: 'mfa-session-token-abc',
				email: '2fa-user@example.com'
			});
			expect(cookies.set).not.toHaveBeenCalled();
		});

		it('returns fail(403) with unverified email message when API returns 403', async () => {
			mockLogin.mockRejectedValue(new ApiError(403, 'Email not verified'));

			const req = createMockRequest({ email: 'unverified@example.com', password: 'password123' });
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.login(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 403,
					data: expect.objectContaining({
						email: 'unverified@example.com',
						message: 'Email not verified. Please check your inbox for a verification link.'
					})
				})
			);
		});

		it('returns fail(401) on invalid credentials', async () => {
			mockLogin.mockRejectedValue(new ApiError(401, 'Invalid credentials'));

			const req = createMockRequest({ email: 'wrong@example.com', password: 'badpassword' });
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.login(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 401,
					data: expect.objectContaining({
						email: 'wrong@example.com',
						message: 'Invalid credentials'
					})
				})
			);
		});
	});

	describe('verify2fa action', () => {
		it('returns fail(400) when mfaToken or code is missing', async () => {
			const req = createMockRequest({ mfaToken: '', code: '' });
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.verify2fa(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 400,
					data: expect.objectContaining({
						requires2fa: true,
						message: 'Verification code is required'
					})
				})
			);
			expect(mockLoginVerify2Fa).not.toHaveBeenCalled();
		});

		it('sets auth_token cookie and redirects on successful 2FA TOTP or recovery verification', async () => {
			mockLoginVerify2Fa.mockResolvedValue({
				access_token: 'access-token-after-2fa',
				token_type: 'bearer',
				user: { id: 'u1', email: 'test@example.com' }
			});

			const req = createMockRequest({
				mfaToken: 'mfa-token-123',
				code: '123456',
				email: 'test@example.com'
			});
			const event = createMockEvent(req, cookies, mockFetch);

			await expect(actions.verify2fa(event)).rejects.toMatchObject({
				status: 303,
				location: '/'
			});

			expect(mockLoginVerify2Fa).toHaveBeenCalledWith({
				mfa_token: 'mfa-token-123',
				code: '123456'
			});
			expect(cookies.set).toHaveBeenCalledWith(
				'auth_token',
				'access-token-after-2fa',
				expect.objectContaining({
					path: '/',
					httpOnly: true,
					sameSite: 'lax'
				})
			);
		});

		it('returns fail(401) on invalid 2FA code', async () => {
			mockLoginVerify2Fa.mockRejectedValue(new ApiError(401, 'Invalid 2FA code'));

			const req = createMockRequest({
				mfaToken: 'mfa-token-123',
				code: '000000',
				email: 'test@example.com'
			});
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.verify2fa(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 401,
					data: expect.objectContaining({
						requires2fa: true,
						mfaToken: 'mfa-token-123',
						email: 'test@example.com',
						message: 'Invalid 2FA code'
					})
				})
			);
		});
	});

	describe('passkeyLogin action', () => {
		it('returns fail(400) when credential string is missing', async () => {
			const req = createMockRequest({ credential: '' });
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.passkeyLogin(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 400,
					data: expect.objectContaining({
						message: 'Passkey credential is required'
					})
				})
			);
			expect(mockVerifyPasskeyAuth).not.toHaveBeenCalled();
		});

		it('returns fail(400) on malformed credential JSON', async () => {
			const req = createMockRequest({ credential: 'not-valid-json' });
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.passkeyLogin(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 400,
					data: expect.objectContaining({
						message: 'Invalid credential payload'
					})
				})
			);
			expect(mockVerifyPasskeyAuth).not.toHaveBeenCalled();
		});

		it('sets auth_token cookie and redirects on successful passkey assertion verification', async () => {
			mockVerifyPasskeyAuth.mockResolvedValue({
				access_token: 'access-token-passkey',
				token_type: 'bearer',
				user: { id: 'u1', email: 'passkey@example.com' }
			});

			const credentialObj = {
				id: 'cred-1',
				rawId: 'raw1',
				response: { clientDataJSON: 'xyz' },
				type: 'public-key'
			};

			const req = createMockRequest({
				credential: JSON.stringify(credentialObj),
				email: 'passkey@example.com'
			});
			const event = createMockEvent(req, cookies, mockFetch);

			await expect(actions.passkeyLogin(event)).rejects.toMatchObject({
				status: 303,
				location: '/'
			});

			expect(mockVerifyPasskeyAuth).toHaveBeenCalledWith({
				credential: credentialObj,
				email: 'passkey@example.com'
			});
			expect(cookies.set).toHaveBeenCalledWith(
				'auth_token',
				'access-token-passkey',
				expect.objectContaining({
					path: '/',
					httpOnly: true,
					sameSite: 'lax'
				})
			);
		});

		it('returns fail(400) on passkey verification failure', async () => {
			mockVerifyPasskeyAuth.mockRejectedValue(new ApiError(400, 'Passkey verification failed'));

			const req = createMockRequest({
				credential: JSON.stringify({ id: 'bad-cred' }),
				email: 'passkey@example.com'
			});
			const event = createMockEvent(req, cookies, mockFetch);

			const result = await actions.passkeyLogin(event);

			expect(result).toEqual(
				expect.objectContaining({
					status: 400,
					data: expect.objectContaining({
						message: 'Passkey verification failed'
					})
				})
			);
		});
	});
});
