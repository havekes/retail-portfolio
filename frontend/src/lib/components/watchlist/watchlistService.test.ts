import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	getMarketService,
	type MarketSearchResult,
	type MarketService,
	type WatchlistRead,
	type WatchlistSecuritySchema,
	type WatchlistSort
} from '@/api/marketService';
import { WatchlistService } from './watchlistService.svelte';

vi.mock('@/api/marketService', () => ({
	getMarketService: vi.fn()
}));

function security(id: string, symbol: string): WatchlistSecuritySchema {
	return {
		id,
		symbol,
		exchange: 'NASDAQ',
		currency: 'USD',
		name: `${symbol} Inc.`,
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z',
		added_at: '2026-01-01T00:00:00Z',
		position: 0
	};
}

function watchlist(
	id: string,
	name: string,
	securities: WatchlistSecuritySchema[],
	sort: WatchlistSort = 'custom'
): WatchlistRead {
	return { id, user_id: 'user-1', name, sort, securities };
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
		updateWatchlistSort: vi.fn(),
		deleteWatchlist: vi.fn(),
		addSecurityToWatchlist: vi.fn(),
		removeSecurityFromWatchlist: vi.fn(),
		reorderWatchlistSecurities: vi.fn(),
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

		const result = await service.loadWatchlists('tok');

		expect(client.getWatchlists).toHaveBeenCalledWith('tok');
		expect(service.watchlists).toHaveLength(2);
		expect(service.defaultWatchlistSecurities.map((s) => s.id)).toEqual(['sec-1', 'sec-2']);
		expect(service.isLoading).toBe(false);
		expect(service.error).toBeNull();
		// `null` tells the caller there is nothing to route through the 401 seam.
		expect(result).toBeNull();
	});

	it('surfaces a load failure without leaving isLoading set', async () => {
		const failure = new Error('network down');
		client.getWatchlists.mockRejectedValue(failure);

		const result = await service.loadWatchlists();

		expect(service.error).toBe('network down');
		expect(service.isLoading).toBe(false);
		// The caught error is returned so callers can route a 401 to the login page.
		expect(result).toBe(failure);
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

describe('WatchlistService.setSort', () => {
	it('persists the sort and replaces the returned watchlist in state', async () => {
		service.watchlists = [defaultList(), techList()];
		const updatedSecurities = [aapl, msft, nvda];
		client.updateWatchlistSort.mockResolvedValue(
			watchlist('wl-tech', 'Tech', updatedSecurities, 'date_added')
		);

		await service.setSort('wl-tech', 'date_added', 'tok');

		expect(client.updateWatchlistSort).toHaveBeenCalledWith('wl-tech', 'date_added', 'tok');
		const stored = service.watchlists.find((w) => w.id === 'wl-tech');
		expect(stored?.sort).toBe('date_added');
		expect(stored?.securities.map((s) => s.id)).toEqual(['sec-1', 'sec-2', 'sec-3']);
		// Unrelated watchlists are untouched.
		expect(service.watchlists.find((w) => w.id === 'wl-default')?.sort).toBe('custom');
		expect(service.error).toBeNull();
	});

	it('sets the error and leaves state untouched when the PATCH fails', async () => {
		service.watchlists = [defaultList(), techList()];
		client.updateWatchlistSort.mockRejectedValue(new Error('Watchlist not found'));

		await service.setSort('wl-tech', 'date_added');

		expect(service.error).toBe('Watchlist not found');
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.sort).toBe('custom');
		expect(client.getWatchlists).not.toHaveBeenCalled();
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

describe('WatchlistService.reorderSecurities', () => {
	it('applies the new order optimistically with rewritten positions before the PUT settles', async () => {
		const first = { ...aapl, position: 0 };
		const second = { ...msft, position: 1 };
		const third = { ...nvda, position: 2 };
		service.watchlists = [watchlist('wl-tech', 'Tech', [first, second, third])];

		let resolvePut!: (value: WatchlistRead) => void;
		client.reorderWatchlistSecurities.mockReturnValue(
			new Promise<WatchlistRead>((resolve) => {
				resolvePut = resolve;
			})
		);

		const promise = service.reorderSecurities('wl-tech', ['sec-3', 'sec-1', 'sec-2'], 'tok');

		// The optimistic rebuild is visible while the request is still in flight...
		const optimistic = service.watchlists.find((w) => w.id === 'wl-tech');
		expect(optimistic?.securities.map((s) => s.id)).toEqual(['sec-3', 'sec-1', 'sec-2']);
		expect(optimistic?.securities.map((s) => s.position)).toEqual([0, 1, 2]);
		expect(client.reorderWatchlistSecurities).toHaveBeenCalledWith(
			'wl-tech',
			['sec-3', 'sec-1', 'sec-2'],
			'tok'
		);

		resolvePut(watchlist('wl-tech', 'Tech', [third, first, second]));
		await promise;

		expect(service.error).toBeNull();
	});

	it('replaces the watchlist with the server payload, keeping server positions', async () => {
		service.watchlists = [defaultList(), watchlist('wl-tech', 'Tech', [nvda, aapl])];
		client.reorderWatchlistSecurities.mockResolvedValue(
			watchlist('wl-tech', 'Tech', [
				{ ...nvda, position: 0 },
				{ ...aapl, position: 1 }
			])
		);

		await service.reorderSecurities('wl-tech', ['sec-3', 'sec-1'], 'tok');

		const stored = service.watchlists.find((w) => w.id === 'wl-tech');
		expect(stored?.securities.map((s) => s.id)).toEqual(['sec-3', 'sec-1']);
		expect(stored?.securities.map((s) => s.position)).toEqual([0, 1]);
		// Unrelated watchlists are untouched.
		expect(
			service.watchlists.find((w) => w.id === 'wl-default')?.securities.map((s) => s.id)
		).toEqual(['sec-1', 'sec-2']);
		expect(service.error).toBeNull();
	});

	it('keeps positions contiguous across a reverse-direction second reorder', async () => {
		service.watchlists = [
			watchlist('wl-tech', 'Tech', [
				{ ...aapl, position: 0 },
				{ ...msft, position: 1 },
				{ ...nvda, position: 2 }
			])
		];
		client.reorderWatchlistSecurities
			.mockResolvedValueOnce(
				watchlist('wl-tech', 'Tech', [
					{ ...nvda, position: 0 },
					{ ...aapl, position: 1 },
					{ ...msft, position: 2 }
				])
			)
			.mockResolvedValueOnce(
				watchlist('wl-tech', 'Tech', [
					{ ...nvda, position: 0 },
					{ ...msft, position: 1 },
					{ ...aapl, position: 2 }
				])
			);

		// Forward: NVDA to the front.
		await service.reorderSecurities('wl-tech', ['sec-3', 'sec-1', 'sec-2'], 'tok');
		// Reverse: MSFT up one, computed from the order the first call left behind.
		await service.reorderSecurities('wl-tech', ['sec-3', 'sec-2', 'sec-1'], 'tok');

		expect(client.reorderWatchlistSecurities).toHaveBeenNthCalledWith(
			1,
			'wl-tech',
			['sec-3', 'sec-1', 'sec-2'],
			'tok'
		);
		expect(client.reorderWatchlistSecurities).toHaveBeenNthCalledWith(
			2,
			'wl-tech',
			['sec-3', 'sec-2', 'sec-1'],
			'tok'
		);

		const stored = service.watchlists.find((w) => w.id === 'wl-tech');
		// Optimistic state agrees with the last server payload: the id order and the
		// rewritten positions the next keydown's index is derived from.
		expect(stored?.securities.map((s) => s.id)).toEqual(['sec-3', 'sec-2', 'sec-1']);
		expect(stored?.securities.map((s) => s.position)).toEqual([0, 1, 2]);
		expect(service.error).toBeNull();
	});

	it('resyncs, reverts the optimistic order and records the error when the PUT fails', async () => {
		service.watchlists = [watchlist('wl-tech', 'Tech', [aapl, msft, nvda])];
		client.reorderWatchlistSecurities.mockRejectedValue(new Error('Reorder failed'));
		client.getWatchlists.mockResolvedValue([
			watchlist('wl-tech', 'Tech', [
				{ ...aapl, position: 0 },
				{ ...msft, position: 1 },
				{ ...nvda, position: 2 }
			])
		]);

		await service.reorderSecurities('wl-tech', ['sec-3', 'sec-1', 'sec-2'], 'tok');

		expect(client.getWatchlists).toHaveBeenCalledWith('tok');
		expect(service.watchlists[0].securities.map((s) => s.id)).toEqual(['sec-1', 'sec-2', 'sec-3']);
		expect(service.error).toBe('Reorder failed');
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

	it('is a no-op when the security already belongs to the target list', async () => {
		service.watchlists = [defaultList()];

		await service.addSecurity('wl-default', searchResult('AAPL'));

		// Dedupe happens before any network resolution or membership POST.
		expect(client.createOrUpdateSecurity).not.toHaveBeenCalled();
		expect(client.addSecurityToWatchlist).not.toHaveBeenCalled();
		expect(service.error).toBeNull();
		expect(service.watchlists[0].securities.map((s) => s.id)).toEqual(['sec-1', 'sec-2']);
	});

	it('reuses an existing security id from another watchlist without resolving a new one', async () => {
		service.watchlists = [defaultList(), techList()];
		client.addSecurityToWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda, aapl]));

		// AAPL already exists in the Default list; adding it to Tech reuses sec-1.
		await service.addSecurity('wl-tech', searchResult('AAPL'));

		expect(client.createOrUpdateSecurity).not.toHaveBeenCalled();
		expect(client.addSecurityToWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-1', undefined);
		expect(service.error).toBeNull();
		expect(service.watchlists.find((w) => w.id === 'wl-tech')?.securities.map((s) => s.id)).toEqual(
			['sec-3', 'sec-1']
		);
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

		// TSLA is not a member of any loaded watchlist, so resolution is attempted.
		await service.addSecurity('wl-default', searchResult('TSLA'));

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

describe('WatchlistService error lifecycle', () => {
	it('sets the error on failure and clears it on the next successful mutation', async () => {
		service.watchlists = [defaultList(), techList()];
		client.renameWatchlist.mockRejectedValue(new Error('Watchlist name already in use'));

		await service.renameWatchlist('wl-tech', 'Default');
		expect(service.error).toBe('Watchlist name already in use');

		client.deleteWatchlist.mockResolvedValue(undefined);
		await service.deleteWatchlist('wl-tech');
		expect(service.error).toBeNull();
	});

	it('clears a stale error on every successful mutation', async () => {
		service.watchlists = [defaultList(), techList()];
		client.getWatchlists.mockResolvedValue([]);
		client.createWatchlist.mockResolvedValue(watchlist('wl-new', 'New', []));
		client.renameWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda]));
		client.updateWatchlistSort.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda]));
		client.deleteWatchlist.mockResolvedValue(undefined);
		client.addSecurityToWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda, aapl]));
		client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', []));
		client.reorderWatchlistSecurities.mockResolvedValue(watchlist('wl-tech', 'Tech', [nvda]));
		client.addToWatchlist.mockResolvedValue(watchlist('wl-default', 'Default', [aapl, msft, nvda]));
		client.removeFromWatchlist.mockResolvedValue(watchlist('wl-default', 'Default', [msft]));

		const cases: [string, () => Promise<unknown>][] = [
			['loadWatchlists', () => service.loadWatchlists()],
			['createWatchlist', () => service.createWatchlist('New')],
			['renameWatchlist', () => service.renameWatchlist('wl-tech', 'Tech')],
			['setSort', () => service.setSort('wl-tech', 'name_asc')],
			['deleteWatchlist', () => service.deleteWatchlist('wl-tech')],
			['addSecurity', () => service.addSecurity('wl-tech', searchResult('AAPL'))],
			['removeSecurity', () => service.removeSecurity('wl-tech', 'sec-1')],
			['addSecurityToWatchlist', () => service.addSecurityToWatchlist('wl-tech', 'sec-1')],
			[
				'removeSecurityFromWatchlist',
				() => service.removeSecurityFromWatchlist('wl-tech', 'sec-1')
			],
			['reorderSecurities', () => service.reorderSecurities('wl-tech', ['sec-3'])],
			['toggleSecurity', () => service.toggleSecurity('sec-3')]
		];

		for (const [name, run] of cases) {
			service.watchlists = [defaultList(), techList()];
			service.error = 'stale error';
			await run();
			expect(service.error, name).toBeNull();
		}
	});
});
