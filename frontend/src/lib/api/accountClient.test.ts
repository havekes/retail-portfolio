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

	describe('inspectCsv', () => {
		it('should send FormData with file and institution_id to /accounts/csv/inspect', async () => {
			const mockDiscoveredAccounts = [
				{
					account_number: 'W123456789',
					account_name: 'My TFSA',
					account_type_id: 1,
					account_type_name: 'TFSA',
					currency: 'CAD',
					positions_count: 1
				}
			];
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => mockDiscoveredAccounts
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			const result = await client.inspectCsv(1, file);

			expect(result).toEqual(mockDiscoveredAccounts);
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/accounts/csv/inspect'),
				expect.objectContaining({
					method: 'POST',
					body: expect.any(FormData)
				})
			);

			const call = vi.mocked(global.fetch).mock.calls[0];
			const formData = call[1]?.body as FormData;
			expect(formData.get('file')).toBe(file);
			expect(formData.get('institution_id')).toBe('1');
		});

		it('should send Authorization header when token is provided to inspectCsv', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => []
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			await client.inspectCsv('inst-1', file, 'secret-token');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/accounts/csv/inspect'),
				expect.objectContaining({
					method: 'POST',
					headers: expect.objectContaining({
						Authorization: 'Bearer secret-token'
					})
				})
			);
		});

		it('should not send Authorization header when token is omitted from inspectCsv', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => []
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			await client.inspectCsv('inst-1', file);

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/accounts/csv/inspect'),
				expect.objectContaining({
					method: 'POST',
					headers: expect.not.objectContaining({
						Authorization: expect.any(String)
					})
				})
			);
		});

		it('should throw ApiError when inspectCsv request fails', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 400,
				json: async () => ({ detail: 'Invalid CSV format' })
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			await expect(client.inspectCsv(1, file)).rejects.toThrow('Invalid CSV format');
		});
	});

	describe('importAccountsCsv', () => {
		it('should send FormData with file, institution_id, and repeated account_numbers to /accounts/csv/import', async () => {
			const mockAccounts = [{ id: 'acc-1', name: 'Imported TFSA' }];
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => mockAccounts
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			const result = await client.importAccountsCsv(1, file, ['W123456789', 'W987654321']);

			expect(result).toEqual(mockAccounts);
			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/accounts/csv/import'),
				expect.objectContaining({
					method: 'POST',
					body: expect.any(FormData)
				})
			);

			const call = vi.mocked(global.fetch).mock.calls[0];
			const formData = call[1]?.body as FormData;
			expect(formData.get('file')).toBe(file);
			expect(formData.get('institution_id')).toBe('1');
			expect(formData.getAll('account_numbers')).toEqual(['W123456789', 'W987654321']);
		});

		it('should send Authorization header when token is provided to importAccountsCsv', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => []
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			await client.importAccountsCsv('inst-1', file, ['W123'], 'secret-token');

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/accounts/csv/import'),
				expect.objectContaining({
					method: 'POST',
					headers: expect.objectContaining({
						Authorization: 'Bearer secret-token'
					})
				})
			);
		});

		it('should not send Authorization header when token is omitted from importAccountsCsv', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				status: 200,
				json: async () => []
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			await client.importAccountsCsv('inst-1', file, ['W123']);

			expect(global.fetch).toHaveBeenCalledWith(
				expect.stringContaining('/accounts/csv/import'),
				expect.objectContaining({
					method: 'POST',
					headers: expect.not.objectContaining({
						Authorization: expect.any(String)
					})
				})
			);
		});

		it('should throw ApiError when importAccountsCsv request fails', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 400,
				json: async () => ({ detail: 'Account already exists' })
			} as Response);

			const file = new File(['content'], 'test.csv', { type: 'text/csv' });
			await expect(client.importAccountsCsv(1, file, ['W123'])).rejects.toThrow(
				'Account already exists'
			);
		});
	});
});
