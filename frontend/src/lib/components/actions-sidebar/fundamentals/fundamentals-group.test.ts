import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';
import FundamentalsGroup from './fundamentals-group.svelte';
import type { SecurityValuationRead } from '$lib/api/valuationClient';

vi.mock('$lib/api/valuationClient', () => ({
	valuationClient: {
		setValuation: vi.fn(),
		getValuation: vi.fn()
	}
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		patchPreferences: vi.fn().mockResolvedValue({})
	}
}));

import { valuationClient } from '$lib/api/valuationClient';
import { userPreferencesService } from '$lib/api/userPreferencesService';
import { fireEvent } from '@testing-library/svelte';

describe('FundamentalsGroup Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders empty state when no valuation exists', async () => {
		vi.mocked(valuationClient.getValuation).mockResolvedValue(null);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			currency: 'USD',
			expanded: true
		});

		await waitFor(() => {
			expect(screen.getByText('Fair value range not set.')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: /set valuation range/i })).toBeInTheDocument();
		});
	});

	it('renders valuation range when valuation exists and checkbox is positioned next to display', async () => {
		const mockValuation: SecurityValuationRead = {
			id: 1,
			user_id: 'u-1',
			security_id: 'sec-1',
			lower_bound: 100,
			upper_bound: 150,
			created_at: '',
			updated_at: ''
		};
		vi.mocked(valuationClient.getValuation).mockResolvedValue(mockValuation);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			currency: 'USD',
			expanded: true
		});

		await waitFor(() => {
			expect(screen.getByText('Fair Value Range')).toBeInTheDocument();
			const rangeEl = screen.getByText('$100.00 – $150.00');
			expect(rangeEl).toBeInTheDocument();
			const checkbox = screen.getByLabelText('Show on chart');
			expect(checkbox).toBeInTheDocument();
			// Checkbox should be a sibling in the same flex container next to rangeEl
			expect(rangeEl.parentElement).toContainElement(checkbox);
			// Default showOverlay is true
			expect(checkbox).toBeChecked();
		});
	});

	it('persists show_valuation_band when overlay toggle is clicked', async () => {
		const mockValuation: SecurityValuationRead = {
			id: 1,
			user_id: 'u-1',
			security_id: 'sec-1',
			lower_bound: 100,
			upper_bound: 150,
			created_at: '',
			updated_at: ''
		};
		vi.mocked(valuationClient.getValuation).mockResolvedValue(mockValuation);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			currency: 'USD',
			expanded: true,
			showOverlay: true
		});

		await waitFor(() => {
			expect(screen.getByLabelText('Show on chart')).toBeInTheDocument();
		});

		const checkbox = screen.getByLabelText('Show on chart');
		await fireEvent.click(checkbox);

		expect(userPreferencesService.patchPreferences).toHaveBeenCalledWith({
			show_valuation_band: false
		});
	});
});
