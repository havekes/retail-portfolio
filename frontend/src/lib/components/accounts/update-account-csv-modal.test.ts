import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import UpdateAccountCsvModal from './update-account-csv-modal.svelte';
import { ModalState } from '@/utils/modal-state.svelte';
import { accountClient } from '$lib/api/accountClient';
import { Institution, AccountType, type Account } from '@/types/account';

vi.mock('$lib/api/accountClient', () => {
	return {
		accountClient: {
			syncAccountCsv: vi.fn()
		}
	};
});

describe('UpdateAccountCsvModal', () => {
	let modalState: ModalState<void>;
	let mockOnSuccess = vi.fn<() => void>();

	const mockAccount: Account = {
		id: 'acc-csv-1',
		name: 'CSV Trading Account',
		external_id: 'ext-csv-1',
		account_type_id: AccountType.NonRegistered,
		institution_id: Institution.Wealthsimple,
		currency: 'CAD',
		is_active: true,
		api_sync_enabled: false,
		created_at: new Date('2026-01-01')
	};

	beforeEach(() => {
		vi.clearAllMocks();
		modalState = new ModalState<void>();
		mockOnSuccess = vi.fn();
	});

	it('renders modal header, description, dropzone, and buttons when open', () => {
		modalState.open();

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		expect(screen.getByText('Update account from CSV')).toBeInTheDocument();
		expect(
			screen.getByText(/Upload a CSV file to update positions for CSV Trading Account/i)
		).toBeInTheDocument();
		expect(screen.getByText('Click to select or drag CSV file here')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		expect(uploadBtn).toBeInTheDocument();
		expect(uploadBtn).toBeDisabled();
	});

	it('selects a CSV file via file input and displays file name and formatted size', async () => {
		modalState.open();

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const file = new File(['col1,col2\nval1,val2'], 'positions.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		expect(input).toBeInTheDocument();

		await fireEvent.change(input, { target: { files: [file] } });

		expect(screen.getByTestId('selected-file-name')).toHaveTextContent('positions.csv');
		expect(screen.getByTestId('selected-file-size')).toBeInTheDocument();

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		expect(uploadBtn).not.toBeDisabled();
	});

	it('selects a CSV file via drag and drop', async () => {
		modalState.open();

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const dropzone = screen.getByRole('region', { name: 'CSV file dropzone' });
		expect(dropzone).toBeInTheDocument();

		await fireEvent.dragOver(dropzone);
		expect(dropzone.className).toContain('border-primary');

		await fireEvent.dragLeave(dropzone);
		expect(dropzone.className).not.toContain('border-primary bg-primary/5');

		const file = new File(['a,b\n1,2'], 'dropped_file.csv', { type: 'text/csv' });
		await fireEvent.drop(dropzone, {
			dataTransfer: { files: [file] }
		});

		expect(screen.getByTestId('selected-file-name')).toHaveTextContent('dropped_file.csv');
		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		expect(uploadBtn).not.toBeDisabled();
	});

	it('rejects non-CSV files with client-side validation error and keeps upload disabled', async () => {
		modalState.open();

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const file = new File(['sample'], 'statement.pdf', { type: 'application/pdf' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;

		await fireEvent.change(input, { target: { files: [file] } });

		expect(screen.getByText('Please select a valid CSV file (.csv).')).toBeInTheDocument();
		expect(screen.queryByTestId('selected-file-name')).not.toBeInTheDocument();

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		expect(uploadBtn).toBeDisabled();
	});

	it('rejects files exceeding 10MB limit with client-side validation error', async () => {
		modalState.open();

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const largeFile = new File(['x'], 'huge.csv', { type: 'text/csv' });
		Object.defineProperty(largeFile, 'size', { value: 11 * 1024 * 1024 });

		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [largeFile] } });

		expect(screen.getByText('File size exceeds 10MB limit.')).toBeInTheDocument();
		expect(screen.queryByTestId('selected-file-name')).not.toBeInTheDocument();

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		expect(uploadBtn).toBeDisabled();
	});

	it('handles successful upload: calls accountClient.syncAccountCsv, closes modal, and invokes onSuccess', async () => {
		modalState.open();
		vi.mocked(accountClient.syncAccountCsv).mockResolvedValue(mockAccount);

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const file = new File(['symbol,shares\nAAPL,10'], 'portfolio.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		await fireEvent.click(uploadBtn);

		expect(accountClient.syncAccountCsv).toHaveBeenCalledWith('acc-csv-1', file);

		await waitFor(() => {
			expect(mockOnSuccess).toHaveBeenCalledTimes(1);
			expect(modalState.isOpen).toBe(false);
		});
	});

	it('displays API error message in alert and keeps modal open when sync fails', async () => {
		modalState.open();
		vi.mocked(accountClient.syncAccountCsv).mockRejectedValue(new Error('Account number mismatch'));

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const file = new File(['symbol,shares\nAAPL,10'], 'portfolio.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		await fireEvent.click(uploadBtn);

		await waitFor(() => {
			expect(screen.getByText('Account number mismatch')).toBeInTheDocument();
		});

		expect(mockOnSuccess).not.toHaveBeenCalled();
		expect(modalState.isOpen).toBe(true);
	});

	it('closes modal when Cancel button is clicked', async () => {
		modalState.open();

		render(UpdateAccountCsvModal, {
			props: {
				account: mockAccount,
				modalState,
				onSuccess: mockOnSuccess
			}
		});

		const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
		await fireEvent.click(cancelBtn);

		expect(modalState.isOpen).toBe(false);
	});
});
