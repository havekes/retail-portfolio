import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/svelte';
import FundamentalsGroup from './fundamentals-group.svelte';
import type { SecurityValuationRead } from '$lib/api/valuationClient';
import type { InstitutionalOwnershipResponse } from '$lib/api/marketService';

vi.mock('$lib/api/valuationClient', () => ({
	valuationClient: {
		setValuation: vi.fn(),
		getValuation: vi.fn()
	}
}));

vi.mock('$lib/api/marketService', () => ({
	marketService: {
		getInstitutionalOwnership: vi.fn()
	}
}));

vi.mock('$lib/api/userPreferencesService', () => ({
	userPreferencesService: {
		patchPreferences: vi.fn().mockResolvedValue({})
	}
}));

import { valuationClient } from '$lib/api/valuationClient';
import { marketService } from '$lib/api/marketService';
import { userPreferencesService } from '$lib/api/userPreferencesService';

describe('FundamentalsGroup Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(marketService.getInstitutionalOwnership).mockResolvedValue(null);
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

	it('renders short date of last update when valuation is present', async () => {
		const mockValuation: SecurityValuationRead = {
			id: 1,
			user_id: 'u-1',
			security_id: 'sec-1',
			lower_bound: 100,
			upper_bound: 150,
			created_at: '2026-10-05T12:00:00Z',
			updated_at: '2026-10-05T12:00:00Z'
		};
		vi.mocked(valuationClient.getValuation).mockResolvedValue(mockValuation);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			currency: 'USD',
			expanded: true
		});

		await waitFor(() => {
			expect(screen.getByText('Oct 5, 2026')).toBeInTheDocument();
		});
	});

	it('renders institutional ownership metric when data is present', async () => {
		const mockOwnership: InstitutionalOwnershipResponse = {
			symbol: 'AAPL',
			current_ownership_percent: 60.12,
			investors_count: 5834,
			total_invested: 1980000000000,
			history: [
				{
					date: '2024-06-30',
					ownership_percent: 60.12,
					investors_count: 5834,
					total_invested: 1980000000000
				}
			]
		};
		vi.mocked(marketService.getInstitutionalOwnership).mockResolvedValue(mockOwnership);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			currency: 'USD',
			expanded: true
		});

		await waitFor(() => {
			expect(screen.getByText('Institutional Ownership')).toBeInTheDocument();
			const trigger = screen.getByTestId('ownership-metric-trigger');
			expect(trigger).toHaveTextContent('60.12%');
			expect(trigger).not.toBeDisabled();
		});
	});

	it('opens institutional ownership modal when trigger is clicked', async () => {
		const mockOwnership: InstitutionalOwnershipResponse = {
			symbol: 'AAPL',
			current_ownership_percent: 60.12,
			investors_count: 5834,
			total_invested: 1980000000000,
			history: [
				{
					date: '2024-06-30',
					ownership_percent: 60.12,
					investors_count: 5834,
					total_invested: 1980000000000
				}
			]
		};
		vi.mocked(marketService.getInstitutionalOwnership).mockResolvedValue(mockOwnership);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			symbol: 'AAPL',
			currency: 'USD',
			expanded: true
		});

		await waitFor(() => {
			expect(screen.getByTestId('ownership-metric-trigger')).toHaveTextContent('60.12%');
		});

		const trigger = screen.getByTestId('ownership-metric-trigger');
		await fireEvent.click(trigger);

		await waitFor(() => {
			expect(screen.getByTestId('modal-title')).toHaveTextContent('AAPL Institutional Ownership');
		});
	});

	it('renders disabled N/A state when institutional ownership data is null or unavailable', async () => {
		vi.mocked(marketService.getInstitutionalOwnership).mockResolvedValue(null);

		render(FundamentalsGroup, {
			securityId: 'sec-1',
			currency: 'USD',
			expanded: true
		});

		await waitFor(() => {
			expect(screen.getByText('Institutional Ownership')).toBeInTheDocument();
			const trigger = screen.getByTestId('ownership-metric-trigger');
			expect(trigger).toHaveTextContent('N/A');
			expect(trigger).toBeDisabled();
		});
	});
});
