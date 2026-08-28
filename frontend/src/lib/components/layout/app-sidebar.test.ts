import { render, screen, fireEvent } from '@testing-library/svelte';
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
		symbol: 'C',
		exchange: 'NYSE',
		currency: 'USD',
		name: 'Citigroup Inc.',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	},
	{
		id: 'sec-2',
		symbol: 'BA',
		exchange: 'NYSE',
		currency: 'USD',
		name: 'Boeing Co.',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	},
	{
		id: 'sec-3',
		symbol: 'SPY',
		exchange: 'NYSE',
		currency: 'USD',
		name: 'SPDR S&P 500 ETF Trust',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	},
	{
		id: 'sec-4',
		symbol: 'AAPL',
		exchange: 'NASDAQ',
		currency: 'USD',
		name: 'Apple Inc.',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	},
	{
		id: 'sec-5',
		symbol: 'GOOGL',
		exchange: 'NASDAQ',
		currency: 'USD',
		name: 'Alphabet Inc.',
		isin: null,
		is_active: true,
		updated_at: '2026-01-01T00:00:00Z'
	}
];

describe('AppSidebar Modular Components', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('Header & Toggle', () => {
		it('renders portfolio dashboard link and sidebar trigger in expanded state', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: mockSecurities
				}
			});

			expect(screen.getByText('Portfolio dashboard')).toBeInTheDocument();
			const trigger = document.querySelector('[data-sidebar="trigger"]');
			expect(trigger).toBeInTheDocument();
		});

		it('renders sidebar trigger in collapsed state and allows toggling', async () => {
			render(AppSidebarTestHarness, {
				props: {
					open: false,
					securities: mockSecurities
				}
			});

			const trigger = document.querySelector('[data-sidebar="trigger"]') as HTMLElement;
			const container = document.querySelector('[data-slot="sidebar-container"]') as HTMLElement;
			const gap = document.querySelector('[data-slot="sidebar-gap"]') as HTMLElement;
			expect(trigger).toBeInTheDocument();
			expect(container).toHaveClass('w-12');
			expect(gap).toHaveClass('w-12');
			expect(screen.queryByText('Portfolio dashboard')).not.toBeInTheDocument();

			await fireEvent.click(trigger);
			expect(screen.getByText('Portfolio dashboard')).toBeInTheDocument();
			expect(container).toHaveClass('w-64');
			expect(gap).toHaveClass('w-64');
		});
	});

	describe('Actions', () => {
		it('renders search button and invokes global search callback on click', async () => {
			const onToggleSearch = vi.fn();
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: mockSecurities,
					onToggleGlobalSearch: onToggleSearch
				}
			});

			const searchBtn = screen.getByRole('button', { name: /search/i });
			expect(searchBtn).toBeInTheDocument();
			expect(screen.getByText('⌘')).toBeInTheDocument();
			expect(screen.getByText('P')).toBeInTheDocument();

			await fireEvent.click(searchBtn);
			expect(onToggleSearch).toHaveBeenCalledTimes(1);
		});
	});

	describe('Watchlist UI', () => {
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
			expect(screen.getByText('GOOGL')).toBeInTheDocument();
			expect(screen.getByText('Alphabet Inc.')).toBeInTheDocument();
		});

		it('centers and scales 1 to 5 char tickers in collapsed state without truncation', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: false,
					securities: mockSecurities
				}
			});

			// 1 char: 'C' -> text-xs
			const cTicker = screen.getByText('C');
			expect(cTicker).toBeInTheDocument();
			expect(cTicker).toHaveClass('text-xs');
			expect(cTicker).not.toHaveClass('truncate');

			// 2 chars: 'BA' -> text-xs
			const baTicker = screen.getByText('BA');
			expect(baTicker).toBeInTheDocument();
			expect(baTicker).toHaveClass('text-xs');
			expect(baTicker).not.toHaveClass('truncate');

			// 3 chars: 'SPY' -> text-[10px]
			const spyTicker = screen.getByText('SPY');
			expect(spyTicker).toBeInTheDocument();
			expect(spyTicker).toHaveClass('text-[10px]');
			expect(spyTicker).not.toHaveClass('truncate');

			// 4 chars: 'AAPL' -> text-[10px]
			const aaplTicker = screen.getByText('AAPL');
			expect(aaplTicker).toBeInTheDocument();
			expect(aaplTicker).toHaveClass('text-[10px]');
			expect(aaplTicker).not.toHaveClass('truncate');

			// 5 chars: 'GOOGL' -> text-[8.5px]
			const googlTicker = screen.getByText('GOOGL');
			expect(googlTicker).toBeInTheDocument();
			expect(googlTicker).toHaveClass('text-[8.5px]');
			expect(googlTicker).not.toHaveClass('truncate');

			// Company names should not be rendered in collapsed view
			expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument();
			expect(screen.queryByText('Alphabet Inc.')).not.toBeInTheDocument();
		});
	});

	describe('Profile & Rail', () => {
		it('displays user email in expanded state and user icon in collapsed state', () => {
			const { rerender } = render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: mockSecurities
				}
			});

			expect(screen.getByText('test@example.com')).toBeInTheDocument();

			rerender({
				open: false,
				securities: mockSecurities
			});

			expect(screen.queryByText('test@example.com')).not.toBeInTheDocument();
			const userIcon = document.querySelector('svg.lucide-circle-user');
			expect(userIcon).toBeInTheDocument();
		});

		it('renders sidebar rail for resizing/toggling', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: mockSecurities
				}
			});

			const rail = document.querySelector('[data-sidebar="rail"]');
			expect(rail).toBeInTheDocument();
		});
	});
});
