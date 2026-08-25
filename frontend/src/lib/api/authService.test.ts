import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthService, authService } from './authService';
import { ApiError } from './apiClient';
import type { AuthenticationResponseJSON } from '@simplewebauthn/browser';

describe('AuthService', () => {
	let service: AuthService;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		service = new AuthService();
	});

	it('exports singleton authService instance', () => {
		expect(authService).toBeInstanceOf(AuthService);
	});

	it('login sends POST request to /auth/login returning AuthResponse', async () => {
		const mockResponse = {
			access_token: 'jwt-token-123',
			token_type: 'bearer',
			user: { id: 'u1', email: 'user@example.com' }
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await service.login({ email: 'user@example.com', password: 'password123' });

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/login'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ email: 'user@example.com', password: 'password123' })
			})
		);
	});

	it('login handles 2FA challenge response', async () => {
		const mockChallenge = {
			requires_2fa: true,
			mfa_token: 'mfa-temp-token-xyz'
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockChallenge
		} as Response);

		const result = await service.login({ email: 'mfa-user@example.com', password: 'password123' });

		expect(result).toEqual(mockChallenge);
		expect(result).toHaveProperty('requires_2fa', true);
		expect(result).toHaveProperty('mfa_token', 'mfa-temp-token-xyz');
	});

	it('loginVerify2Fa sends POST request to /auth/2fa/login-verify', async () => {
		const mockResponse = {
			access_token: 'jwt-token-after-2fa',
			token_type: 'bearer',
			user: { id: 'u1', email: 'user@example.com' }
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await service.loginVerify2Fa({
			mfa_token: 'mfa-temp-token-xyz',
			code: '123456'
		});

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/2fa/login-verify'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ mfa_token: 'mfa-temp-token-xyz', code: '123456' })
			})
		);
	});

	it('getPasskeyAuthOptions sends POST request to /auth/passkey/authenticate/options with optional email', async () => {
		const mockOptions = {
			challenge: 'auth-challenge-123',
			rpId: 'localhost',
			allowCredentials: []
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockOptions
		} as Response);

		const resultWithEmail = await service.getPasskeyAuthOptions({
			email: 'passkey-user@example.com'
		});
		expect(resultWithEmail).toEqual(mockOptions);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkey/authenticate/options'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ email: 'passkey-user@example.com' })
			})
		);

		const resultWithoutEmail = await service.getPasskeyAuthOptions();
		expect(resultWithoutEmail).toEqual(mockOptions);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkey/authenticate/options'),
			expect.objectContaining({
				method: 'POST',
				body: '{}'
			})
		);
	});

	it('verifyPasskeyAuth sends POST request to /auth/passkey/authenticate/verify', async () => {
		const payload = {
			credential: {
				id: 'cred-auth-1',
				rawId: 'raw1',
				response: {
					clientDataJSON: 'xyz',
					authenticatorData: 'abc',
					signature: '123',
					userHandle: 'u1'
				} as unknown as AuthenticationResponseJSON['response'],
				type: 'public-key' as const
			},
			email: 'passkey-user@example.com'
		};
		const mockResponse = {
			access_token: 'jwt-token-passkey',
			token_type: 'bearer',
			user: { id: 'u1', email: 'passkey-user@example.com' }
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await service.verifyPasskeyAuth(payload);

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkey/authenticate/verify'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify(payload)
			})
		);
	});

	it('signup sends POST request to /auth/signup', async () => {
		const mockResponse = { message: 'Signup successful' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await service.signup({ email: 'new@example.com', password: 'password123' });

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/signup'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ email: 'new@example.com', password: 'password123' })
			})
		);
	});

	it('verifyEmail sends POST request to /auth/verify-email', async () => {
		const mockResponse = { message: 'Email verified' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await service.verifyEmail('token-xyz');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/verify-email'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ token: 'token-xyz' })
			})
		);
	});

	it('logout sends POST request to /auth/logout', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({})
		} as Response);

		await service.logout();

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/logout'),
			expect.objectContaining({
				method: 'POST',
				body: '{}'
			})
		);
	});

	it('getWsTicket sends POST request to /auth/ws-ticket', async () => {
		const mockResponse = { ticket: 'ws-ticket-123' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await service.getWsTicket();

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/ws-ticket'),
			expect.objectContaining({
				method: 'POST',
				body: '{}'
			})
		);
	});

	it('propagates ApiError on failed responses', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 401,
			json: async () => ({ detail: 'Invalid 2FA code' })
		} as Response);

		await expect(service.loginVerify2Fa({ mfa_token: 't', code: '000000' })).rejects.toThrow(
			ApiError
		);
		await expect(service.loginVerify2Fa({ mfa_token: 't', code: '000000' })).rejects.toThrow(
			'Invalid 2FA code'
		);
	});
});
