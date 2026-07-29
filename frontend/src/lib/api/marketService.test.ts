import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MarketService } from './marketService';

describe('MarketService', () => {
	let service: MarketService;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		service = new MarketService();
	});

	it('should call getPrices with default interval 1d and from/to dates', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				security_id: 'sec-123',
				from_date: '2026-01-01',
				to_date: '2026-07-29',
				items: [],
				total: 0,
				offset: 0,
				limit: 50
			})
		} as Response);

		await service.getPrices('sec-123', '2026-01-01', '2026-07-29');

		expect(global.fetch).toHaveBeenCalledWith(
			'/api/v1/market/prices/sec-123?interval=1d&from_date=2026-01-01&to_date=2026-07-29',
			expect.objectContaining({ method: 'GET' })
		);
	});

	it('should call getPrices with 1h intraday interval without dates', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				security_id: 'sec-123',
				items: [
					{
						id: 1,
						security_id: 'sec-123',
						timestamp: '2026-07-29T12:00:00Z',
						open: 100,
						high: 105,
						low: 99,
						close: 104,
						volume: 500
					}
				],
				total: 1,
				offset: 0,
				limit: 50
			})
		} as Response);

		const result = await service.getPrices('sec-123', undefined, undefined, '1h');

		expect(global.fetch).toHaveBeenCalledWith(
			'/api/v1/market/prices/sec-123?interval=1h',
			expect.objectContaining({ method: 'GET' })
		);
		expect(result.items.length).toBe(1);
		expect(result.items[0].timestamp).toBe('2026-07-29T12:00:00Z');
	});

	it('should call getPrices with 4h intraday interval', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				security_id: 'sec-123',
				items: [],
				total: 0,
				offset: 0,
				limit: 50
			})
		} as Response);

		await service.getPrices('sec-123', undefined, undefined, '4h');

		expect(global.fetch).toHaveBeenCalledWith(
			'/api/v1/market/prices/sec-123?interval=4h',
			expect.objectContaining({ method: 'GET' })
		);
	});

	it('should call getPrices with 1w weekly interval and dates', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({
				security_id: 'sec-123',
				from_date: '2020-01-01',
				to_date: '2026-07-29',
				items: [],
				total: 0,
				offset: 0,
				limit: 50
			})
		} as Response);

		await service.getPrices('sec-123', '2020-01-01', '2026-07-29', '1w');

		expect(global.fetch).toHaveBeenCalledWith(
			'/api/v1/market/prices/sec-123?interval=1w&from_date=2020-01-01&to_date=2026-07-29',
			expect.objectContaining({ method: 'GET' })
		);
	});
});
