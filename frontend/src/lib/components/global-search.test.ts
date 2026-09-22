import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import GlobalSearch from './global-search.svelte';
import GlobalSearchTestHarness from './global-search.test-harness.svelte';
import type { WatchlistRead, WatchlistSecuritySchema } from '@/api/marketService';
import { WatchlistService } from '$lib/components/watchlist/watchlistService.svelte';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

const mocks = vi.hoisted(() => ({
	marketService: {
		search: vi.fn(),
		createOrUpdateSecurity: vi.fn()
	},
	service: null as unknown
}));

vi.mock('@/api/marketService', () => ({
	marketService: mocks.marketService,
	getMarketService: () => mocks.marketService
}));

vi.mock('$lib/components/watchlist/watchlistService.svelte', async (importOriginal) => {
	const actual =
		await importOriginal<typeof import('$lib/components/watchlist/watchlistService.svelte')>();
	return {
		...actual,
		getWatchlistService: () => mocks.service
	};
});

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

function watchlist(id: string, name: string, securities: WatchlistSecuritySchema[]): WatchlistRead {
	return { id, user_id: 'user-1', name, sort: 'custom', securities };
}

describe('GlobalSearch component', () => {
	let service: WatchlistService;

	beforeEach(() => {
		vi.resetAllMocks();
		service = new WatchlistService();
		mocks.service = service;
	});

	it('renders default placeholder when targetWatchlist is null', () => {
		render(GlobalSearch, {
			props: {
				open: true,
				targetWatchlist: null
			}
		});

		expect(screen.getByPlaceholderText('Search for a company or symbol...')).toBeInTheDocument();
	});

	it('renders targeted placeholder when targetWatchlist is provided', () => {
		const target = watchlist('wl-tech', 'Tech Focus', []);
		render(GlobalSearch, {
			props: {
				open: true,
				targetWatchlist: target
			}
		});

		expect(
			screen.getByPlaceholderText('Search securities to add to Tech Focus...')
		).toBeInTheDocument();
	});

	it('toggles security on default watchlist when targetWatchlist is not set', async () => {
		const defaultSec = security('sec-1', 'AAPL');
		service.watchlists = [watchlist('wl-def', 'Default', [defaultSec])];
		vi.spyOn(service, 'toggleSecurity').mockResolvedValue();

		mocks.marketService.search.mockResolvedValue([
			{ code: 'AAPL', exchange: 'NASDAQ', name: 'Apple Inc.', security_type: 'Stock' }
		]);

		render(GlobalSearch, {
			props: {
				open: true,
				targetWatchlist: null
			}
		});

		const input = screen.getByPlaceholderText('Search for a company or symbol...');
		await fireEvent.input(input, { target: { value: 'AAPL' } });

		await waitFor(() => expect(mocks.marketService.search).toHaveBeenCalledWith('AAPL'));

		const toggleBtn = await screen.findByRole('button', { name: 'Toggle watchlist' });
		const starSvg = toggleBtn.querySelector('svg');
		expect(starSvg).toHaveClass('fill-amber-400');

		await fireEvent.click(toggleBtn);
		expect(service.toggleSecurity).toHaveBeenCalledWith('sec-1');
	});

	it('adds security to targeted watchlist when security is not yet a member', async () => {
		const target = watchlist('wl-tech', 'Tech', []);
		service.watchlists = [target];
		vi.spyOn(service, 'addSecurityToWatchlist').mockResolvedValue();
		mocks.marketService.createOrUpdateSecurity.mockResolvedValue({
			security_id: 'sec-nvda',
			symbol: 'NVDA',
			exchange: 'NASDAQ',
			name: 'Nvidia',
			has_price_data: true
		});
		mocks.marketService.search.mockResolvedValue([
			{ code: 'NVDA', exchange: 'NASDAQ', name: 'Nvidia', security_type: 'Stock' }
		]);

		render(GlobalSearch, {
			props: {
				open: true,
				targetWatchlist: target
			}
		});

		const input = screen.getByPlaceholderText('Search securities to add to Tech...');
		await fireEvent.input(input, { target: { value: 'NVDA' } });

		await waitFor(() => expect(mocks.marketService.search).toHaveBeenCalledWith('NVDA'));

		const toggleBtn = await screen.findByRole('button', { name: 'Toggle watchlist' });
		const starSvg = toggleBtn.querySelector('svg');
		expect(starSvg).not.toHaveClass('fill-amber-400');

		await fireEvent.click(toggleBtn);

		expect(mocks.marketService.createOrUpdateSecurity).toHaveBeenCalledWith({
			code: 'NVDA',
			exchange: 'NASDAQ',
			name: 'Nvidia',
			currency: 'USD'
		});
		expect(service.addSecurityToWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-nvda');
	});

	it('removes security from targeted watchlist when security is already a member', async () => {
		const nvdaSec = security('sec-nvda', 'NVDA');
		const target = watchlist('wl-tech', 'Tech', [nvdaSec]);
		service.watchlists = [target];
		vi.spyOn(service, 'removeSecurityFromWatchlist').mockResolvedValue();
		mocks.marketService.search.mockResolvedValue([
			{ code: 'NVDA', exchange: 'NASDAQ', name: 'NVDA Inc.', security_type: 'Stock' }
		]);

		render(GlobalSearch, {
			props: {
				open: true,
				targetWatchlist: target
			}
		});

		const input = screen.getByPlaceholderText('Search securities to add to Tech...');
		await fireEvent.input(input, { target: { value: 'NVDA' } });

		await waitFor(() => expect(mocks.marketService.search).toHaveBeenCalledWith('NVDA'));

		const toggleBtn = await screen.findByRole('button', { name: 'Toggle watchlist' });
		const starSvg = toggleBtn.querySelector('svg');
		expect(starSvg).toHaveClass('fill-amber-400');

		await fireEvent.click(toggleBtn);
		expect(service.removeSecurityFromWatchlist).toHaveBeenCalledWith('wl-tech', 'sec-nvda');
	});

	it('resets query, results, and targetWatchlist when closed', async () => {
		const target = watchlist('wl-tech', 'Tech', []);
		service.watchlists = [target];
		mocks.marketService.search.mockResolvedValue([
			{ code: 'NVDA', exchange: 'NASDAQ', name: 'Nvidia', security_type: 'Stock' }
		]);

		render(GlobalSearchTestHarness, {
			props: {
				initialOpen: true,
				initialTarget: target
			}
		});

		expect(screen.getByTestId('target-name')).toHaveTextContent('Tech');
		const input = screen.getByPlaceholderText('Search securities to add to Tech...');
		await fireEvent.input(input, { target: { value: 'NVDA' } });
		await waitFor(() => expect(mocks.marketService.search).toHaveBeenCalledWith('NVDA'));

		// Close modal
		await fireEvent.click(screen.getByRole('button', { name: 'Close search' }));
		await waitFor(() => expect(screen.getByTestId('target-name')).toHaveTextContent('none'));

		// Reopen modal
		await fireEvent.click(screen.getByRole('button', { name: 'Open search' }));
		expect(screen.getByPlaceholderText('Search for a company or symbol...')).toBeInTheDocument();
		expect(screen.queryByText(/NVDA/)).not.toBeInTheDocument();
	});
});
