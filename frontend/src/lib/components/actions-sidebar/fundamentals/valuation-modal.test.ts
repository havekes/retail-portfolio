import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import ValuationModal from './valuation-modal.svelte';
import { ModalState } from '$lib/utils/modal-state.svelte';
import type { SecurityValuationRead } from '$lib/api/valuationClient';

vi.mock('$lib/api/valuationClient', () => ({
	valuationClient: {
		setValuation: vi.fn(),
		getValuation: vi.fn()
	}
}));

import { valuationClient } from '$lib/api/valuationClient';

describe('ValuationModal Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders dialog content when opened', async () => {
		const modalState = new ModalState<{
			securityId: string;
			valuation?: SecurityValuationRead | null;
		}>();
		modalState.open({
			securityId: 'sec-1',
			valuation: {
				id: 1,
				user_id: 'u-1',
				security_id: 'sec-1',
				lower_bound: 100,
				upper_bound: 150,
				created_at: '',
				updated_at: ''
			}
		});

		render(ValuationModal, { modalState });

		expect(screen.getByText('Set Valuation Range')).toBeInTheDocument();
		expect(screen.getByLabelText('Lower Bound')).toHaveValue(100);
		expect(screen.getByLabelText('Upper Bound')).toHaveValue(150);
	});

	it('validates lower bound greater than upper bound', async () => {
		const modalState = new ModalState<{
			securityId: string;
			valuation?: SecurityValuationRead | null;
		}>();
		modalState.open({ securityId: 'sec-1' });

		render(ValuationModal, { modalState });

		const lowerInput = screen.getByLabelText('Lower Bound');
		const upperInput = screen.getByLabelText('Upper Bound');
		const saveButton = screen.getByRole('button', { name: /save valuation/i });

		await fireEvent.input(lowerInput, { target: { value: '200' } });
		await fireEvent.input(upperInput, { target: { value: '100' } });
		await fireEvent.click(saveButton);

		expect(screen.getByText('Lower bound cannot be greater than upper bound')).toBeInTheDocument();
		expect(valuationClient.setValuation).not.toHaveBeenCalled();
	});

	it('submits valid valuation successfully', async () => {
		const modalState = new ModalState<{
			securityId: string;
			valuation?: SecurityValuationRead | null;
		}>();
		modalState.open({ securityId: 'sec-1' });

		const mockSaved: SecurityValuationRead = {
			id: 1,
			user_id: 'u-1',
			security_id: 'sec-1',
			lower_bound: 120,
			upper_bound: 160,
			created_at: '',
			updated_at: ''
		};
		vi.mocked(valuationClient.setValuation).mockResolvedValue(mockSaved);

		const onSaved = vi.fn();
		render(ValuationModal, { modalState, onSaved });

		const lowerInput = screen.getByLabelText('Lower Bound');
		const upperInput = screen.getByLabelText('Upper Bound');
		const saveButton = screen.getByRole('button', { name: /save valuation/i });

		await fireEvent.input(lowerInput, { target: { value: '120' } });
		await fireEvent.input(upperInput, { target: { value: '160' } });
		await fireEvent.click(saveButton);

		await waitFor(() => {
			expect(valuationClient.setValuation).toHaveBeenCalledWith('sec-1', {
				lower_bound: 120,
				upper_bound: 160
			});
			expect(onSaved).toHaveBeenCalledWith(mockSaved);
			expect(modalState.isOpen).toBe(false);
		});
	});

	it('configures step="0.01" and rounds pre-filled bounds to 2 decimals', async () => {
		const modalState = new ModalState<{
			securityId: string;
			valuation?: SecurityValuationRead | null;
		}>();
		modalState.open({
			securityId: 'sec-1',
			valuation: {
				id: 1,
				user_id: 'u-1',
				security_id: 'sec-1',
				lower_bound: 100.456,
				upper_bound: 150.789,
				created_at: '',
				updated_at: ''
			}
		});

		render(ValuationModal, { modalState });

		const lowerInput = screen.getByLabelText('Lower Bound');
		const upperInput = screen.getByLabelText('Upper Bound');

		expect(lowerInput).toHaveAttribute('step', '0.01');
		expect(upperInput).toHaveAttribute('step', '0.01');
		expect(lowerInput).toHaveValue(100.46);
		expect(upperInput).toHaveValue(150.79);
	});

	it('rounds user input to 2 decimal places on save', async () => {
		const modalState = new ModalState<{
			securityId: string;
			valuation?: SecurityValuationRead | null;
		}>();
		modalState.open({ securityId: 'sec-1' });

		const mockSaved: SecurityValuationRead = {
			id: 1,
			user_id: 'u-1',
			security_id: 'sec-1',
			lower_bound: 120.34,
			upper_bound: 160.77,
			created_at: '',
			updated_at: ''
		};
		vi.mocked(valuationClient.setValuation).mockResolvedValue(mockSaved);

		render(ValuationModal, { modalState });

		const lowerInput = screen.getByLabelText('Lower Bound');
		const upperInput = screen.getByLabelText('Upper Bound');
		const saveButton = screen.getByRole('button', { name: /save valuation/i });

		await fireEvent.input(lowerInput, { target: { value: '120.339' } });
		await fireEvent.input(upperInput, { target: { value: '160.771' } });
		await fireEvent.click(saveButton);

		await waitFor(() => {
			expect(valuationClient.setValuation).toHaveBeenCalledWith('sec-1', {
				lower_bound: 120.34,
				upper_bound: 160.77
			});
		});
	});
});
