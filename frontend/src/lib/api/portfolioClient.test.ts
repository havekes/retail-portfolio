import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PortfolioClient, getPortfolioClient } from './portfolioClient';
import type { Portfolio, PortfolioCreatePayload } from '@/types/portfolio';
import { ApiError } from './apiClient';

describe('PortfolioClient', () => {
	let client: PortfolioClient;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		client = new PortfolioClient();
	});

	it('should send Authorization header when token is provided to getPortfolios', async () => {
		const mockPortfolios: Portfolio[] = [{ id: 'port-1', name: 'Retirement', accounts: [] }];
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockPortfolios
		} as Response);

		const result = await client.getPortfolios('secret-token');

		expect(result).toEqual(mockPortfolios);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/portfolios/'),
			expect.objectContaining({
				method: 'GET',
				headers: expect.objectContaining({
					Authorization: 'Bearer secret-token',
					'Content-Type': 'application/json'
				})
			})
		);
	});

	it('should not send Authorization header when token is omitted from getPortfolios', async () => {
		const mockPortfolios: Portfolio[] = [{ id: 'port-1', name: 'Retirement', accounts: [] }];
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => mockPortfolios
		} as Response);

		const result = await client.getPortfolios();

		expect(result).toEqual(mockPortfolios);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/portfolios/'),
			expect.objectContaining({
				method: 'GET',
				headers: expect.not.objectContaining({
					Authorization: expect.any(String)
				})
			})
		);
	});

	it('should throw ApiError when getPortfolios fails', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 500,
			json: async () => ({ detail: 'Internal server error' })
		} as Response);

		await expect(client.getPortfolios('token')).rejects.toThrow(ApiError);
	});

	it('should send POST to /portfolios/ with payload and token in createPortfolio', async () => {
		const payload: PortfolioCreatePayload = {
			name: 'Growth',
			accounts: ['acc-1', 'acc-2']
		};
		const created: Portfolio = {
			id: 'port-2',
			name: 'Growth',
			accounts: []
		};

		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => created
		} as Response);

		const result = await client.createPortfolio(payload, 'token-123');

		expect(result).toEqual(created);
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/portfolios/'),
			expect.objectContaining({
				method: 'POST',
				headers: expect.objectContaining({
					Authorization: 'Bearer token-123',
					'Content-Type': 'application/json'
				}),
				body: JSON.stringify(payload)
			})
		);
	});

	it('getPortfolioClient returns a client using custom fetch', async () => {
		const customFetch = vi.fn().mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => []
		} as unknown as Response);

		const customClient = getPortfolioClient(customFetch);
		await customClient.getPortfolios();

		expect(customFetch).toHaveBeenCalledTimes(1);
	});
});
