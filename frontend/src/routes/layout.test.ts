import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Layout from './+layout.svelte';
import { load } from './+layout.server';
import { createRawSnippet } from 'svelte';
import { goto, preloadData } from '$app/navigation';
import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
import { getUserPreferencesService } from '$lib/api/userPreferencesService';
import { ApiError } from '$lib/api/apiClient';

const marketMocks = vi.hoisted(() => ({
	getWatchlists: vi.fn(),
	getWatchlistSecurities: vi.fn()
}));

vi.mock('mode-watcher', () => ({
	ModeWatcher: () => null
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn(),
	preloadData: vi.fn()
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
	getMarketService: () => marketMocks
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		patchPreferences: vi.fn().mockResolvedValue({})
	},
	getUserPreferencesService: vi.fn()
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

describe('Root +layout.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// `clearAllMocks` keeps implementations, so reset explicitly: the async
		// watchlists load must default to a successful, empty response per test.
		marketMocks.getWatchlists.mockReset().mockResolvedValue([]);
		marketMocks.getWatchlistSecurities.mockReset().mockResolvedValue({ items: [] });
		// Bare `vi.fn()` returns undefined, which the layout's `.catch()` would
		// reject on, so every prefetch defaults to a resolved navigation result.
		vi.mocked(preloadData).mockReset().mockResolvedValue({ type: 'loaded', status: 200, data: {} });
	});

	it('renders children without Sidebar.Provider / AppSidebar when unauthenticated', () => {
		const children = createRawSnippet(() => ({
			render: () => '<div data-testid="page-content">Login Page Content</div>'
		}));

		render(Layout, {
			props: {
				data: {
					user: null,
					sidebar_open: true,
					collapsed_watchlist_ids: [],
					watchlist_order: null
				},
				children
			}
		});

		expect(screen.getByTestId('page-content')).toBeInTheDocument();
		expect(screen.queryByText('Portfolio dashboard')).not.toBeInTheDocument();
	});

	it('renders Sidebar.Provider and AppSidebar when authenticated', () => {
		const children = createRawSnippet(() => ({
			render: () => '<div data-testid="page-content">Authenticated Dashboard</div>'
		}));

		render(Layout, {
			props: {
				data: {
					user: { id: 'u1', email: 'test@example.com' },
					sidebar_open: true,
					collapsed_watchlist_ids: [],
					watchlist_order: null
				},
				children
			}
		});

		expect(screen.getByTestId('page-content')).toBeInTheDocument();
		expect(screen.getByText('Portfolio dashboard')).toBeInTheDocument();
		expect(screen.getByText('test@example.com')).toBeInTheDocument();

		const wrapper = document.querySelector('[data-slot="sidebar-wrapper"]');
		expect(wrapper).toBeInTheDocument();
		expect(wrapper).toHaveClass('overflow-hidden');
	});

	it('allows the sidebar inset to shrink below its content min-width', () => {
		const children = createRawSnippet(() => ({
			render: () => '<div data-testid="page-content">Authenticated Dashboard</div>'
		}));

		render(Layout, {
			props: {
				data: {
					user: { id: 'u1', email: 'test@example.com' },
					sidebar_open: true,
					collapsed_watchlist_ids: [],
					watchlist_order: null
				},
				children
			}
		});

		const inset = document.querySelector('[data-slot="sidebar-inset"]');
		expect(inset).toBeInTheDocument();
		expect(inset).toHaveClass('min-w-0');
	});

	describe('sidebar keyboard shortcuts', () => {
		// Svelte delegates `keydown` to the document root, so the event must be
		// dispatched from an element inside the rendered tree to reach the handler.
		let capturedWatchlistService: ReturnType<typeof getWatchlistService> | null = null;

		const renderLayout = () => {
			const children = createRawSnippet(() => ({
				render: () => '<div data-testid="page-content">Authenticated Dashboard</div>',
				setup: () => {
					capturedWatchlistService = getWatchlistService();
				}
			}));

			render(Layout, {
				props: {
					data: {
						user: { id: 'u1', email: 'test@example.com' },
						sidebar_open: true,
						collapsed_watchlist_ids: [],
						watchlist_order: null
					},
					children
				}
			});

			return screen.getByTestId('page-content');
		};

		const pressKey = (target: HTMLElement, key: string, modifiers: KeyboardEventInit = {}) =>
			fireEvent.keyDown(target, { key, ...modifiers });

		it('opens global search on "/"', async () => {
			const content = renderLayout();

			await pressKey(content, '/');

			expect(screen.getByPlaceholderText('Search for a company or symbol...')).toBeInTheDocument();
		});

		it('navigates to portfolios on "p", watchlists on "w", and holdings on "h"', async () => {
			const content = renderLayout();

			await pressKey(content, 'p');
			expect(goto).toHaveBeenCalledWith('/portfolios');

			await pressKey(content, 'w');
			expect(goto).toHaveBeenCalledWith('/watchlists');

			await pressKey(content, 'h');
			expect(goto).toHaveBeenCalledWith('/holdings');
		});

		it('navigates to default watchlist tickers by number, with 0 for the tenth', async () => {
			const content = renderLayout();
			capturedWatchlistService!.defaultWatchlistSecurities = Array.from(
				{ length: 11 },
				(_, index) => ({
					id: `sec-${index}`,
					symbol: `S${index}`,
					exchange: 'NASDAQ',
					currency: 'USD',
					name: `Security ${index}`,
					isin: null,
					is_active: true,
					updated_at: '2026-01-01T00:00:00Z',
					added_at: '2026-01-01T00:00:00Z',
					position: index
				})
			);

			await pressKey(content, '1');
			expect(goto).toHaveBeenCalledWith('/security/sec-0');

			await pressKey(content, '0');
			expect(goto).toHaveBeenCalledWith('/security/sec-9');
		});

		it('ignores shortcuts while typing in an input', async () => {
			renderLayout();
			const input = document.createElement('input');
			document.body.appendChild(input);

			await pressKey(input, 'w');
			await pressKey(input, '1');

			expect(goto).not.toHaveBeenCalled();
			input.remove();
		});

		it('ignores shortcuts when a modifier key is held', async () => {
			const content = renderLayout();

			await pressKey(content, 'w', { metaKey: true });
			await pressKey(content, 'h', { ctrlKey: true });

			expect(goto).not.toHaveBeenCalled();
		});
	});

	describe('shortcut-target prefetch', () => {
		let capturedWatchlistService: ReturnType<typeof getWatchlistService> | null = null;

		const securities = (count: number) =>
			Array.from({ length: count }, (_, index) => ({
				id: `sec-${index}`,
				symbol: `S${index}`,
				exchange: 'NASDAQ',
				currency: 'USD',
				name: `Security ${index}`,
				isin: null,
				is_active: true,
				updated_at: '2026-01-01T00:00:00Z',
				added_at: '2026-01-01T00:00:00Z',
				position: index
			}));

		const renderLayout = () => {
			const children = createRawSnippet(() => ({
				render: () => '<div data-testid="page-content">Authenticated Dashboard</div>',
				setup: () => {
					capturedWatchlistService = getWatchlistService();
				}
			}));

			render(Layout, {
				props: {
					data: {
						user: { id: 'u1', email: 'test@example.com' },
						sidebar_open: true,
						collapsed_watchlist_ids: [],
						watchlist_order: null
					},
					children
				}
			});

			return screen.getByTestId('page-content');
		};

		const pressKey = (target: HTMLElement, key: string) => fireEvent.keyDown(target, { key });

		it('prefetches the shortcut routes plus the default watchlist top ten, in order', async () => {
			renderLayout();
			capturedWatchlistService!.defaultWatchlistSecurities = securities(11);

			await waitFor(() => expect(preloadData).toHaveBeenCalledTimes(13));

			expect(vi.mocked(preloadData).mock.calls.map(([url]) => url)).toEqual([
				'/portfolios',
				'/watchlists',
				'/holdings',
				...securities(10).map((security) => `/security/${security.id}`)
			]);
		});

		it('does not prefetch when unauthenticated', async () => {
			const children = createRawSnippet(() => ({
				render: () => '<div data-testid="page-content">Login Page Content</div>'
			}));

			render(Layout, {
				props: {
					data: {
						user: null,
						sidebar_open: true,
						collapsed_watchlist_ids: [],
						watchlist_order: null
					},
					children
				}
			});

			await new Promise((resolve) => setTimeout(resolve, 0));

			expect(marketMocks.getWatchlists).not.toHaveBeenCalled();
			expect(preloadData).not.toHaveBeenCalled();
		});

		it('prefetches each URL at most once, even across repeated shortcut presses', async () => {
			const content = renderLayout();
			capturedWatchlistService!.defaultWatchlistSecurities = [];

			await pressKey(content, 'w');
			await pressKey(content, 'w');

			await waitFor(() => expect(goto).toHaveBeenCalledTimes(2));

			const watchlistPrefetches = vi
				.mocked(preloadData)
				.mock.calls.filter(([url]) => url === '/watchlists');
			expect(watchlistPrefetches).toHaveLength(1);
			expect(goto).toHaveBeenNthCalledWith(1, '/watchlists');
			expect(goto).toHaveBeenNthCalledWith(2, '/watchlists');
		});

		it('prefetches the numeric shortcut target before navigating to it', async () => {
			const content = renderLayout();
			capturedWatchlistService!.defaultWatchlistSecurities = securities(2);

			await waitFor(() => expect(marketMocks.getWatchlists).toHaveBeenCalledTimes(1));
			await pressKey(content, '1');

			expect(goto).toHaveBeenCalledWith('/security/sec-0');
			expect(preloadData).toHaveBeenCalledWith('/security/sec-0');
			expect(vi.mocked(preloadData).mock.invocationCallOrder.at(-1)!).toBeLessThan(
				vi.mocked(goto).mock.invocationCallOrder.at(-1)!
			);
		});

		it('swallows prefetch failures: navigation still works and no error surfaces', async () => {
			vi.mocked(preloadData).mockRejectedValue(new Error('prefetch boom'));
			const content = renderLayout();
			capturedWatchlistService!.defaultWatchlistSecurities = securities(11);

			await pressKey(content, 'w');
			await pressKey(content, 'h');

			// The whole background pass and both shortcut prefetches rejected, yet
			// the shortcuts keep navigating and nothing is shown to the user: the
			// rejected `preloadData` promises never escape `prefetchUrl`.
			await waitFor(() => expect(goto).toHaveBeenCalledWith('/holdings'));
			expect(goto).toHaveBeenNthCalledWith(1, '/watchlists');
			expect(goto).toHaveBeenNthCalledWith(2, '/holdings');
			expect(screen.queryByRole('alert')).not.toBeInTheDocument();
		});
	});

	describe('async watchlists load', () => {
		const renderAuthenticated = () => {
			const children = createRawSnippet(() => ({
				render: () => '<div data-testid="page-content">Authenticated Dashboard</div>'
			}));

			return render(Layout, {
				props: {
					data: {
						user: { id: 'u1', email: 'test@example.com' },
						sidebar_open: true,
						collapsed_watchlist_ids: [],
						watchlist_order: null
					},
					children
				}
			});
		};

		it('redirects to login through the shared seam when the load returns 401', async () => {
			marketMocks.getWatchlists.mockRejectedValueOnce(new ApiError(401, 'Unauthorized'));

			renderAuthenticated();

			await waitFor(() => expect(goto).toHaveBeenCalledWith('/auth/login?clear_session=true'));
			expect(goto).toHaveBeenCalledTimes(1);
		});

		it('does not redirect when the watchlists load succeeds', async () => {
			marketMocks.getWatchlists.mockResolvedValueOnce([]);

			renderAuthenticated();

			await waitFor(() => expect(marketMocks.getWatchlists).toHaveBeenCalledTimes(1));
			expect(goto).not.toHaveBeenCalled();
		});
	});

	describe('collapsed_watchlist_ids preference', () => {
		const loadEvent = (prefs: Record<string, unknown>) => {
			vi.mocked(getUserPreferencesService).mockReturnValue({
				getPreferences: vi.fn().mockResolvedValue(prefs)
			} as unknown as ReturnType<typeof getUserPreferencesService>);
			return {
				locals: { user: { id: 'u1', email: 'test@example.com' } },
				fetch: vi.fn(),
				cookies: { get: vi.fn().mockReturnValue('token') }
			} as unknown as Parameters<typeof load>[0];
		};

		it('defaults collapsed_watchlist_ids to empty array when the preference is absent', async () => {
			const data = await load(loadEvent({ sidebar_open: true }));
			expect(data.collapsed_watchlist_ids).toEqual([]);
		});

		it('reads collapsed_watchlist_ids from preferences', async () => {
			const data = await load(
				loadEvent({ sidebar_open: true, collapsed_watchlist_ids: ['w1', 'w2'] })
			);
			expect(data.collapsed_watchlist_ids).toEqual(['w1', 'w2']);
		});

		it('reads watchlist_order from preferences', async () => {
			const data = await load(
				loadEvent({
					sidebar_open: true,
					watchlist_order: ['w2', 'w1']
				})
			);
			expect(data.watchlist_order).toEqual(['w2', 'w1']);
		});

		it('defaults watchlist_order to null when absent', async () => {
			const data = await load(loadEvent({ sidebar_open: true }));
			expect(data.watchlist_order).toBeNull();
		});
	});
});
