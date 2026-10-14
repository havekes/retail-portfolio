import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import InstitutionalOwnershipModal, {
	formatOwnershipPercent,
	formatInvestorCount,
	formatTotalInvested,
	type InstitutionalOwnershipModalData
} from './institutional-ownership-modal.svelte';
import { ModalState } from '$lib/utils/modal-state.svelte';
import type { InstitutionalOwnershipResponse } from '$lib/api/marketService';

describe('InstitutionalOwnershipModal Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	const mockOwnershipData: InstitutionalOwnershipResponse = {
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
			},
			{
				date: '2024-03-31',
				ownership_percent: 59.85,
				investors_count: 5790,
				total_invested: 1920000000000
			}
		]
	};

	it('renders dialog content and metrics when opened', () => {
		const modalState = new ModalState<InstitutionalOwnershipModalData>();
		modalState.open({
			symbol: 'AAPL',
			data: mockOwnershipData
		});

		render(InstitutionalOwnershipModal, { modalState });

		expect(screen.getByTestId('modal-title')).toHaveTextContent('AAPL Institutional Ownership');
		expect(screen.getByTestId('current-ownership-metric')).toHaveTextContent('60.12%');
		expect(screen.getByTestId('current-investors-metric')).toHaveTextContent('5,834');
		expect(screen.getByTestId('current-total-invested-metric')).toHaveTextContent('$1.98T');

		// Check history table headers
		expect(screen.getByText('Filing Date')).toBeInTheDocument();
		expect(screen.getByText('Ownership %')).toBeInTheDocument();
		expect(screen.getAllByText('Investors').length).toBe(2);
		expect(screen.getAllByText('Total Invested').length).toBe(2);

		// Check history rows
		expect(screen.getByText('Jun 30, 2024')).toBeInTheDocument();
		expect(screen.getByText('Mar 31, 2024')).toBeInTheDocument();
		expect(screen.getByText('59.85%')).toBeInTheDocument();
		expect(screen.getByText('5,790')).toBeInTheDocument();
		expect(screen.getByText('$1.92T')).toBeInTheDocument();
	});

	it('renders empty history message when history is empty', () => {
		const modalState = new ModalState<InstitutionalOwnershipModalData>();
		modalState.open({
			symbol: 'XYZ',
			data: {
				symbol: 'XYZ',
				current_ownership_percent: null,
				investors_count: null,
				total_invested: null,
				history: []
			}
		});

		render(InstitutionalOwnershipModal, { modalState });

		expect(screen.getByTestId('modal-title')).toHaveTextContent('XYZ Institutional Ownership');
		expect(screen.getByTestId('current-ownership-metric')).toHaveTextContent('N/A');
		expect(screen.getByText('No historical ownership filings available.')).toBeInTheDocument();
	});

	it('closes modal when clicking close button', async () => {
		const modalState = new ModalState<InstitutionalOwnershipModalData>();
		modalState.open({
			symbol: 'AAPL',
			data: mockOwnershipData
		});

		render(InstitutionalOwnershipModal, { modalState });

		expect(modalState.isOpen).toBe(true);
		const closeButton = screen.getByTestId('modal-close-button');
		await fireEvent.click(closeButton);
		expect(modalState.isOpen).toBe(false);
	});

	describe('formatters', () => {
		it('formats ownership percentage correctly', () => {
			expect(formatOwnershipPercent(60.123)).toBe('60.12%');
			expect(formatOwnershipPercent(0)).toBe('0.00%');
			expect(formatOwnershipPercent(null)).toBe('N/A');
			expect(formatOwnershipPercent(undefined)).toBe('N/A');
		});

		it('formats investor count correctly', () => {
			expect(formatInvestorCount(5834)).toBe('5,834');
			expect(formatInvestorCount(0)).toBe('0');
			expect(formatInvestorCount(null)).toBe('N/A');
			expect(formatInvestorCount(undefined)).toBe('N/A');
		});

		it('formats total invested currency with compact suffixes', () => {
			expect(formatTotalInvested(1980000000000)).toBe('$1.98T');
			expect(formatTotalInvested(2500000000)).toBe('$2.50B');
			expect(formatTotalInvested(15000000)).toBe('$15.00M');
			expect(formatTotalInvested(500000)).toBe('$500,000');
			expect(formatTotalInvested(null)).toBe('N/A');
			expect(formatTotalInvested(undefined)).toBe('N/A');
		});
	});
});
