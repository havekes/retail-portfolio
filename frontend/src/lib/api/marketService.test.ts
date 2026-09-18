import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiError } from './apiClient';
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
			expect.stringContaining(
				'/api/v1/market/prices/sec-123?interval=1d&from_date=2026-01-01&to_date=2026-07-29'
			),
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
			expect.stringContaining('/api/v1/market/prices/sec-123?interval=1h'),
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
			expect.stringContaining('/api/v1/market/prices/sec-123?interval=4h'),
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
			expect.stringContaining(
				'/api/v1/market/prices/sec-123?interval=1w&from_date=2020-01-01&to_date=2026-07-29'
			),
			expect.objectContaining({ method: 'GET' })
		);
	});

	it('should call getPrices with token as 5th argument', async () => {
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

		await service.getPrices('sec-123', '2026-01-01', '2026-07-29', '1d', 'test-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining(
				'/api/v1/market/prices/sec-123?interval=1d&from_date=2026-01-01&to_date=2026-07-29'
			),
			expect.objectContaining({
				method: 'GET',
				headers: expect.objectContaining({
					Authorization: 'Bearer test-token'
				})
			})
		);
	});

	it('should call createWatchlist with POST, name payload, and token', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 201,
			json: async () => watchlistFixture({ id: 'wl-new', name: 'Growth' })
		} as Response);

		const result = await service.createWatchlist('Growth', 'test-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/market/watchlists'),
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({ name: 'Growth' }),
				headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
			})
		);
		expect(result.name).toBe('Growth');
	});

	it('should call renameWatchlist with PATCH on the watchlist path', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => watchlistFixture({ id: 'wl-1', name: 'Renamed' })
		} as Response);

		await service.renameWatchlist('wl-1', 'Renamed', 'test-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/market/watchlists/wl-1'),
			expect.objectContaining({
				method: 'PATCH',
				body: JSON.stringify({ name: 'Renamed' }),
				headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
			})
		);
	});

	it('should call deleteWatchlist with DELETE and resolve undefined on 204', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 204,
			json: async () => {
				throw new Error('204 has no body');
			}
		} as unknown as Response);

		const result = await service.deleteWatchlist('wl-1', 'test-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/market/watchlists/wl-1'),
			expect.objectContaining({
				method: 'DELETE',
				headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
			})
		);
		expect(result).toBeUndefined();
	});

	it('should call addSecurityToWatchlist with POST on the membership path', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => watchlistFixture({ id: 'wl-2', name: 'Tech', securities: [security] })
		} as Response);

		const result = await service.addSecurityToWatchlist('wl-2', 'sec-1', 'test-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/market/watchlists/wl-2/securities/sec-1'),
			expect.objectContaining({
				method: 'POST',
				headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
			})
		);
		expect(result.securities).toEqual([security]);
	});

	it('should call removeSecurityFromWatchlist with DELETE on the membership path', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => watchlistFixture({ id: 'wl-2', name: 'Tech', securities: [] })
		} as Response);

		const result = await service.removeSecurityFromWatchlist('wl-2', 'sec-1', 'test-token');

		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/api/v1/market/watchlists/wl-2/securities/sec-1'),
			expect.objectContaining({
				method: 'DELETE',
				headers: expect.objectContaining({ Authorization: 'Bearer test-token' })
			})
		);
		expect(result.securities).toEqual([]);
	});

	it('should surface the backend detail through ApiError for a failed watchlist call', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 409,
			json: async () => ({ detail: 'Watchlist with this name already exists' })
		} as Response);

		await expect(service.createWatchlist('Default', 'test-token')).rejects.toThrow(
			'Watchlist with this name already exists'
		);
		await expect(service.createWatchlist('Default', 'test-token')).rejects.toBeInstanceOf(ApiError);
	});
});

const security = {
	id: 'sec-1',
	symbol: 'AAPL',
	exchange: 'NASDAQ',
	currency: 'USD',
	name: 'Apple Inc.',
	isin: null,
	is_active: true,
	updated_at: '2026-01-01T00:00:00Z'
};

function watchlistFixture(
	overrides: Partial<{
		id: string;
		user_id: string;
		name: string;
		securities: (typeof security)[];
	}> = {}
) {
	return {
		id: 'wl-1',
		user_id: 'user-1',
		name: 'Default',
		securities: [],
		...overrides
	};
}
