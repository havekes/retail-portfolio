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
});
