import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AccountClient } from './accountClient';

describe('AccountClient', () => {
	let client: AccountClient;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		client = new AccountClient();
	});

	it('should send Authorization header when token is provided to renameAccount', async () => {
		const mockResponse = { id: 'acc-1', name: 'New Name' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		const result = await client.renameAccount('acc-1', 'New Name', 'secret-token');

		expect(result).toEqual(mockResponse);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/acc-1/rename'),
			expect.objectContaining({
				method: 'PATCH',
				headers: expect.objectContaining({
					Authorization: 'Bearer secret-token',
					'Content-Type': 'application/json'
				})
			})
		);
	});

	it('should not send Authorization header when token is omitted from renameAccount', async () => {
		const mockResponse = { id: 'acc-1', name: 'New Name' };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockResponse
		} as Response);

		await client.renameAccount('acc-1', 'New Name');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/acc-1/rename'),
			expect.objectContaining({
				method: 'PATCH',
				headers: expect.not.objectContaining({
					Authorization: expect.any(String)
				})
			})
		);
	});

	it('should send FormData with file to /accounts/:id/csv-sync', async () => {
		const mockAccount = { id: 'acc-1', name: 'Test Account', api_sync_enabled: false };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockAccount
		} as Response);

		const file = new File(['symbol,quantity\nAAPL,10'], 'transactions.csv', {
			type: 'text/csv'
		});
		const result = await client.syncAccountCsv('acc-1', file);

		expect(result).toEqual(mockAccount);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/acc-1/csv-sync'),
			expect.objectContaining({
				method: 'POST',
				body: expect.any(FormData)
			})
		);

		const call = vi.mocked(global.fetch).mock.calls[0];
		const formData = call[1]?.body as FormData;
		expect(formData.get('file')).toBe(file);
	});

	it('should send Authorization header when token is provided to syncAccountCsv', async () => {
		const mockAccount = { id: 'acc-1', name: 'Test Account', api_sync_enabled: false };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockAccount
		} as Response);

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		await client.syncAccountCsv('acc-1', file, 'secret-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/acc-1/csv-sync'),
			expect.objectContaining({
				method: 'POST',
				headers: expect.objectContaining({
					Authorization: 'Bearer secret-token'
				})
			})
		);
	});

	it('should not send Authorization header when token is omitted from syncAccountCsv', async () => {
		const mockAccount = { id: 'acc-1', name: 'Test Account', api_sync_enabled: false };
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockAccount
		} as Response);

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		await client.syncAccountCsv('acc-1', file);

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/accounts/acc-1/csv-sync'),
			expect.objectContaining({
				method: 'POST',
				headers: expect.not.objectContaining({
					Authorization: expect.any(String)
				})
			})
		);
	});

	it('should throw ApiError when syncAccountCsv request fails', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 400,
			json: async () => ({ detail: 'Account number mismatch' })
		} as Response);

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		await expect(client.syncAccountCsv('acc-1', file)).rejects.toThrow('Account number mismatch');
	});
});
