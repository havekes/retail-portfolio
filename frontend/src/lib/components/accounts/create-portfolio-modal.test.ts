import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import CreatePortfolioModal from './create-portfolio-modal.svelte';
import { ModalState } from '@/utils/modal-state.svelte';
import { portfolioClient } from '$lib/api/portfolioClient';

// Mock the API client
vi.mock('$lib/api/portfolioClient', () => {
	return {
		portfolioClient: {
			createPortfolio: vi.fn()
		}
	};
});

describe('CreatePortfolioModal', () => {
	let modalState: ModalState<string[]>;
	let mockOnCreated = vi.fn<() => void>();

	beforeEach(() => {
		vi.clearAllMocks();
		modalState = new ModalState<string[]>();
		mockOnCreated = vi.fn<() => void>();
	});

	it('should render the correct prompt and pre-populated default name when open', () => {
		modalState.open(['acc-1', 'acc-2']);

		render(CreatePortfolioModal, {
			props: {
				modalState,
				onCreated: mockOnCreated
			}
		});

		expect(
			screen.getByText('Do you want to create a portfolio from the selected accounts?')
		).toBeInTheDocument();

		const nameInput = screen.getByLabelText('Portfolio Name') as HTMLInputElement;
		expect(nameInput).toBeInTheDocument();
		expect(nameInput.value).toContain('Portfolio -');
	});

	it('should trigger API client and show loading state when submitting', async () => {
		modalState.open(['acc-1', 'acc-2']);
		vi.mocked(portfolioClient.createPortfolio).mockResolvedValue({
			id: 'portfolio-1',
			name: 'Test Portfolio',
			accounts: []
		});

		render(CreatePortfolioModal, {
			props: {
				modalState,
				onCreated: mockOnCreated
			}
		});

		const submitButton = screen.getByRole('button', { name: 'Create portfolio' });
		await fireEvent.click(submitButton);

		expect(portfolioClient.createPortfolio).toHaveBeenCalledWith({
			name: expect.stringContaining('Portfolio -'),
			accounts: ['acc-1', 'acc-2']
		});

		// Verify onCreated is called and modal is closed
		await waitFor(() => {
			expect(mockOnCreated).toHaveBeenCalled();
			expect(modalState.isOpen).toBe(false);
		});
	});

	it('should display error callout when request fails', async () => {
		modalState.open(['acc-1', 'acc-2']);
		vi.mocked(portfolioClient.createPortfolio).mockRejectedValue(new Error('API Error'));

		render(CreatePortfolioModal, {
			props: {
				modalState,
				onCreated: mockOnCreated
			}
		});

		const submitButton = screen.getByRole('button', { name: 'Create portfolio' });
		await fireEvent.click(submitButton);

		// Expect error to be in the document
		await waitFor(() => {
			expect(screen.getByText('API Error')).toBeInTheDocument();
		});

		expect(mockOnCreated).not.toHaveBeenCalled();
		expect(modalState.isOpen).toBe(true);
	});
});
