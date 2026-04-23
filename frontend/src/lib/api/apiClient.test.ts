import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient, ApiError } from './apiClient';

// Concrete implementation for testing
class TestClient extends ApiClient {
	async testGet() {
		return this.get('/test');
	}
}

describe('ApiClient', () => {
	let client: TestClient;

	beforeEach(() => {
		client = new TestClient();
		vi.clearAllMocks();
		global.fetch = vi.fn();
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
