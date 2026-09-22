import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/svelte';
import type { Component } from 'svelte';
import type { WatchlistRead, WatchlistSecuritySchema, WatchlistSort } from '@/api/marketService';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

const mocks = vi.hoisted(() => ({
	client: {
		search: vi.fn(),
		createOrUpdateSecurity: vi.fn(),
		getWatchlists: vi.fn().mockResolvedValue([]),
		createWatchlist: vi.fn(),
		renameWatchlist: vi.fn(),
		updateWatchlistSort: vi.fn(),
		deleteWatchlist: vi.fn(),
		addSecurityToWatchlist: vi.fn(),
		removeSecurityFromWatchlist: vi.fn(),
		reorderWatchlistSecurities: vi.fn(),
		addToWatchlist: vi.fn(),
		removeFromWatchlist: vi.fn()
	},
	preferences: {
		patchPreferences: vi.fn().mockResolvedValue({}),
		getPreferences: vi.fn().mockResolvedValue({})
	},
	service: null as unknown
}));

vi.mock('@/api/marketService', () => ({
	getMarketService: () => mocks.client
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: mocks.preferences,
	getUserPreferencesService: () => mocks.preferences
}));

// Return a real WatchlistService instance so its $state drives reactivity, while
// the service module itself is mocked away from the layout context.
vi.mock('$lib/components/watchlist/watchlistService.svelte', async (importOriginal) => {
	const actual =
		await importOriginal<typeof import('$lib/components/watchlist/watchlistService.svelte')>();
	return {
		...actual,
		getWatchlistService: () => mocks.service
	};
});

import { WatchlistService } from '$lib/components/watchlist/watchlistService.svelte';

function security(
	id: string,
	symbol: string,
	price?: number | null,
	changePercent?: number | null,
	addedAt = '2026-01-01T00:00:00Z',
	position = 0
): WatchlistSecuritySchema {
	return {
		id,
		symbol,
		exchange: 'NASDAQ',
		currency: 'USD',
		name: `${symbol} Inc.`,
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z',
		added_at: addedAt,
		position,
		current_price: price,
		daily_price_change: null,
		daily_price_change_percent: changePercent
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

const defaultList = () =>
	watchlist('wl-default', 'Default', [security('sec-1', 'AAPL'), security('sec-2', 'MSFT')]);
const techList = () => watchlist('wl-tech', 'Tech', [security('sec-3', 'NVDA')]);

/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
let PageComponent: Component<any>;
let service: WatchlistService;

beforeAll(async () => {
	const mod = await import('./+page.svelte');
	PageComponent = mod.default;
}, 30000);

beforeEach(() => {
	vi.resetAllMocks();
	mocks.preferences.patchPreferences.mockResolvedValue({});
	mocks.preferences.getPreferences.mockResolvedValue({});
	service = new WatchlistService();
	mocks.service = service;
});

function renderPage(
	watchlists: WatchlistRead[],
	openGlobalSearch: (watchlist?: WatchlistRead | null) => void = vi.fn(),
	order?: string[] | null
) {
	return render(PageComponent, {
		props: {
			data: {
				watchlists,
				watchlist_order: order ?? null
			}
		},
		context: new Map([['openGlobalSearch', openGlobalSearch] as const])
	});
}

async function openCreateModal(name: string) {
	await fireEvent.click(screen.getByRole('button', { name: 'Create watchlist' }));
	const input = await screen.findByLabelText('Watchlist name');
	await fireEvent.input(input, { target: { value: name } });
	await fireEvent.click(screen.getByRole('button', { name: 'Create' }));
	return input;
}

describe('Watchlists page - rendering and sections', () => {
	it('renders every watchlist as its own section with title and count', () => {
		renderPage([defaultList(), techList()]);

		const defaultSection = screen.getByRole('region', { name: 'Default securities' });
		const techSection = screen.getByRole('region', { name: 'Tech securities' });

		expect(defaultSection).toBeInTheDocument();
		expect(techSection).toBeInTheDocument();
		expect(
			within(defaultSection).getByRole('heading', { level: 2, name: 'Default' })
		).toBeInTheDocument();
		expect(
			within(techSection).getByRole('heading', { level: 2, name: 'Tech' })
		).toBeInTheDocument();
		expect(within(defaultSection).getByText('2 securities')).toBeInTheDocument();
		expect(within(techSection).getByText('1 security')).toBeInTheDocument();
	});

	it('renders securities with rounded hover links navigating to /security/[id]', () => {
		renderPage([defaultList(), techList()]);

		const defaultSection = screen.getByRole('region', { name: 'Default securities' });
		const aaplLink = within(defaultSection).getByRole('link', { name: /AAPL/ });
		const msftLink = within(defaultSection).getByRole('link', { name: /MSFT/ });

		expect(aaplLink).toHaveAttribute('href', '/security/sec-1');
		expect(aaplLink).toHaveClass('rounded-md');
		expect(aaplLink).toHaveClass('hover:bg-muted');

		expect(msftLink).toHaveAttribute('href', '/security/sec-2');
		expect(msftLink).toHaveClass('rounded-md');
		expect(msftLink).toHaveClass('hover:bg-muted');
	});

	it('shows the formatted date added as muted secondary text', () => {
		renderPage([
			watchlist('wl-dates', 'Dates', [security('sec-1', 'AAPL', 180, 1.2, '2026-01-01T00:00:00Z')])
		]);

		const section = screen.getByRole('region', { name: 'Dates securities' });
		const added = within(section).getByTitle('Added');

		expect(added).toHaveTextContent('Jan 1, 2026');
		expect(added).toHaveClass('text-xs');
		expect(added).toHaveClass('text-muted-foreground');
	});

	it('omits the date added when it is missing or invalid without breaking the row', () => {
		renderPage([
			watchlist('wl-dates', 'Dates', [
				security('sec-1', 'AAPL', 180, 1.2, ''),
				security('sec-2', 'MSFT', 200, -0.5, 'not-a-date')
			])
		]);

		const section = screen.getByRole('region', { name: 'Dates securities' });

		expect(within(section).queryByTitle('Added')).not.toBeInTheDocument();
		expect(within(section).getByRole('link', { name: /AAPL/ })).toHaveAttribute(
			'href',
			'/security/sec-1'
		);
		expect(within(section).getByRole('link', { name: /MSFT/ })).toHaveAttribute(
			'href',
			'/security/sec-2'
		);
	});

	it('renders empty message for watchlists without securities', () => {
		renderPage([watchlist('wl-empty', 'Empty List', [])]);

		const section = screen.getByRole('region', { name: 'Empty List securities' });
		expect(within(section).getByText('No securities in this watchlist yet.')).toBeInTheDocument();
	});

	it('renders the empty state when there are no watchlists at all', () => {
		renderPage([]);

		expect(screen.getByText("You don't have any watchlists yet")).toBeInTheDocument();
		expect(screen.queryByRole('region')).not.toBeInTheDocument();
	});

	it('does not render inline WatchlistSecurityPicker', () => {
		renderPage([defaultList()]);

		expect(screen.queryByLabelText('Search securities to add')).not.toBeInTheDocument();
		expect(screen.queryByRole('combobox', { name: /add securities/i })).not.toBeInTheDocument();
	});

	it('renders Create watchlist button in PageHeader actions and removes sidebar pref toggle', () => {
		renderPage([defaultList()]);

		expect(screen.getByRole('button', { name: 'Create watchlist' })).toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /show watchlists/i })).not.toBeInTheDocument();
		expect(screen.queryByRole('button', { name: /hide watchlists/i })).not.toBeInTheDocument();
	});
});

describe('Watchlists page - create watchlist', () => {
	it('creates a new watchlist through the modal and adds it to the list', async () => {
		mocks.client.createWatchlist.mockResolvedValue(watchlist('wl-new', 'Dividend', []));
		renderPage([defaultList()]);

		await openCreateModal('Dividend');

		await waitFor(() =>
			expect(mocks.client.createWatchlist).toHaveBeenCalledWith('Dividend', undefined)
		);
		expect(await screen.findByRole('region', { name: 'Dividend securities' })).toBeInTheDocument();
	});

	it('shows the backend error message when creation fails', async () => {
		mocks.client.createWatchlist.mockRejectedValue(new Error('Name already taken'));
		renderPage([defaultList()]);

		await openCreateModal('Duplicate');

		expect(await screen.findByText('Name already taken')).toBeInTheDocument();
		expect(screen.queryByRole('region', { name: 'Duplicate securities' })).not.toBeInTheDocument();
	});
});

describe('Watchlists page - rename watchlist', () => {
	it('renames a watchlist via inline input and save button', async () => {
		mocks.client.renameWatchlist.mockResolvedValue(
			watchlist('wl-tech', 'Tech & AI', [security('sec-3', 'NVDA')])
		);
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Tech' }));

		const input = screen.getByLabelText('Watchlist name');
		expect(input).toHaveValue('Tech');
		await fireEvent.input(input, { target: { value: 'Tech & AI' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save Tech' }));

		await waitFor(() =>
			expect(mocks.client.renameWatchlist).toHaveBeenCalledWith('wl-tech', 'Tech & AI', undefined)
		);
		expect(await screen.findByRole('heading', { level: 2, name: 'Tech & AI' })).toBeInTheDocument();
	});

	it('cancels renaming on cancel button click', async () => {
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Tech' }));
		const input = screen.getByLabelText('Watchlist name');
		await fireEvent.input(input, { target: { value: 'Different' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Cancel rename' }));

		expect(mocks.client.renameWatchlist).not.toHaveBeenCalled();
		expect(screen.getByRole('heading', { level: 2, name: 'Tech' })).toBeInTheDocument();
		expect(screen.queryByLabelText('Watchlist name')).not.toBeInTheDocument();
	});

	it('submits rename on Enter key and cancels on Escape', async () => {
		mocks.client.renameWatchlist.mockResolvedValue(watchlist('wl-tech', 'New Tech', []));
		renderPage([techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Tech' }));
		let input = screen.getByLabelText('Watchlist name');
		await fireEvent.keyDown(input, { key: 'Escape' });
		expect(screen.queryByLabelText('Watchlist name')).not.toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Tech' }));
		input = screen.getByLabelText('Watchlist name');
		await fireEvent.input(input, { target: { value: 'New Tech' } });
		await fireEvent.keyDown(input, { key: 'Enter' });

		await waitFor(() =>
			expect(mocks.client.renameWatchlist).toHaveBeenCalledWith('wl-tech', 'New Tech', undefined)
		);
	});
});

describe('Watchlists page - delete watchlist', () => {
	it('opens confirmation modal and deletes watchlist on confirm', async () => {
		mocks.client.deleteWatchlist.mockResolvedValue(undefined);
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete Tech' }));
		expect(screen.getByText('Delete "Tech"? This cannot be undone.')).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

		await waitFor(() =>
			expect(mocks.client.deleteWatchlist).toHaveBeenCalledWith('wl-tech', undefined)
		);
		await waitFor(() =>
			expect(screen.queryByRole('region', { name: 'Tech securities' })).not.toBeInTheDocument()
		);
	});

	it('does not delete when cancel is clicked in confirmation modal', async () => {
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete Tech' }));
		await fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));

		expect(mocks.client.deleteWatchlist).not.toHaveBeenCalled();
		expect(screen.getByRole('region', { name: 'Tech securities' })).toBeInTheDocument();
	});

	it('shows the backend error message when deletion fails', async () => {
		mocks.client.deleteWatchlist.mockRejectedValue(new Error('Watchlist not found'));
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete Tech' }));
		await fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));

		expect(await screen.findByText('Watchlist not found')).toBeInTheDocument();
		expect(screen.getByRole('region', { name: 'Tech securities' })).toBeInTheDocument();
	});
});

describe('Watchlists page - targeted search integration', () => {
	it('calls openGlobalSearch with the target watchlist when "+" button is clicked', async () => {
		const openGlobalSearch = vi.fn();
		const tech = techList();
		renderPage([defaultList(), tech], openGlobalSearch);

		const addBtn = screen.getByRole('button', { name: 'Add security to Tech' });
		await fireEvent.click(addBtn);

		expect(openGlobalSearch).toHaveBeenCalledTimes(1);
		expect(openGlobalSearch).toHaveBeenCalledWith(
			expect.objectContaining({ id: 'wl-tech', name: 'Tech' })
		);
	});
});

describe('Watchlists page - remove security', () => {
	it('removes the security and updates the count and empty state', async () => {
		mocks.client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', []));
		renderPage([defaultList(), techList()]);

		const section = screen.getByRole('region', { name: 'Tech securities' });
		await fireEvent.click(within(section).getByRole('button', { name: 'Remove NVDA' }));

		await waitFor(() =>
			expect(mocks.client.removeSecurityFromWatchlist).toHaveBeenCalledWith(
				'wl-tech',
				'sec-3',
				undefined
			)
		);
		await waitFor(() =>
			expect(within(section).queryByRole('link', { name: /NVDA/ })).not.toBeInTheDocument()
		);
		expect(within(section).getByText('0 securities')).toBeInTheDocument();
		expect(within(section).getByText('No securities in this watchlist yet.')).toBeInTheDocument();
	});

	it('shows the backend error and keeps the row when removal fails', async () => {
		mocks.client.removeSecurityFromWatchlist.mockRejectedValue(new Error('Security not found'));
		mocks.client.getWatchlists.mockResolvedValue([defaultList(), techList()]);
		renderPage([defaultList(), techList()]);

		const section = screen.getByRole('region', { name: 'Tech securities' });
		await fireEvent.click(within(section).getByRole('button', { name: 'Remove NVDA' }));

		expect(await screen.findByText('Security not found')).toBeInTheDocument();
		expect(within(section).getByRole('link', { name: /NVDA/ })).toBeInTheDocument();
		expect(within(section).getByText('1 security')).toBeInTheDocument();
	});
});

describe('Watchlists page - security prices and daily performance display', () => {
	it('displays formatted price and positive change pill with emerald styling', () => {
		const positiveSec = security('s1', 'AAPL', 150.25, 2.5);
		renderPage([watchlist('wl-1', 'Tech', [positiveSec])]);

		expect(screen.getByText('150.25')).toBeInTheDocument();
		const pill = screen.getByText('+2.50%');
		expect(pill).toBeInTheDocument();
		expect(pill).toHaveClass('text-emerald-600');
		expect(pill).toHaveClass('bg-emerald-500/10');
	});

	it('displays formatted price and negative change pill with rose styling', () => {
		const negativeSec = security('s2', 'MSFT', 320.5, -1.75);
		renderPage([watchlist('wl-1', 'Tech', [negativeSec])]);

		expect(screen.getByText('320.50')).toBeInTheDocument();
		const pill = screen.getByText('-1.75%');
		expect(pill).toBeInTheDocument();
		expect(pill).toHaveClass('text-rose-600');
		expect(pill).toHaveClass('bg-rose-500/10');
	});

	it('displays muted styling for zero or absent price change', () => {
		const zeroSec = security('s3', 'GOOG', 100.0, 0);
		const absentSec = security('s4', 'AMZN', null, null);
		renderPage([watchlist('wl-1', 'Tech', [zeroSec, absentSec])]);

		const zeroPill = screen.getByText('0.00%');
		expect(zeroPill).toHaveClass('text-muted-foreground');

		const absentPills = screen.getAllByText('-');
		expect(absentPills.length).toBeGreaterThanOrEqual(1);
	});
});

describe('Watchlists page - per-watchlist stock sorting', () => {
	function openSortMenu() {
		return fireEvent.click(screen.getByRole('button', { name: 'Sort securities in Tech' }));
	}

	function rowSymbols(listName = 'Tech securities'): string[] {
		return within(screen.getByRole('region', { name: listName }))
			.getAllByRole('link')
			.map((link) => link.querySelector('span')?.textContent?.trim() ?? '');
	}

	function wroteWatchlistSortPreference(): boolean {
		return mocks.preferences.patchPreferences.mock.calls.some((call) => {
			const payload = (call as unknown[])[0] as Record<string, unknown> | undefined;
			return !!payload && Object.prototype.hasOwnProperty.call(payload, 'watchlist_sort');
		});
	}

	it('lists exactly the six sort options in order', async () => {
		renderPage([watchlist('wl-1', 'Tech', [security('s1', 'AAPL')])]);

		await openSortMenu();

		const items = await screen.findAllByRole('menuitem');
		expect(items.map((item) => item.textContent?.trim())).toEqual([
			'Custom',
			'Name (alphabetical)',
			'Price Change (Gainers)',
			'Price Change (Losers)',
			'Date added (newest first)',
			'Date added (oldest first)'
		]);
	});

	it('selecting Name (alphabetical) persists via the model and reorders rows', async () => {
		const s1 = security('s1', 'TSLA', 200, 1.0, '2026-01-03T00:00:00Z', 0);
		const s2 = security('s2', 'AAPL', 150, 2.0, '2026-01-01T00:00:00Z', 1);
		const s3 = security('s3', 'MSFT', 300, 3.0, '2026-01-02T00:00:00Z', 2);
		mocks.client.updateWatchlistSort.mockResolvedValue(
			watchlist('wl-1', 'Tech', [s2, s3, s1], 'name_asc')
		);
		renderPage([watchlist('wl-1', 'Tech', [s1, s2, s3])]);

		// Before any selection: custom order, i.e. insertion (position) order.
		expect(rowSymbols()).toEqual(['TSLA', 'AAPL', 'MSFT']);

		await openSortMenu();
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Name (alphabetical)' }));

		await waitFor(() =>
			expect(mocks.client.updateWatchlistSort).toHaveBeenCalledWith('wl-1', 'name_asc', undefined)
		);
		await waitFor(() => expect(rowSymbols()).toEqual(['AAPL', 'MSFT', 'TSLA']));
		expect(wroteWatchlistSortPreference()).toBe(false);
	});

	it('persists gainers and losers selections', async () => {
		const s1 = security('s1', 'AAPL', 150, 1.5, '2026-01-01T00:00:00Z', 0);
		const s2 = security('s2', 'MSFT', 300, -2.0, '2026-01-02T00:00:00Z', 1);
		const s3 = security('s3', 'NVDA', 450, 5.0, '2026-01-03T00:00:00Z', 2);
		mocks.client.updateWatchlistSort
			.mockResolvedValueOnce(watchlist('wl-1', 'Tech', [s3, s1, s2], 'price_change_desc'))
			.mockResolvedValueOnce(watchlist('wl-1', 'Tech', [s2, s1, s3], 'price_change_asc'));
		renderPage([watchlist('wl-1', 'Tech', [s1, s2, s3])]);

		await openSortMenu();
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Price Change (Gainers)' }));

		await waitFor(() => expect(rowSymbols()).toEqual(['NVDA', 'AAPL', 'MSFT']));
		expect(mocks.client.updateWatchlistSort).toHaveBeenCalledWith(
			'wl-1',
			'price_change_desc',
			undefined
		);

		await openSortMenu();
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Price Change (Losers)' }));

		await waitFor(() => expect(rowSymbols()).toEqual(['MSFT', 'AAPL', 'NVDA']));
		expect(mocks.client.updateWatchlistSort).toHaveBeenLastCalledWith(
			'wl-1',
			'price_change_asc',
			undefined
		);
	});

	it('round-trips both date added directions', async () => {
		const oldest = security('s1', 'AAPL', 150, 1.5, '2026-01-01T00:00:00Z', 0);
		const middle = security('s2', 'MSFT', 300, -2.0, '2026-02-01T00:00:00Z', 1);
		const newest = security('s3', 'NVDA', 450, 5.0, '2026-03-01T00:00:00Z', 2);
		mocks.client.updateWatchlistSort
			.mockResolvedValueOnce(watchlist('wl-1', 'Tech', [newest, middle, oldest], 'date_added'))
			.mockResolvedValueOnce(watchlist('wl-1', 'Tech', [oldest, middle, newest], 'date_added_asc'));
		renderPage([watchlist('wl-1', 'Tech', [oldest, middle, newest])]);

		await openSortMenu();
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Date added (newest first)' }));

		await waitFor(() => expect(rowSymbols()).toEqual(['NVDA', 'MSFT', 'AAPL']));
		expect(mocks.client.updateWatchlistSort).toHaveBeenCalledWith('wl-1', 'date_added', undefined);

		await openSortMenu();
		await fireEvent.click(screen.getByRole('menuitem', { name: 'Date added (oldest first)' }));

		await waitFor(() => expect(rowSymbols()).toEqual(['AAPL', 'MSFT', 'NVDA']));
		expect(mocks.client.updateWatchlistSort).toHaveBeenLastCalledWith(
			'wl-1',
			'date_added_asc',
			undefined
		);
	});

	it('renders each watchlist from its own persisted sort on load', async () => {
		const oldest = security('s1', 'AAPL', 150, 1.5, '2026-01-01T00:00:00Z', 0);
		const newest = security('s2', 'NVDA', 450, 5.0, '2026-03-01T00:00:00Z', 1);
		renderPage([
			watchlist('wl-1', 'Tech', [oldest, newest], 'date_added'),
			watchlist('wl-2', 'Energy', [newest, oldest])
		]);

		// Persisted mode alone drives the first render: newest first for Tech...
		expect(rowSymbols()).toEqual(['NVDA', 'AAPL']);
		// ...and custom (position) order for the freshly created Energy list.
		expect(rowSymbols('Energy securities')).toEqual(['AAPL', 'NVDA']);
		expect(mocks.client.updateWatchlistSort).not.toHaveBeenCalled();
	});

	it('marks the active option with a check and the matching direction chevron', async () => {
		renderPage([watchlist('wl-1', 'Tech', [security('s1', 'AAPL')], 'date_added')]);

		await openSortMenu();

		const activeItem = await screen.findByRole('menuitem', {
			name: 'Date added (newest first)'
		});
		expect(activeItem.querySelector('.lucide-check')).not.toBeNull();
		expect(activeItem.querySelector('.lucide-chevron-down')).not.toBeNull();
		expect(activeItem.querySelector('.lucide-chevron-up')).toBeNull();

		const inactiveItem = screen.getByRole('menuitem', { name: 'Custom' });
		expect(inactiveItem.querySelector('.lucide-check')).toBeNull();
		expect(inactiveItem.querySelector('.lucide-chevron-down')).toBeNull();
		expect(inactiveItem.querySelector('.lucide-chevron-up')).toBeNull();
	});

	it('shows the ascending chevron for ascending modes', async () => {
		renderPage([watchlist('wl-1', 'Tech', [security('s1', 'AAPL')], 'custom')]);

		await openSortMenu();

		const customItem = await screen.findByRole('menuitem', { name: 'Custom' });
		expect(customItem.querySelector('.lucide-check')).not.toBeNull();
		expect(customItem.querySelector('.lucide-chevron-up')).not.toBeNull();
		expect(customItem.querySelector('.lucide-chevron-down')).toBeNull();
	});

	it('shows the ascending chevron for date added (oldest first)', async () => {
		renderPage([watchlist('wl-1', 'Tech', [security('s1', 'AAPL')], 'date_added_asc')]);

		await openSortMenu();

		const activeItem = await screen.findByRole('menuitem', { name: 'Date added (oldest first)' });
		expect(activeItem.querySelector('.lucide-check')).not.toBeNull();
		expect(activeItem.querySelector('.lucide-chevron-up')).not.toBeNull();
	});

	it('falls back to custom order for an unknown persisted sort and can reset it', async () => {
		const staleSort = 'garbage' as unknown as WatchlistSort;
		const s1 = security('s1', 'TSLA', 200, 1.0, '2026-01-03T00:00:00Z', 0);
		const s2 = security('s2', 'AAPL', 150, 2.0, '2026-01-01T00:00:00Z', 1);
		const s3 = security('s3', 'MSFT', 300, 3.0, '2026-01-02T00:00:00Z', 2);
		mocks.client.updateWatchlistSort.mockResolvedValue(
			watchlist('wl-1', 'Tech', [s1, s2, s3], 'custom')
		);
		// Array order is deliberately not the position order.
		renderPage([watchlist('wl-1', 'Tech', [s2, s3, s1], staleSort)]);

		expect(rowSymbols()).toEqual(['TSLA', 'AAPL', 'MSFT']);

		await openSortMenu();
		const customItem = await screen.findByRole('menuitem', { name: 'Custom' });
		expect(customItem.querySelector('.lucide-check')).not.toBeNull();
		await fireEvent.click(customItem);

		await waitFor(() =>
			expect(mocks.client.updateWatchlistSort).toHaveBeenCalledWith('wl-1', 'custom', undefined)
		);
		expect(wroteWatchlistSortPreference()).toBe(false);
	});
});

describe('Watchlists page - watchlist reorder mode and drag-and-drop', () => {
	it('toggles reorder mode and shows drag handles', async () => {
		const w1 = watchlist('wl-1', 'Tech', []);
		const w2 = watchlist('wl-2', 'Energy', []);
		renderPage([w1, w2]);

		expect(screen.queryByTestId('drag-handle')).not.toBeInTheDocument();
		const reorderBtn = screen.getByRole('button', { name: 'Reorder' });
		await fireEvent.click(reorderBtn);

		expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument();
		expect(screen.getAllByTestId('drag-handle')).toHaveLength(2);

		const doneBtn = screen.getByRole('button', { name: 'Done' });
		await fireEvent.click(doneBtn);
		expect(screen.queryByTestId('drag-handle')).not.toBeInTheDocument();
	});

	it('reorders watchlists via drag-and-drop and persists to preferences', async () => {
		const w1 = watchlist('wl-1', 'Tech', []);
		const w2 = watchlist('wl-2', 'Energy', []);
		const w3 = watchlist('wl-3', 'Crypto', []);
		renderPage([w1, w2, w3]);

		await fireEvent.click(screen.getByRole('button', { name: 'Reorder' }));

		const sections = screen.getAllByRole('region');
		expect(sections).toHaveLength(3);

		const dataTransfer = {
			effectAllowed: '',
			dropEffect: '',
			setData: vi.fn(),
			getData: vi.fn().mockReturnValue('0')
		};

		// Drag first section (Tech) to third section (Crypto)
		await fireEvent.dragStart(sections[0], { dataTransfer });
		await fireEvent.dragOver(sections[2], { dataTransfer });
		await fireEvent.drop(sections[2], { dataTransfer });

		await waitFor(() => {
			expect(mocks.preferences.patchPreferences).toHaveBeenCalledWith({
				watchlist_order: ['wl-2', 'wl-3', 'wl-1']
			});
		});

		const reorderedSections = screen.getAllByRole('region');
		const headings = reorderedSections.map((s) => within(s).getByRole('heading', { level: 2 }));
		expect(headings[0]).toHaveTextContent('Energy');
		expect(headings[1]).toHaveTextContent('Crypto');
		expect(headings[2]).toHaveTextContent('Tech');
	});

	it('renders focusable labelled drag handles instead of aria-hidden icons', async () => {
		renderPage([watchlist('wl-1', 'Tech', [])]);

		await fireEvent.click(screen.getByRole('button', { name: 'Reorder' }));

		const handle = screen.getByTestId('drag-handle');
		expect(handle.tagName).toBe('BUTTON');
		expect(handle).toHaveAttribute('type', 'button');
		expect(handle).toHaveAttribute('aria-label', 'Reorder Tech');
		expect(handle).not.toHaveAttribute('aria-hidden');
	});

	it('moves a watchlist with ArrowDown and persists the new order', async () => {
		renderPage([
			watchlist('wl-1', 'Tech', []),
			watchlist('wl-2', 'Energy', []),
			watchlist('wl-3', 'Crypto', [])
		]);

		await fireEvent.click(screen.getByRole('button', { name: 'Reorder' }));
		await fireEvent.keyDown(screen.getByRole('button', { name: 'Reorder Tech' }), {
			key: 'ArrowDown'
		});

		await waitFor(() =>
			expect(mocks.preferences.patchPreferences).toHaveBeenCalledWith({
				watchlist_order: ['wl-2', 'wl-1', 'wl-3']
			})
		);

		const headings = screen
			.getAllByRole('region')
			.map((section) => within(section).getByRole('heading', { level: 2 }).textContent);
		expect(headings).toEqual(['Energy', 'Tech', 'Crypto']);
		expect(screen.getByRole('status')).toHaveTextContent('Tech moved to position 2 of 3');
	});

	it('moves a watchlist with ArrowUp and keeps focus on the handle', async () => {
		renderPage([watchlist('wl-1', 'Tech', []), watchlist('wl-2', 'Energy', [])]);

		await fireEvent.click(screen.getByRole('button', { name: 'Reorder' }));
		const handle = screen.getByRole('button', { name: 'Reorder Energy' });
		handle.focus();
		await fireEvent.keyDown(handle, { key: 'ArrowUp' });

		await waitFor(() =>
			expect(mocks.preferences.patchPreferences).toHaveBeenCalledWith({
				watchlist_order: ['wl-2', 'wl-1']
			})
		);
		expect(screen.getByRole('button', { name: 'Reorder Energy' })).toHaveFocus();
	});

	it('does not move a watchlist past the top or bottom boundary', async () => {
		renderPage([watchlist('wl-1', 'Tech', []), watchlist('wl-2', 'Energy', [])]);

		await fireEvent.click(screen.getByRole('button', { name: 'Reorder' }));
		await fireEvent.keyDown(screen.getByRole('button', { name: 'Reorder Tech' }), {
			key: 'ArrowUp'
		});
		await fireEvent.keyDown(screen.getByRole('button', { name: 'Reorder Energy' }), {
			key: 'ArrowDown'
		});

		expect(mocks.preferences.patchPreferences).not.toHaveBeenCalled();
	});

	it('rolls both order snapshots back and shows the error when persisting fails', async () => {
		mocks.preferences.patchPreferences.mockRejectedValue(new Error('Order save failed'));
		renderPage([watchlist('wl-1', 'Tech', []), watchlist('wl-2', 'Energy', [])]);

		await fireEvent.click(screen.getByRole('button', { name: 'Reorder' }));
		await fireEvent.keyDown(screen.getByRole('button', { name: 'Reorder Tech' }), {
			key: 'ArrowDown'
		});

		expect(await screen.findByText('Order save failed')).toBeInTheDocument();

		const headings = screen
			.getAllByRole('region')
			.map((section) => within(section).getByRole('heading', { level: 2 }).textContent);
		expect(headings).toEqual(['Tech', 'Energy']);
	});
});

describe('Watchlists page - security reorder in custom sort mode', () => {
	function dataTransfer() {
		return {
			effectAllowed: '',
			dropEffect: '',
			setData: vi.fn(),
			getData: vi.fn().mockReturnValue('0')
		};
	}

	function rowSymbols(listName = 'Tech securities'): string[] {
		return within(screen.getByRole('region', { name: listName }))
			.getAllByRole('link')
			.map((link) => link.querySelector('span')?.textContent?.trim() ?? '');
	}

	const a = () => security('s1', 'AAPL', 150, 1, '2026-01-01T00:00:00Z', 0);
	const b = () => security('s2', 'MSFT', 300, 2, '2026-01-02T00:00:00Z', 1);
	const c = () => security('s3', 'NVDA', 450, 3, '2026-01-03T00:00:00Z', 2);

	async function enableReorder(name = 'Tech') {
		await fireEvent.click(screen.getByRole('button', { name: `Reorder securities in ${name}` }));
	}

	it('offers the reorder toggle only for custom-sorted watchlists', () => {
		renderPage([
			watchlist('wl-tech', 'Tech', [a()], 'custom'),
			watchlist('wl-recent', 'Recent', [b()], 'date_added')
		]);

		const toggle = screen.getByRole('button', { name: 'Reorder securities in Tech' });
		expect(toggle).toHaveAttribute('aria-pressed', 'false');
		expect(
			screen.queryByRole('button', { name: 'Reorder securities in Recent' })
		).not.toBeInTheDocument();
	});

	it('shows labelled focusable handles on every row once the toggle is on', async () => {
		renderPage([watchlist('wl-tech', 'Tech', [a(), b()])]);

		expect(screen.queryByTestId('security-drag-handle')).not.toBeInTheDocument();

		await enableReorder();

		expect(screen.getByRole('button', { name: 'Reorder securities in Tech' })).toHaveAttribute(
			'aria-pressed',
			'true'
		);
		expect(screen.getAllByTestId('security-drag-handle')).toHaveLength(2);
		expect(screen.getByRole('button', { name: 'Reorder AAPL' })).toHaveAttribute('type', 'button');
		expect(screen.getByRole('button', { name: 'Reorder MSFT' })).toBeInTheDocument();
	});

	it('reorders rows by drag and persists the new id order', async () => {
		mocks.client.reorderWatchlistSecurities.mockResolvedValue(
			watchlist('wl-tech', 'Tech', [
				{ ...b(), position: 0 },
				{ ...c(), position: 1 },
				{ ...a(), position: 2 }
			])
		);
		renderPage([watchlist('wl-tech', 'Tech', [a(), b(), c()])]);
		await enableReorder();

		const rows = within(screen.getByRole('region', { name: 'Tech securities' })).getAllByRole(
			'listitem'
		);
		const dt = dataTransfer();

		await fireEvent.dragStart(rows[0], { dataTransfer: dt });
		await fireEvent.dragOver(rows[2], { dataTransfer: dt });
		await fireEvent.drop(rows[2], { dataTransfer: dt });

		await waitFor(() =>
			expect(mocks.client.reorderWatchlistSecurities).toHaveBeenCalledWith(
				'wl-tech',
				['s2', 's3', 's1'],
				undefined
			)
		);
		await waitFor(() => expect(rowSymbols()).toEqual(['MSFT', 'NVDA', 'AAPL']));
	});

	it('moves a security down with ArrowDown, persists and announces it', async () => {
		mocks.client.reorderWatchlistSecurities
			.mockResolvedValueOnce(
				watchlist('wl-tech', 'Tech', [
					{ ...b(), position: 0 },
					{ ...a(), position: 1 },
					{ ...c(), position: 2 }
				])
			)
			.mockResolvedValueOnce(
				watchlist('wl-tech', 'Tech', [
					{ ...b(), position: 0 },
					{ ...c(), position: 1 },
					{ ...a(), position: 2 }
				])
			);
		renderPage([watchlist('wl-tech', 'Tech', [a(), b(), c()])]);
		await enableReorder();

		const handle = screen.getByRole('button', { name: 'Reorder AAPL' });
		handle.focus();
		await fireEvent.keyDown(handle, { key: 'ArrowDown' });

		await waitFor(() =>
			expect(mocks.client.reorderWatchlistSecurities).toHaveBeenCalledWith(
				'wl-tech',
				['s2', 's1', 's3'],
				undefined
			)
		);
		await waitFor(() => expect(rowSymbols()).toEqual(['MSFT', 'AAPL', 'NVDA']));
		expect(screen.getByRole('status')).toHaveTextContent('AAPL moved to position 2 of 3');

		// The keyed row survives the optimistic + server re-render, so focus and
		// subsequent keystrokes stay attached to the same security handle.
		expect(screen.getByRole('button', { name: 'Reorder AAPL' })).toBe(handle);
		await fireEvent.keyDown(handle, { key: 'ArrowDown' });
		await waitFor(() =>
			expect(mocks.client.reorderWatchlistSecurities).toHaveBeenLastCalledWith(
				'wl-tech',
				['s2', 's3', 's1'],
				undefined
			)
		);
	});

	it('does not move a security past the top or bottom boundary', async () => {
		renderPage([watchlist('wl-tech', 'Tech', [a(), b()])]);
		await enableReorder();

		await fireEvent.keyDown(screen.getByRole('button', { name: 'Reorder AAPL' }), {
			key: 'ArrowUp'
		});
		await fireEvent.keyDown(screen.getByRole('button', { name: 'Reorder MSFT' }), {
			key: 'ArrowDown'
		});

		expect(mocks.client.reorderWatchlistSecurities).not.toHaveBeenCalled();
	});

	it('shows no controls and ignores drops for non-custom sorts', async () => {
		renderPage([watchlist('wl-tech', 'Tech', [a(), b()], 'name_asc')]);

		expect(
			screen.queryByRole('button', { name: 'Reorder securities in Tech' })
		).not.toBeInTheDocument();
		expect(screen.queryByTestId('security-drag-handle')).not.toBeInTheDocument();

		const rows = within(screen.getByRole('region', { name: 'Tech securities' })).getAllByRole(
			'listitem'
		);
		const dt = dataTransfer();
		await fireEvent.dragStart(rows[0], { dataTransfer: dt });
		await fireEvent.dragOver(rows[1], { dataTransfer: dt });
		await fireEvent.drop(rows[1], { dataTransfer: dt });

		expect(mocks.client.reorderWatchlistSecurities).not.toHaveBeenCalled();
	});

	it('ignores drags when the toggle is off', async () => {
		renderPage([watchlist('wl-tech', 'Tech', [a(), b()])]);

		const rows = within(screen.getByRole('region', { name: 'Tech securities' })).getAllByRole(
			'listitem'
		);
		const dt = dataTransfer();
		await fireEvent.dragStart(rows[0], { dataTransfer: dt });
		await fireEvent.dragOver(rows[1], { dataTransfer: dt });
		await fireEvent.drop(rows[1], { dataTransfer: dt });

		expect(mocks.client.reorderWatchlistSecurities).not.toHaveBeenCalled();
	});

	it('resyncs, reverts the optimistic order and shows the error when the reorder fails', async () => {
		mocks.client.reorderWatchlistSecurities.mockRejectedValue(new Error('Reorder failed'));
		mocks.client.getWatchlists.mockResolvedValue([watchlist('wl-tech', 'Tech', [a(), b()])]);
		renderPage([watchlist('wl-tech', 'Tech', [a(), b()])]);
		await enableReorder();

		const rows = within(screen.getByRole('region', { name: 'Tech securities' })).getAllByRole(
			'listitem'
		);
		const dt = dataTransfer();
		await fireEvent.dragStart(rows[0], { dataTransfer: dt });
		await fireEvent.dragOver(rows[1], { dataTransfer: dt });
		await fireEvent.drop(rows[1], { dataTransfer: dt });

		expect(await screen.findByText('Reorder failed')).toBeInTheDocument();
		await waitFor(() => expect(mocks.client.getWatchlists).toHaveBeenCalled());
		await waitFor(() => expect(rowSymbols()).toEqual(['AAPL', 'MSFT']));
	});
});

describe('Watchlists page - layout stability during inline editing', () => {
	it('preserves header container height and classes across view and edit states', async () => {
		renderPage([techList()]);

		const section = screen.getByRole('region', { name: 'Tech securities' });
		const headerContainer = section.querySelector('.min-h-10.h-10');
		expect(headerContainer).toBeInTheDocument();
		expect(headerContainer).toHaveClass(
			'min-h-10',
			'h-10',
			'flex',
			'items-center',
			'justify-between'
		);

		// Switch to edit mode
		await fireEvent.click(screen.getByRole('button', { name: 'Rename Tech' }));

		const editHeaderContainer = section.querySelector('.min-h-10.h-10');
		expect(editHeaderContainer).toBeInTheDocument();
		expect(editHeaderContainer).toHaveClass(
			'min-h-10',
			'h-10',
			'flex',
			'items-center',
			'justify-between'
		);
		expect(screen.getByLabelText('Watchlist name')).toBeInTheDocument();

		// Switch back to view mode
		await fireEvent.click(screen.getByRole('button', { name: 'Cancel rename' }));

		const restoredHeaderContainer = section.querySelector('.min-h-10.h-10');
		expect(restoredHeaderContainer).toBeInTheDocument();
		expect(restoredHeaderContainer).toHaveClass(
			'min-h-10',
			'h-10',
			'flex',
			'items-center',
			'justify-between'
		);
		expect(screen.getByRole('heading', { level: 2, name: 'Tech' })).toBeInTheDocument();
	});
});

describe('Watchlists page - instant shell with async list', () => {
	it('renders the shell and skeleton rows before the async watchlists load resolves', async () => {
		let resolveWatchlists!: (value: WatchlistRead[]) => void;
		mocks.client.getWatchlists.mockReturnValue(
			new Promise<WatchlistRead[]>((resolve) => {
				resolveWatchlists = resolve;
			})
		);

		// The layout-owned service starts the initial fetch; its pending promise is what
		// drives the page's `isInitialLoading` skeleton path.
		const loadPromise = service.loadWatchlists();
		renderPage([]);

		// Titlebar, page actions and structure are up before any data arrives.
		expect(screen.getByRole('heading', { name: 'Watchlists' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Reorder' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Create watchlist' })).toBeInTheDocument();

		const status = screen.getByRole('status', { name: 'Loading watchlists' });
		expect(status.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(3);
		expect(screen.queryByRole('region')).not.toBeInTheDocument();
		expect(screen.queryByText("You don't have any watchlists yet")).not.toBeInTheDocument();

		resolveWatchlists([defaultList(), techList()]);
		await loadPromise;

		await waitFor(() =>
			expect(screen.getByRole('region', { name: 'Default securities' })).toBeInTheDocument()
		);
		expect(screen.getByRole('region', { name: 'Tech securities' })).toBeInTheDocument();
		expect(screen.queryByRole('status', { name: 'Loading watchlists' })).not.toBeInTheDocument();
		expect(mocks.client.getWatchlists).toHaveBeenCalledTimes(1);
	});

	it('fills in the real sections without re-navigating, and never fetches on its own', async () => {
		mocks.client.getWatchlists.mockResolvedValue([defaultList(), techList()]);
		renderPage([]);

		// Rendering the page alone must not fetch: the layout-owned service is the single
		// owner of the initial request, so no duplicate server + client request exists.
		expect(mocks.client.getWatchlists).not.toHaveBeenCalled();

		await service.loadWatchlists();

		await waitFor(() =>
			expect(screen.getByRole('region', { name: 'Default securities' })).toBeInTheDocument()
		);
		expect(screen.getByRole('region', { name: 'Tech securities' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { level: 2, name: 'Default' })).toBeInTheDocument();
		expect(screen.getByText('2 securities')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Sort securities in Default' })).toBeInTheDocument();
		expect(screen.queryByRole('status', { name: 'Loading watchlists' })).not.toBeInTheDocument();
		expect(mocks.client.getWatchlists).toHaveBeenCalledTimes(1);
	});

	it('applies the persisted watchlist order to the asynchronously loaded sections', async () => {
		mocks.client.getWatchlists.mockResolvedValue([defaultList(), techList()]);
		renderPage([], vi.fn(), ['wl-tech', 'wl-default']);

		await service.loadWatchlists();

		await waitFor(() => expect(screen.getAllByRole('region')).toHaveLength(2));
		const headings = screen
			.getAllByRole('region')
			.map((section) => within(section).getByRole('heading', { level: 2 }).textContent);
		expect(headings).toEqual(['Tech', 'Default']);
	});

	it('shows the destructive alert and keeps the shell when the async load fails', async () => {
		mocks.client.getWatchlists.mockRejectedValue(new Error('boom'));
		renderPage([]);

		await service.loadWatchlists();

		await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('boom'));
		expect(screen.getByRole('alert')).toHaveClass('text-destructive');
		// No SvelteKit error page: the shell and its actions survive the failed load.
		expect(screen.getByRole('heading', { name: 'Watchlists' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Create watchlist' })).toBeInTheDocument();
	});
});

describe('Watchlists page - shared error lifecycle', () => {
	it('clears the page-level error after a subsequent successful mutation', async () => {
		mocks.client.renameWatchlist.mockRejectedValue(new Error('Watchlist name already in use'));
		mocks.client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', []));
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Tech' }));
		const input = screen.getByLabelText('Watchlist name');
		await fireEvent.input(input, { target: { value: 'Default' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save Tech' }));

		expect(await screen.findByText('Watchlist name already in use')).toBeInTheDocument();
		expect(service.error).toBe('Watchlist name already in use');

		const section = screen.getByRole('region', { name: 'Tech securities' });
		await fireEvent.click(within(section).getByRole('button', { name: 'Remove NVDA' }));

		await waitFor(() => expect(service.error).toBeNull());
		await waitFor(() =>
			expect(screen.queryByText('Watchlist name already in use')).not.toBeInTheDocument()
		);
	});

	it('suppresses the page-level alert while the create modal owns the error', async () => {
		mocks.client.createWatchlist.mockRejectedValue(new Error('Name already taken'));
		renderPage([defaultList()]);

		await openCreateModal('Duplicate');

		expect(await screen.findByText('Name already taken')).toBeInTheDocument();
		// Only the modal alert renders; the page-level banner is suppressed.
		expect(screen.getAllByText('Name already taken')).toHaveLength(1);
	});
});
