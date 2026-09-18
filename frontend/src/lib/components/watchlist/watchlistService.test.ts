import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	getMarketService,
	type MarketSearchResult,
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
		search: vi.fn(),
		createOrUpdateSecurity: vi.fn(),
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

function searchResult(code: string, exchange = 'NASDAQ'): MarketSearchResult {
	return { code, exchange, name: `${code} Inc.`, security_type: 'Stock' };
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

describe('WatchlistService.selectWatchlist', () => {
	it('tracks the active watchlist and derives it from the shared state', () => {
		service.watchlists = [defaultList(), techList()];
		expect(service.activeWatchlist).toBeNull();

		service.selectWatchlist('wl-tech');

		expect(service.activeWatchlistId).toBe('wl-tech');
		expect(service.activeWatchlist?.name).toBe('Tech');
	});

	it('keeps the derived active list in sync when its entry is replaced', async () => {
		service.watchlists = [defaultList(), techList()];
		service.selectWatchlist('wl-tech');
		client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', []));

		await service.removeSecurity('wl-tech', 'sec-3');

		expect(service.activeWatchlist?.securities).toEqual([]);
	});
});

describe('WatchlistService.searchSecurities', () => {
	it('delegates to the market search endpoint', async () => {
		client.search.mockResolvedValue([searchResult('AAPL')]);

		const results = await service.searchSecurities('AAPL');

		expect(client.search).toHaveBeenCalledWith('AAPL');
		expect(results.map((r) => r.code)).toEqual(['AAPL']);
	});
});

describe('WatchlistService.addSecurity', () => {
	it('resolves the search result, adds membership and replaces the returned list', async () => {
		service.watchlists = [defaultList(), techList()];
		client.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-4',
			symbol: 'GOOG',
			exchange: 'NASDAQ',
			name: 'GOOG Inc.',
			has_price_data: false
		});
		client.addSecurityToWatchlist.mockResolvedValue(
			watchlist('wl-tech', 'Tech', [nvda, security('sec-4', 'GOOG')])
		);

		await service.addSecurity('wl-tech', searchResult('GOOG'));

		expect(client.createOrUpdateSecurity).toHaveBeenCalledWith({
			code: 'GOOG',
			exchange: 'NASDAQ',
			name: 'GOOG Inc.',
			currency: 'USD'
		});
		expect(client.addSecurityToWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-4', undefined);
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.securities.map((s) => s.id)).toEqual(
			['sec-3', 'sec-4']
		);
		expect(service.error).toBeNull();
	});

	it('is a no-op when the resolved security already belongs to the list', async () => {
		service.watchlists = [defaultList()];
		client.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-1',
			symbol: 'AAPL',
			exchange: 'NASDAQ',
			name: 'AAPL Inc.',
			has_price_data: true
		});

		await service.addSecurity('wl-default', searchResult('AAPL'));

		expect(client.createOrUpdateSecurity).toHaveBeenCalled();
		expect(client.addSecurityToWatchlist).not.toHaveBeenCalled();
		expect(service.watchlists[0].securities.map((s) => s.id)).toEqual(['sec-1', 'sec-2']);
	});

	it('keeps the Default list and sidebar array in sync when a security is added', async () => {
		service.watchlists = [defaultList()];
		client.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-3',
			symbol: 'NVDA',
			exchange: 'NASDAQ',
			name: 'NVDA Inc.',
			has_price_data: true
		});
		client.addSecurityToWatchlist.mockResolvedValue(
			watchlist('wl-default', 'Default', [aapl, msft, nvda])
		);

		await service.addSecurity('wl-default', searchResult('NVDA'));

		expect(service.defaultWatchlistSecurities.map((s) => s.id)).toEqual([
			'sec-1',
			'sec-2',
			'sec-3'
		]);
	});

	it('surfaces errors and leaves state untouched when resolution fails', async () => {
		service.watchlists = [defaultList()];
		client.createOrUpdateSecurity.mockRejectedValue(new Error('Security lookup failed'));

		await service.addSecurity('wl-default', searchResult('AAPL'));

		expect(service.error).toBe('Security lookup failed');
		expect(client.addSecurityToWatchlist).not.toHaveBeenCalled();
		expect(service.watchlists[0].securities.map((s) => s.id)).toEqual(['sec-1', 'sec-2']);
	});

	it('surfaces errors and leaves state untouched when the membership POST fails', async () => {
		service.watchlists = [techList()];
		client.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-4',
			symbol: 'GOOG',
			exchange: 'NASDAQ',
			name: 'GOOG Inc.',
			has_price_data: false
		});
		client.addSecurityToWatchlist.mockRejectedValue(new Error('Watchlist not found'));

		await service.addSecurity('wl-tech', searchResult('GOOG'));

		expect(service.error).toBe('Watchlist not found');
		expect(service.watchlists[0].securities.map((s) => s.id)).toEqual(['sec-3']);
	});
});

describe('WatchlistService.removeSecurity', () => {
	it('replaces the returned list for a non-default list', async () => {
		service.watchlists = [defaultList(), watchlist('wl-tech', 'Tech', [nvda, aapl])];
		client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda]));

		await service.removeSecurity('wl-tech', 'sec-1');

		expect(client.removeSecurityFromWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-1', undefined);
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.securities.map((s) => s.id)).toEqual(
			['sec-3']
		);
	});

	it('keeps the Default list and sidebar array in sync when a security is removed', async () => {
		service.watchlists = [defaultList()];
		client.removeSecurityFromWatchlist.mockResolvedValue(
			watchlist('wl-default', 'Default', [msft])
		);

		await service.removeSecurity('wl-default', 'sec-1');

		expect(service.defaultWatchlistSecurities.map((s) => s.id)).toEqual(['sec-2']);
	});

	it('surfaces errors and leaves state untouched when removal fails', async () => {
		service.watchlists = [defaultList(), techList()];
		client.removeSecurityFromWatchlist.mockRejectedValue(new Error('Security not found'));

		await service.removeSecurity('wl-tech', 'sec-3');

		expect(service.error).toBe('Security not found');
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.securities.map((s) => s.id)).toEqual(
			['sec-3']
		);
		expect(client.getWatchlists).not.toHaveBeenCalled();
	});
});
