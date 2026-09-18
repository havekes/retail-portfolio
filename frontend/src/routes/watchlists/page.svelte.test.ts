import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/svelte';
import type { Component } from 'svelte';
import type { SecuritySchema, WatchlistRead } from '@/api/marketService';

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
		deleteWatchlist: vi.fn(),
		addSecurityToWatchlist: vi.fn(),
		removeSecurityFromWatchlist: vi.fn(),
		addToWatchlist: vi.fn(),
		removeFromWatchlist: vi.fn()
	},
	service: null as unknown
}));

vi.mock('@/api/marketService', () => ({
	getMarketService: () => mocks.client
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
	service = new WatchlistService();
	mocks.service = service;
});

function renderPage(
	watchlists: WatchlistRead[],
	openGlobalSearch: (watchlist?: WatchlistRead | null) => void = vi.fn()
) {
	return render(PageComponent, {
		props: { data: { watchlists } },
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
