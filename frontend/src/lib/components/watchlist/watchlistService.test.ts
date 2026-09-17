import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	getMarketService,
	type MarketService,
	type SecuritySchema,
	type WatchlistRead
} from '@/api/marketService';
import { WatchlistService } from './watchlistService.svelte';

vi.mock('@/api/marketService', () => ({
	getMarketService: vi.fn()
}));

function security(id: string, symbol: string): SecuritySchema {
	return {
		id,
		symbol,
		exchange: 'NASDAQ',
		currency: 'USD',
		name: `${symbol} Inc.`,
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	};
}

function watchlist(id: string, name: string, securities: SecuritySchema[]): WatchlistRead {
	return { id, user_id: 'user-1', name, securities };
}

const aapl = security('sec-1', 'AAPL');
const msft = security('sec-2', 'MSFT');
const nvda = security('sec-3', 'NVDA');

const defaultList = () => watchlist('wl-default', 'Default', [aapl, msft]);
const techList = () => watchlist('wl-tech', 'Tech', [nvda]);

function makeClient() {
	return {
		getWatchlists: vi.fn(),
		createWatchlist: vi.fn(),
		renameWatchlist: vi.fn(),
		deleteWatchlist: vi.fn(),
		addSecurityToWatchlist: vi.fn(),
		removeSecurityFromWatchlist: vi.fn(),
		addToWatchlist: vi.fn(),
		removeFromWatchlist: vi.fn()
	};
}

let client: ReturnType<typeof makeClient>;
let service: WatchlistService;

beforeEach(() => {
	vi.clearAllMocks();
	client = makeClient();
	vi.mocked(getMarketService).mockReturnValue(client as unknown as MarketService);
	service = new WatchlistService();
});

describe('WatchlistService.loadWatchlists', () => {
	it('stores watchlists with embedded securities and derives the default list', async () => {
		client.getWatchlists.mockResolvedValue([techList(), defaultList()]);

		await service.loadWatchlists('tok');

		expect(client.getWatchlists).toHaveBeenCalledWith('tok');
		expect(service.watchlists).toHaveLength(2);
		expect(service.defaultWatchlistSecurities.map((s) => s.id)).toEqual(['sec-1', 'sec-2']);
		expect(service.isLoading).toBe(false);
		expect(service.error).toBeNull();
	});

	it('surfaces a load failure without leaving isLoading set', async () => {
		client.getWatchlists.mockRejectedValue(new Error('network down'));

		await service.loadWatchlists();

		expect(service.error).toBe('network down');
		expect(service.isLoading).toBe(false);
	});
});

describe('WatchlistService.createWatchlist', () => {
	it('appends the returned watchlist locally', async () => {
		service.watchlists = [defaultList()];
		client.createWatchlist.mockResolvedValue(techList());

		await service.createWatchlist('Tech', 'tok');

		expect(client.createWatchlist).toHaveBeenCalledWith('Tech', 'tok');
		expect(service.watchlists.map((w) => w.id)).toEqual(['wl-default', 'wl-tech']);
	});

	it('sets the error message and leaves state untouched on failure', async () => {
		service.watchlists = [defaultList()];
		client.createWatchlist.mockRejectedValue(new Error('Watchlist already exists'));

		await service.createWatchlist('Default');

		expect(service.error).toBe('Watchlist already exists');
		expect(service.watchlists.map((w) => w.id)).toEqual(['wl-default']);
	});
});

describe('WatchlistService.renameWatchlist', () => {
	it('replaces only the matching watchlist', async () => {
		service.watchlists = [defaultList(), techList()];
		client.renameWatchlist.mockResolvedValue(watchlist('wl-tech', 'Renamed', [nvda]));

		await service.renameWatchlist('wl-tech', 'Renamed', 'tok');

		expect(client.renameWatchlist).toHaveBeenCalledWith('wl-tech', 'Renamed', 'tok');
		expect(service.watchlists[0].name).toBe('Default');
		expect(service.watchlists[1].name).toBe('Renamed');
	});

	it('surfaces backend errors', async () => {
		service.watchlists = [techList()];
		client.renameWatchlist.mockRejectedValue(new Error('Watchlist name already in use'));

		await service.renameWatchlist('wl-tech', 'Default');

		expect(service.error).toBe('Watchlist name already in use');
		expect(service.watchlists[0].name).toBe('Tech');
	});
});

describe('WatchlistService.deleteWatchlist', () => {
	it('filters the deleted watchlist from local state', async () => {
		service.watchlists = [defaultList(), techList()];
		client.deleteWatchlist.mockResolvedValue(undefined);

		await service.deleteWatchlist('wl-tech', 'tok');

		expect(client.deleteWatchlist).toHaveBeenCalledWith('wl-tech', 'tok');
		expect(service.watchlists.map((w) => w.id)).toEqual(['wl-default']);
	});

	it('surfaces backend errors', async () => {
		service.watchlists = [defaultList(), techList()];
		client.deleteWatchlist.mockRejectedValue(new Error('Watchlist not found'));

		await service.deleteWatchlist('wl-tech');

		expect(service.error).toBe('Watchlist not found');
		expect(service.watchlists.map((w) => w.id)).toEqual(['wl-default', 'wl-tech']);
	});
});

describe('WatchlistService membership', () => {
	it('adds a security to a non-default list without clobbering other lists', async () => {
		service.watchlists = [defaultList(), techList()];
		client.addSecurityToWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda, aapl]));

		await service.addSecurityToWatchlist('wl-tech', 'sec-1', 'tok');

		expect(client.addSecurityToWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-1', 'tok');
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.securities.map((s) => s.id)).toEqual(
			['sec-3', 'sec-1']
		);
		expect(
			service.watchlists.find((w) => w.id === 'wl-default')?.securities.map((s) => s.id)
		).toEqual(['sec-1', 'sec-2']);
		expect(service.defaultWatchlistSecurities.map((s) => s.id)).toEqual(['sec-1', 'sec-2']);
	});

	it('removes a security from a non-default list without clobbering other lists', async () => {
		service.watchlists = [defaultList(), watchlist('wl-tech', 'Tech', [nvda, aapl])];
		client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda]));

		await service.removeSecurityFromWatchlist('wl-tech', 'sec-1', 'tok');

		expect(client.removeSecurityFromWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-1', 'tok');
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.securities.map((s) => s.id)).toEqual(
			['sec-3']
		);
		expect(
			service.watchlists.find((w) => w.id === 'wl-default')?.securities.map((s) => s.id)
		).toEqual(['sec-1', 'sec-2']);
	});

	it('sets the error and resyncs watchlists when removing fails', async () => {
		service.watchlists = [defaultList(), techList()];
		client.removeSecurityFromWatchlist.mockRejectedValue(new Error('Security not found'));
		client.getWatchlists.mockResolvedValue([defaultList(), techList()]);

		await service.removeSecurityFromWatchlist('wl-tech', 'sec-3', 'tok');

		expect(service.error).toBe('Security not found');
		expect(client.getWatchlists).toHaveBeenCalledWith('tok');
	});
});

describe('WatchlistService default-list star', () => {
	it('hasSecurity looks at the Default list only', async () => {
		client.getWatchlists.mockResolvedValue([defaultList(), techList()]);

		await service.loadWatchlists();

		expect(service.hasSecurity('sec-1')).toBe(true);
		expect(service.hasSecurity('sec-3')).toBe(false);
	});

	it('toggleSecurity adds through the default-list route when the security is absent', async () => {
		client.getWatchlists.mockResolvedValue([defaultList()]);
		await service.loadWatchlists();
		client.addToWatchlist.mockResolvedValue(watchlist('wl-default', 'Default', [aapl, msft, nvda]));

		await service.toggleSecurity('sec-3', 'tok');

		expect(client.addToWatchlist).toHaveBeenCalledWith('sec-3', 'tok');
		expect(service.hasSecurity('sec-3')).toBe(true);
	});

	it('toggleSecurity removes through the default-list route when the security is present', async () => {
		client.getWatchlists.mockResolvedValue([defaultList()]);
		await service.loadWatchlists();
		client.removeFromWatchlist.mockResolvedValue(watchlist('wl-default', 'Default', [msft]));

		await service.toggleSecurity('sec-1', 'tok');

		expect(client.removeFromWatchlist).toHaveBeenCalledWith('sec-1', 'tok');
		expect(service.hasSecurity('sec-1')).toBe(false);
		expect(service.hasSecurity('sec-2')).toBe(true);
	});
});
