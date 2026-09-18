import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Layout from './+layout.svelte';
import { load } from './+layout.server';
import { createRawSnippet } from 'svelte';
import { userPreferencesService, getUserPreferencesService } from '$lib/api/userPreferencesService';

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
				data: { user: null, sidebar_open: true, sidebar_watchlists: false },
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
					sidebar_watchlists: false
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
					sidebar_watchlists: false
				},
				children
			}
		});

		const inset = document.querySelector('[data-slot="sidebar-inset"]');
		expect(inset).toBeInTheDocument();
		expect(inset).toHaveClass('min-w-0');
	});

	describe('sidebar_watchlists preference', () => {
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

		it('defaults sidebar_watchlists to false when the preference is absent', async () => {
			const data = await load(loadEvent({ sidebar_open: true }));
			expect(data.sidebar_watchlists).toBe(false);
		});

		it('reads sidebar_watchlists from preferences', async () => {
			const data = await load(loadEvent({ sidebar_open: true, sidebar_watchlists: true }));
			expect(data.sidebar_watchlists).toBe(true);
		});

		it('renders the watchlists header when the preference is on', () => {
			const children = createRawSnippet(() => ({
				render: () => '<div data-testid="page-content">Authenticated Dashboard</div>'
			}));

			render(Layout, {
				props: {
					data: {
						user: { id: 'u1', email: 'test@example.com' },
						sidebar_open: true,
						sidebar_watchlists: true
					},
					children
				}
			});

			// The nav link also renders 'Watchlists'; assert on the sidebar group
			// label to verify the preference turns the group on.
			expect(
				screen.getByText('Watchlists', { selector: '[data-sidebar="group-label"]' })
			).toBeInTheDocument();
		});

		it('persists the toggle through the preferences client', async () => {
			const children = createRawSnippet(() => ({
				render: () => '<div data-testid="page-content">Authenticated Dashboard</div>'
			}));

			render(Layout, {
				props: {
					data: {
						user: { id: 'u1', email: 'test@example.com' },
						sidebar_open: true,
						sidebar_watchlists: false
					},
					children
				}
			});

			await fireEvent.click(screen.getByRole('button', { name: 'Show watchlists' }));

			expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
				sidebar_watchlists: true
			});
		});
	});
});
