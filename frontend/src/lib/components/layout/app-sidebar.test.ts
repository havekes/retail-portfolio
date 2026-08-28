import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AppSidebarTestHarness from './app-sidebar.test-harness.svelte';
import type { SecuritySchema } from '$lib/api/marketService';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/stores', async () => {
	const { readable } = await import('svelte/store');
	return {
		page: readable({
			data: { user: { id: 'u1', email: 'test@example.com' } }
		})
	};
});

vi.mock('$lib/api/marketService', () => ({
	getMarketService: () => ({
		getWatchlists: vi.fn().mockResolvedValue([]),
		getWatchlistSecurities: vi.fn().mockResolvedValue({ items: [] }),
		addToWatchlist: vi.fn(),
		removeFromWatchlist: vi.fn()
	})
}));

if (typeof window !== 'undefined') {
	Object.defineProperty(window, 'matchMedia', {
		writable: true,
		value: vi.fn().mockImplementation((query) => ({
			matches: false,
			media: query,
			onchange: null,
			addListener: vi.fn(),
			removeListener: vi.fn(),
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			dispatchEvent: vi.fn()
		}))
	});
}

const mockSecurities: SecuritySchema[] = [
	{
		id: 'sec-1',
		symbol: 'AAPL',
		exchange: 'NASDAQ',
		currency: 'USD',
		name: 'Apple Inc.',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	},
	{
		id: 'sec-2',
		symbol: 'MSFT',
		exchange: 'NASDAQ',
		currency: 'USD',
		name: 'Microsoft Corporation',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	}
];

describe('AppSidebar Watchlist UI', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('does not display a star icon on watchlist items', () => {
		render(AppSidebarTestHarness, {
			props: {
				open: true,
				securities: mockSecurities
			}
		});

		const starIcons = document.querySelectorAll('svg.lucide-star');
		expect(starIcons.length).toBe(0);
	});

	it('displays ticker and company name when sidebar is expanded', () => {
		render(AppSidebarTestHarness, {
			props: {
				open: true,
				securities: mockSecurities
			}
		});

		expect(screen.getByText('AAPL')).toBeInTheDocument();
		expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
		expect(screen.getByText('MSFT')).toBeInTheDocument();
		expect(screen.getByText('Microsoft Corporation')).toBeInTheDocument();
	});

	it('displays only the smaller ticker without company name when sidebar is collapsed', () => {
		render(AppSidebarTestHarness, {
			props: {
				open: false,
				securities: mockSecurities
			}
		});

		const aaplTicker = screen.getByText('AAPL');
		expect(aaplTicker).toBeInTheDocument();
		expect(aaplTicker).toHaveClass('text-[10px]');
		expect(aaplTicker).not.toHaveClass('truncate');

		const msftTicker = screen.getByText('MSFT');
		expect(msftTicker).toBeInTheDocument();
		expect(msftTicker).toHaveClass('text-[10px]');
		expect(msftTicker).not.toHaveClass('truncate');

		expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument();
		expect(screen.queryByText('Microsoft Corporation')).not.toBeInTheDocument();
	});
});
