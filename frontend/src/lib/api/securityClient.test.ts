import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SecurityClient } from './securityClient';
import { ApiError } from './apiClient';

describe('SecurityClient', () => {
	let client: SecurityClient;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		client = new SecurityClient();
	});

	it('get2FaStatus sends GET request to /auth/2fa/status with optional token', async () => {
		const mockResponse = { totp_enabled: true, recovery_codes_remaining: 8 };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.get2FaStatus('test-token');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/2fa/status'),
			expect.objectContaining({
				method: 'GET',
				headers: expect.objectContaining({
					Authorization: 'Bearer test-token',
					'Content-Type': 'application/json'
				})
			})
		);
	});

	it('setupTotp sends POST request to /auth/2fa/totp/setup', async () => {
		const mockResponse = { secret: 'JBSWY3DPEHPK3PXP', provisioning_uri: 'otpauth://totp/...' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.setupTotp('test-token');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/2fa/totp/setup'),
			expect.objectContaining({
				method: 'POST',
				body: '{}',
				headers: expect.objectContaining({
					Authorization: 'Bearer test-token'
				})
			})
		);
	});

	it('activateTotp sends POST request to /auth/2fa/totp/activate with code', async () => {
		const mockResponse = {
			recovery_codes: ['code1', 'code2'],
			message: 'TOTP two-factor authentication enabled successfully'
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.activateTotp('123456');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/2fa/totp/activate'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ code: '123456' })
			})
		);
	});

	it('disableTotp sends POST request to /auth/2fa/totp/disable', async () => {
		const mockResponse = { message: 'TOTP disabled' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.disableTotp({ code: '123456', password: 'secret' });

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/2fa/totp/disable'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ code: '123456', password: 'secret' })
			})
		);
	});

	it('regenerateRecoveryCodes sends POST request to /auth/2fa/totp/recovery-codes/regenerate', async () => {
		const mockResponse = {
			recovery_codes: ['rc1', 'rc2', 'rc3', 'rc4', 'rc5', 'rc6', 'rc7', 'rc8']
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.regenerateRecoveryCodes();

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/2fa/totp/recovery-codes/regenerate'),
			expect.objectContaining({
				method: 'POST',
				body: '{}'
			})
		);
	});

	it('getPasskeyRegistrationOptions sends POST request to /auth/passkey/register/options', async () => {
		const mockResponse = { challenge: 'test-challenge', rp: { name: 'Retail Portfolio' } };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.getPasskeyRegistrationOptions('test-token');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkey/register/options'),
			expect.objectContaining({
				method: 'POST',
				headers: expect.objectContaining({
					Authorization: 'Bearer test-token'
				})
			})
		);
	});

	it('verifyPasskeyRegistration sends POST request to /auth/passkey/register/verify', async () => {
		const payload = { credential: { id: 'cred-1' }, name: 'My Passkey' };
		const mockResponse = {
			id: 'pk-1',
			name: 'My Passkey',
			created_at: '2026-08-25T10:00:00Z',
			last_used_at: null,
			transports: ['internal']
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.verifyPasskeyRegistration(payload);

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkey/register/verify'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify(payload)
			})
		);
	});

	it('getPasskeys sends GET request to /auth/passkeys', async () => {
		const mockResponse = [
			{
				id: 'pk-1',
				name: 'MacBook',
				created_at: '2026-08-25T10:00:00Z',
				last_used_at: '2026-08-25T12:00:00Z',
				transports: ['internal']
			}
		];
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.getPasskeys();

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkeys'),
			expect.objectContaining({
				method: 'GET'
			})
		);
	});

	it('renamePasskey sends PATCH request to /auth/passkeys/{id}', async () => {
		const mockResponse = {
			id: 'pk-1',
			name: 'Updated Name',
			created_at: '2026-08-25T10:00:00Z',
			last_used_at: null,
			transports: null
		};
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.renamePasskey('pk-1', 'Updated Name');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkeys/pk-1'),
			expect.objectContaining({
				method: 'PATCH',
				body: JSON.stringify({ name: 'Updated Name' })
			})
		);
	});

	it('deletePasskey sends DELETE request to /auth/passkeys/{id}', async () => {
		const mockResponse = { message: 'Passkey deleted successfully' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.deletePasskey('pk-1');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/auth/passkeys/pk-1'),
			expect.objectContaining({
				method: 'DELETE'
			})
		);
	});

	it('propagates ApiError on non-ok responses', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 400,
			json: async () => ({ detail: 'Invalid 2FA verification code' })
		} as Response);

		await expect(client.activateTotp('000000')).rejects.toThrow(ApiError);
		await expect(client.activateTotp('000000')).rejects.toThrow('Invalid 2FA verification code');
	});
});
