import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient, ApiError } from './apiClient';

// Concrete implementation for testing
class TestClient extends ApiClient {
	async testGet() {
		return this.get('/test');
	}

	async testPut(payload: { name: string }) {
		return this.put<{ success: boolean }, typeof payload>('/test', payload);
	}
}

describe('ApiClient', () => {
	let client: TestClient;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		client = new TestClient();
	});

	it('should send PUT request correctly', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ success: true })
		} as Response);

		const result = await client.testPut({ name: 'test' });
		expect(result).toEqual({ success: true });
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/test'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify({ name: 'test' })
			})
		);
	});

	it('should throw ApiError on 401', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 401,
			json: async () => ({ detail: 'Unauthorized' })
		} as Response);

		await expect(client.testGet()).rejects.toThrow(ApiError);
	});

	it('should throw ApiError on 404', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 404,
			json: async () => ({ detail: 'Not Found' })
		} as Response);

		await expect(client.testGet()).rejects.toThrow(ApiError);
	});
});
