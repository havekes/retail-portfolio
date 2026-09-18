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
		getWatchlists: vi.fn(),
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

function renderPage(watchlists: WatchlistRead[]) {
	return render(PageComponent, { props: { data: { watchlists } } });
}

async function submitCreate(name: string) {
	const input = screen.getByLabelText('New watchlist name') as HTMLInputElement;
	await fireEvent.input(input, { target: { value: name } });
	await fireEvent.submit(screen.getByRole('form', { name: 'Create watchlist' }));
	return input;
}

async function selectWatchlist(name: string) {
	await fireEvent.click(screen.getByRole('button', { name }));
}

async function searchFor(text: string) {
	const input = screen.getByLabelText('Search securities to add');
	await fireEvent.input(input, { target: { value: text } });
}

describe('Watchlists page - rendering', () => {
	it('renders every watchlist with its security count', () => {
		renderPage([defaultList(), techList()]);

		expect(screen.getByText('Default')).toBeInTheDocument();
		expect(screen.getByText('Tech')).toBeInTheDocument();
		expect(screen.getByText('2 securities')).toBeInTheDocument();
		expect(screen.getByText('1 security')).toBeInTheDocument();
	});

	it('renders the empty state when there are no watchlists', () => {
		renderPage([]);

		expect(screen.getByText(/don't have any watchlists yet/i)).toBeInTheDocument();
		expect(screen.queryByRole('list', { name: 'Watchlists' })).not.toBeInTheDocument();
	});

	it('renders the loading state while the service has no data yet', () => {
		service.isLoading = true;
		renderPage([]);

		expect(screen.getByRole('status', { name: 'Loading watchlists' })).toBeInTheDocument();
	});
});

describe('Watchlists page - create', () => {
	it('adds a created watchlist to the list without a reload and clears the input', async () => {
		mocks.client.createWatchlist.mockResolvedValue(watchlist('wl-growth', 'Growth', []));
		renderPage([]);

		const input = await submitCreate('Growth');

		await waitFor(() =>
			expect(mocks.client.createWatchlist).toHaveBeenCalledWith('Growth', undefined)
		);
		expect(await screen.findByText('Growth')).toBeInTheDocument();
		expect(input.value).toBe('');
	});

	it('shows the backend error message when creation fails', async () => {
		mocks.client.createWatchlist.mockRejectedValue(new Error('Watchlist already exists'));
		renderPage([]);

		await submitCreate('Default');

		expect(await screen.findByText('Watchlist already exists')).toBeInTheDocument();
	});
});

describe('Watchlists page - rename', () => {
	it('updates the displayed name after a successful rename', async () => {
		mocks.client.renameWatchlist.mockResolvedValue(
			watchlist('wl-default', 'Core', [security('sec-1', 'AAPL')])
		);
		renderPage([defaultList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Default' }));
		const input = screen.getByLabelText('Watchlist name');
		await fireEvent.input(input, { target: { value: 'Core' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save Default' }));

		await waitFor(() =>
			expect(mocks.client.renameWatchlist).toHaveBeenCalledWith('wl-default', 'Core', undefined)
		);
		expect(await screen.findByText('Core')).toBeInTheDocument();
		expect(screen.queryByText('Default')).not.toBeInTheDocument();
	});

	it('shows the backend error message when renaming fails', async () => {
		mocks.client.renameWatchlist.mockRejectedValue(new Error('Watchlist name already in use'));
		renderPage([defaultList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Rename Default' }));
		const input = screen.getByLabelText('Watchlist name');
		await fireEvent.input(input, { target: { value: 'Core' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Save Default' }));

		expect(await screen.findByText('Watchlist name already in use')).toBeInTheDocument();
		expect(screen.getByLabelText('Watchlist name')).toHaveValue('Core');
		expect(service.watchlists[0].name).toBe('Default');
	});
});

describe('Watchlists page - delete', () => {
	it('removes the watchlist after confirmation', async () => {
		mocks.client.deleteWatchlist.mockResolvedValue(undefined);
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete Tech' }));
		expect(await screen.findByText('Delete watchlist')).toBeInTheDocument();
		await fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

		await waitFor(() =>
			expect(mocks.client.deleteWatchlist).toHaveBeenCalledWith('wl-tech', undefined)
		);
		await waitFor(() => expect(screen.queryByText('Tech')).not.toBeInTheDocument());
		expect(screen.getByText('Default')).toBeInTheDocument();
	});

	it('keeps the watchlist when the confirmation is cancelled', async () => {
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete Tech' }));
		await fireEvent.click(await screen.findByRole('button', { name: 'Cancel' }));

		expect(mocks.client.deleteWatchlist).not.toHaveBeenCalled();
		expect(screen.getByText('Tech')).toBeInTheDocument();
	});

	it('shows the backend error message when deletion fails', async () => {
		mocks.client.deleteWatchlist.mockRejectedValue(new Error('Watchlist not found'));
		renderPage([defaultList(), techList()]);

		await fireEvent.click(screen.getByRole('button', { name: 'Delete Tech' }));
		await fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }));

		expect(await screen.findByText('Watchlist not found')).toBeInTheDocument();
		expect(screen.getByText('Tech')).toBeInTheDocument();
	});
});

describe('Watchlists page - detail view', () => {
	it('shows the selected watchlist securities with links to the security page', async () => {
		renderPage([defaultList(), techList()]);

		await selectWatchlist('Default');

		const section = screen.getByRole('region', { name: 'Default securities' });
		expect(within(section).getByRole('link', { name: 'AAPL' })).toHaveAttribute(
			'href',
			'/security/sec-1'
		);
		expect(within(section).getByRole('link', { name: 'MSFT' })).toHaveAttribute(
			'href',
			'/security/sec-2'
		);
		expect(within(section).queryByRole('link', { name: 'NVDA' })).not.toBeInTheDocument();
	});

	it('does not render a detail view until a watchlist is selected', () => {
		renderPage([defaultList(), techList()]);

		expect(screen.queryByRole('region', { name: 'Default securities' })).not.toBeInTheDocument();
	});

	it('swaps the detail view when another watchlist is selected', async () => {
		renderPage([defaultList(), techList()]);

		await selectWatchlist('Tech');

		const section = screen.getByRole('region', { name: 'Tech securities' });
		expect(within(section).getByRole('link', { name: 'NVDA' })).toHaveAttribute(
			'href',
			'/security/sec-3'
		);
	});
});

describe('Watchlists page - add security', () => {
	function mockAddToDefault() {
		mocks.client.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-3',
			symbol: 'NVDA',
			exchange: 'NASDAQ',
			name: 'NVDA Inc.',
			has_price_data: true
		});
		mocks.client.addSecurityToWatchlist.mockResolvedValue(
			watchlist('wl-default', 'Default', [
				security('sec-1', 'AAPL'),
				security('sec-2', 'MSFT'),
				security('sec-3', 'NVDA')
			])
		);
	}

	it('searches the market and adds the selected security to the active list', async () => {
		mocks.client.search.mockResolvedValue([
			{ code: 'NVDA', exchange: 'NASDAQ', name: 'NVDA Inc.', security_type: 'Stock' }
		]);
		mockAddToDefault();
		renderPage([defaultList()]);
		await selectWatchlist('Default');

		await searchFor('NV');
		await waitFor(() => expect(mocks.client.search).toHaveBeenCalledWith('NV'), { timeout: 2000 });
		await fireEvent.click(await screen.findByRole('option', { name: /NVDA/ }));

		await waitFor(() =>
			expect(mocks.client.addSecurityToWatchlist).toHaveBeenCalledWith(
				'wl-default',
				'sec-3',
				undefined
			)
		);
		expect(mocks.client.createOrUpdateSecurity).toHaveBeenCalledWith({
			code: 'NVDA',
			exchange: 'NASDAQ',
			name: 'NVDA Inc.',
			currency: 'USD'
		});
		const section = screen.getByRole('region', { name: 'Default securities' });
		expect(await within(section).findByRole('link', { name: 'NVDA' })).toBeInTheDocument();
		expect(within(section).getByText('3 securities')).toBeInTheDocument();
	});

	it('does not search until the query has at least two characters', async () => {
		renderPage([defaultList()]);
		await selectWatchlist('Default');

		await searchFor('N');
		await new Promise((resolve) => setTimeout(resolve, 400));

		expect(mocks.client.search).not.toHaveBeenCalled();
	});

	it('is a no-op when the resolved security is already in the list', async () => {
		mocks.client.search.mockResolvedValue([
			{ code: 'AAPL', exchange: 'NASDAQ', name: 'AAPL Inc.', security_type: 'Stock' }
		]);
		mocks.client.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-1',
			symbol: 'AAPL',
			exchange: 'NASDAQ',
			name: 'AAPL Inc.',
			has_price_data: true
		});
		renderPage([defaultList()]);
		await selectWatchlist('Default');

		await searchFor('AA');
		await waitFor(() => expect(mocks.client.search).toHaveBeenCalledWith('AA'), { timeout: 2000 });
		await fireEvent.click(await screen.findByRole('option', { name: /AAPL/ }));

		await waitFor(() => expect(mocks.client.createOrUpdateSecurity).toHaveBeenCalled());
		await new Promise((resolve) => setTimeout(resolve, 50));

		expect(mocks.client.addSecurityToWatchlist).not.toHaveBeenCalled();
		const section = screen.getByRole('region', { name: 'Default securities' });
		expect(within(section).getAllByRole('link', { name: 'AAPL' })).toHaveLength(1);
		expect(within(section).getByText('2 securities')).toBeInTheDocument();
	});

	it('shows the backend error and leaves the list intact when adding fails', async () => {
		mocks.client.search.mockResolvedValue([
			{ code: 'NVDA', exchange: 'NASDAQ', name: 'NVDA Inc.', security_type: 'Stock' }
		]);
		mocks.client.createOrUpdateSecurity.mockRejectedValue(new Error('Security lookup failed'));
		renderPage([defaultList()]);
		await selectWatchlist('Default');

		await searchFor('NV');
		await waitFor(() => expect(mocks.client.search).toHaveBeenCalledWith('NV'), { timeout: 2000 });
		await fireEvent.click(await screen.findByRole('option', { name: /NVDA/ }));

		expect(await screen.findByText('Security lookup failed')).toBeInTheDocument();
		expect(mocks.client.addSecurityToWatchlist).not.toHaveBeenCalled();
		const section = screen.getByRole('region', { name: 'Default securities' });
		expect(within(section).getByRole('link', { name: 'AAPL' })).toBeInTheDocument();
		expect(within(section).getByText('2 securities')).toBeInTheDocument();
	});
});

describe('Watchlists page - remove security', () => {
	it('removes the security and updates the count', async () => {
		mocks.client.removeSecurityFromWatchlist.mockResolvedValue(watchlist('wl-tech', 'Tech', []));
		renderPage([defaultList(), techList()]);
		await selectWatchlist('Tech');

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
			expect(within(section).queryByRole('link', { name: 'NVDA' })).not.toBeInTheDocument()
		);
		expect(within(section).getByText('0 securities')).toBeInTheDocument();
		expect(within(section).getByText('No securities in this watchlist yet.')).toBeInTheDocument();
	});

	it('shows the backend error and keeps the row when removal fails', async () => {
		mocks.client.removeSecurityFromWatchlist.mockRejectedValue(new Error('Security not found'));
		renderPage([defaultList(), techList()]);
		await selectWatchlist('Tech');

		const section = screen.getByRole('region', { name: 'Tech securities' });
		await fireEvent.click(within(section).getByRole('button', { name: 'Remove NVDA' }));

		expect(await screen.findByText('Security not found')).toBeInTheDocument();
		expect(within(section).getByRole('link', { name: 'NVDA' })).toBeInTheDocument();
		expect(within(section).getByText('1 security')).toBeInTheDocument();
	});
});
