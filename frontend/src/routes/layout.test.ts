import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Layout from './+layout.svelte';
import { load } from './+layout.server';
import { createRawSnippet } from 'svelte';
import { goto } from '$app/navigation';
import { getWatchlistService } from '$lib/components/watchlist/watchlistService.svelte';
import { getUserPreferencesService } from '$lib/api/userPreferencesService';

vi.mock('mode-watcher', () => ({
	ModeWatcher: () => null
}));

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
		getWatchlistSecurities: vi.fn().mockResolvedValue({ items: [] })
	})
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
					watchlist_order: null,
					watchlist_sort: null
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
					watchlist_order: null,
					watchlist_sort: null
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
					watchlist_order: null,
					watchlist_sort: null
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
						watchlist_order: null,
						watchlist_sort: null
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

		it('navigates to watchlists on "w" and holdings on "h"', async () => {
			const content = renderLayout();

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
					updated_at: '2026-01-01T00:00:00Z'
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

		it('reads watchlist_order and watchlist_sort from preferences', async () => {
			const data = await load(
				loadEvent({
					sidebar_open: true,
					watchlist_order: ['w2', 'w1'],
					watchlist_sort: { w1: 'name_asc' }
				})
			);
			expect(data.watchlist_order).toEqual(['w2', 'w1']);
			expect(data.watchlist_sort).toEqual({ w1: 'name_asc' });
		});

		it('defaults watchlist_order and watchlist_sort to null when absent', async () => {
			const data = await load(loadEvent({ sidebar_open: true }));
			expect(data.watchlist_order).toBeNull();
			expect(data.watchlist_sort).toBeNull();
		});
	});
});
