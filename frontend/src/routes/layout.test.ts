import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Layout from './+layout.svelte';
import { createRawSnippet } from 'svelte';

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
				data: { user: null, sidebar_open: true },
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
					sidebar_open: true
				},
				children
			}
		});

		expect(screen.getByTestId('page-content')).toBeInTheDocument();
		expect(screen.getByText('Portfolio dashboard')).toBeInTheDocument();
		expect(screen.getByText('test@example.com')).toBeInTheDocument();
	});
});
