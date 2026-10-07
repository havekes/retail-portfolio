import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import { userPreferencesService } from '$lib/api/userPreferencesService';

vi.mock('$lib/api/userPreferencesService', async (importOriginal) => {
	const actual = await importOriginal<typeof import('$lib/api/userPreferencesService')>();
	return {
		...actual,
		userPreferencesService: {
			patchPreferences: vi.fn()
		}
	};
});

describe('Preferences Page (+page.svelte)', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	function renderPage(displayCurrency: string = 'CAD') {
		return render(Page, {
			props: {
				data: {
					user: { id: 'u-1', email: 'user@example.com' },
					sidebar_open: true,
					collapsed_watchlist_ids: [],
					watchlist_order: null,
					expanded_account_ids: [],
					display_currency: displayCurrency
				}
			}
		});
	}

	it('renders the display currency select defaulting to CAD', () => {
		renderPage();

		expect(screen.getByText('Preferences')).toBeInTheDocument();
		const select = screen.getByLabelText('Display currency') as HTMLSelectElement;
		expect(select).toBeInTheDocument();
		expect(select.value).toBe('CAD');
	});

	it('renders the select with the stored value', () => {
		renderPage('USD');

		const select = screen.getByLabelText('Display currency') as HTMLSelectElement;
		expect(select.value).toBe('USD');
	});

	it('calls patchPreferences with the new value on change', async () => {
		vi.mocked(userPreferencesService.patchPreferences).mockResolvedValue({
			display_currency: 'USD'
		});
		renderPage('CAD');

		const select = screen.getByLabelText('Display currency') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: 'USD' } });

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
			display_currency: 'USD'
		});
		await waitFor(() => {
			expect(select.value).toBe('USD');
		});
	});

	it('shows an error and reverts the select when saving fails', async () => {
		vi.mocked(userPreferencesService.patchPreferences).mockRejectedValue(
			new Error('Request failed with status 500')
		);
		renderPage('CAD');

		const select = screen.getByLabelText('Display currency') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: 'EUR' } });

		await waitFor(() => {
			expect(screen.getByText('Request failed with status 500')).toBeInTheDocument();
		});
		expect(select.value).toBe('CAD');
	});
});
