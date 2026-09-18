import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Layout from './+layout.svelte';
import { load } from './+layout.server';
import { createRawSnippet } from 'svelte';
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
				data: { user: null, sidebar_open: true, collapsed_watchlist_ids: [] },
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
					collapsed_watchlist_ids: []
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
					collapsed_watchlist_ids: []
				},
				children
			}
		});

		const inset = document.querySelector('[data-slot="sidebar-inset"]');
		expect(inset).toBeInTheDocument();
		expect(inset).toHaveClass('min-w-0');
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
	});
});
