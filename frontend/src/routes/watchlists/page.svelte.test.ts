import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import type { Component } from 'svelte';
import type { SecuritySchema, WatchlistRead } from '@/api/marketService';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

const mocks = vi.hoisted(() => ({
	client: {
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
