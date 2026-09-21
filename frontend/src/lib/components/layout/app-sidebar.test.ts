import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AppSidebarTestHarness from './app-sidebar.test-harness.svelte';
import type { SecuritySchema } from '$lib/api/marketService';
import { userPreferencesService } from '$lib/api/userPreferencesService';

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

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		patchPreferences: vi.fn().mockResolvedValue({})
	}
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
			expect(screen.getByText('/')).toBeInTheDocument();

			await fireEvent.click(searchBtn);
			expect(onToggleSearch).toHaveBeenCalledTimes(1);
		});

		it('shows keyboard shortcut hints for Watchlists and Holdings', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: mockSecurities
				}
			});

			const watchlistsLink = screen.getByRole('link', { name: /watchlists/i });
			expect(watchlistsLink).toHaveTextContent('w');

			const holdingsLink = screen.getByRole('link', { name: /holdings/i });
			expect(holdingsLink).toHaveTextContent('h');
		});

		it('hides the shortcut hints in the collapsed rail', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: false,
					securities: mockSecurities
				}
			});

			for (const hint of Array.from(document.querySelectorAll('[data-slot="kbd-group"]'))) {
				expect(hint).toHaveClass('group-data-[collapsible=icon]:hidden');
			}
		});

		it('renders the Watchlists link directly below Search in the sidebar content', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: mockSecurities
				}
			});

			const searchBtn = screen.getByRole('button', { name: /search/i });
			const watchlistsLink = screen.getByRole('link', { name: /watchlists/i });

			expect(watchlistsLink.closest('[data-slot="sidebar-header"]')).toBeNull();
			expect(searchBtn.closest('[data-slot="sidebar-group"]')).toBe(
				watchlistsLink.closest('[data-slot="sidebar-group"]')
			);
			// Watchlists link follows the Search button in DOM order.
			expect(
				searchBtn.compareDocumentPosition(watchlistsLink) & Node.DOCUMENT_POSITION_FOLLOWING
			).toBeTruthy();
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

	describe('Watchlist sidebar navigation', () => {
		const tech = {
			id: 'w1',
			user_id: 'u1',
			name: 'Tech',
			securities: [mockSecurities[3], mockSecurities[4]]
		};
		const energy = {
			id: 'w2',
			user_id: 'u1',
			name: 'Energy',
			securities: [mockSecurities[2]]
		};

		it('renders each watchlist as its own group with security links by default', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [tech, energy]
				}
			});

			expect(screen.getByText('Tech')).toBeInTheDocument();
			expect(screen.getByText('Energy')).toBeInTheDocument();

			const aaplLink = screen.getByText('AAPL').closest('a');
			expect(aaplLink).toHaveAttribute('href', '/security/sec-4');
			const spyLink = screen.getByText('SPY').closest('a');
			expect(spyLink).toHaveAttribute('href', '/security/sec-3');
			expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
		});

		it('shows numeric shortcut hints on default watchlist tickers only', () => {
			const defaultList = {
				id: 'w-default',
				user_id: 'u1',
				name: 'Default',
				securities: [mockSecurities[0], mockSecurities[1]]
			};
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [defaultList, tech]
				}
			});

			const expected: [string, string][] = [
				['C', '1'],
				['BA', '2']
			];
			for (const [ticker, hint] of expected) {
				const link = screen.getByText(ticker).closest('a') as HTMLElement;
				expect(link.querySelector('[data-slot="kbd"]')?.textContent).toBe(hint);
			}

			// Non-default watchlist tickers get no shortcut hint.
			const aaplLink = screen.getByText('AAPL').closest('a') as HTMLElement;
			expect(aaplLink.querySelector('[data-slot="kbd"]')).toBeNull();
		});

		it('maps the tenth default watchlist ticker to 0', () => {
			const securities = Array.from({ length: 10 }, (_, index) => ({
				...mockSecurities[0],
				id: `sec-${index}`,
				symbol: `S${index}`
			}));
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [{ id: 'w-default', user_id: 'u1', name: 'Default', securities }]
				}
			});

			const defaultGroup = screen
				.getByText('Default')
				.closest('[data-sidebar="group"]') as HTMLElement;
			const hints = Array.from(defaultGroup.querySelectorAll('[data-slot="kbd"]')).map(
				(kbd) => kbd.textContent
			);
			expect(hints).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']);
		});

		it('renders a muted empty state for a watchlist without securities', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [{ id: 'w3', user_id: 'u1', name: 'Empty', securities: [] }]
				}
			});

			expect(screen.getByText('Empty')).toBeInTheDocument();
			expect(screen.getByText('No securities')).toBeInTheDocument();
		});

		it('does not render a watchlist visibility toggle in the sidebar', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [tech, energy]
				}
			});

			expect(screen.queryByRole('button', { name: /show watchlists/i })).not.toBeInTheDocument();
			expect(screen.queryByRole('button', { name: /hide watchlists/i })).not.toBeInTheDocument();
		});

		it('shows only the default watchlist tickers and no names in the collapsed rail', () => {
			const defaultList = {
				id: 'w-default',
				user_id: 'u1',
				name: 'Default',
				securities: [mockSecurities[0], mockSecurities[1]]
			};
			render(AppSidebarTestHarness, {
				props: {
					open: false,
					securities: [],
					watchlists: [defaultList, tech, energy]
				}
			});

			// Default watchlist tickers are rendered.
			expect(screen.getByText('C')).toBeInTheDocument();
			expect(screen.getByText('BA')).toBeInTheDocument();

			// The default watchlist group stays visible; other watchlists are hidden entirely.
			const defaultGroup = screen
				.getByText('Default')
				.closest('[data-sidebar="group"]') as HTMLElement;
			expect(defaultGroup).not.toHaveClass('group-data-[collapsible=icon]:hidden!');
			for (const name of ['Tech', 'Energy']) {
				const group = screen.getByText(name).closest('[data-sidebar="group"]') as HTMLElement;
				expect(group).toHaveClass('group-data-[collapsible=icon]:hidden!');
			}

			// No watchlist name label is shown in the collapsed rail.
			for (const name of ['Default', 'Tech', 'Energy']) {
				const label = screen.getByText(name).closest('[data-sidebar="group-label"]') as HTMLElement;
				expect(label).toHaveClass('group-data-[collapsible=icon]:hidden!');
			}
		});

		it('hides the Watchlists group header in the collapsed rail', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: false,
					securities: [],
					watchlists: [tech, energy]
				}
			});

			const header = screen
				.getByText('Watchlists', { selector: '[data-sidebar="group-label"]' })
				.closest('[data-sidebar="group"]') as HTMLElement;
			expect(header).toHaveClass('group-data-[collapsible=icon]:hidden!');
		});

		it('does not truncate long watchlist names in expanded mode', () => {
			const longName = 'Long-term compounders and dividend growth ideas';
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [
						{ id: 'w-long', user_id: 'u1', name: longName, securities: [mockSecurities[3]] }
					]
				}
			});

			const nameSpan = screen.getByText(longName);
			expect(nameSpan).not.toHaveClass('truncate');
			expect(nameSpan).toHaveClass('whitespace-normal');
			expect(nameSpan.closest('[data-sidebar="group-label"]')).toHaveAttribute('title', longName);
		});

		it('collapses only the watchlist whose caret is clicked and persists to preferences', async () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [tech, energy]
				}
			});

			expect(screen.getByText('AAPL')).toBeInTheDocument();
			expect(screen.getByText('GOOGL')).toBeInTheDocument();
			expect(screen.getByText('SPY')).toBeInTheDocument();

			await fireEvent.click(screen.getByRole('button', { name: 'Toggle Tech' }));

			expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
			expect(screen.queryByText('GOOGL')).not.toBeInTheDocument();
			expect(screen.getByText('SPY')).toBeInTheDocument();
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				collapsed_watchlist_ids: ['w1']
			});

			await fireEvent.click(screen.getByRole('button', { name: 'Toggle Tech' }));
			expect(screen.getByText('AAPL')).toBeInTheDocument();
			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				collapsed_watchlist_ids: []
			});
		});

		it('respects initial collapsed state from initialCollapsedWatchlistIds', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [tech, energy],
					initialCollapsedWatchlistIds: ['w1']
				}
			});

			expect(screen.queryByText('AAPL')).not.toBeInTheDocument();
			expect(screen.queryByText('GOOGL')).not.toBeInTheDocument();
			expect(screen.getByText('SPY')).toBeInTheDocument();
		});

		it('shows ticker-only tickers in collapsed mode for watchlist securities', () => {
			render(AppSidebarTestHarness, {
				props: {
					open: false,
					securities: [],
					watchlists: [tech]
				}
			});

			const googlTicker = screen.getByText('GOOGL');
			expect(googlTicker).toHaveClass('text-[8.5px]');
			expect(googlTicker).not.toHaveClass('truncate');
			expect(screen.queryByText('Alphabet Inc.')).not.toBeInTheDocument();
		});

		it('renders watchlists ordered according to initialWatchlistOrder', () => {
			const crypto = {
				id: 'w3',
				user_id: 'u1',
				name: 'Crypto',
				securities: []
			};
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [tech, energy, crypto],
					initialWatchlistOrder: ['w2', 'w3', 'w1']
				}
			});

			const labels = Array.from(document.querySelectorAll('[data-sidebar="group-label"]'))
				.map((el) => el.textContent?.trim())
				.filter((text) => ['Tech', 'Energy', 'Crypto'].includes(text ?? ''));

			expect(labels).toEqual(['Energy', 'Crypto', 'Tech']);
		});

		it('appends unlisted watchlists gracefully when initialWatchlistOrder is partial', () => {
			const crypto = {
				id: 'w3',
				user_id: 'u1',
				name: 'Crypto',
				securities: []
			};
			render(AppSidebarTestHarness, {
				props: {
					open: true,
					securities: [],
					watchlists: [tech, energy, crypto],
					initialWatchlistOrder: ['w3']
				}
			});

			const labels = Array.from(document.querySelectorAll('[data-sidebar="group-label"]'))
				.map((el) => el.textContent?.trim())
				.filter((text) => ['Tech', 'Energy', 'Crypto'].includes(text ?? ''));

			expect(labels).toEqual(['Crypto', 'Tech', 'Energy']);
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
