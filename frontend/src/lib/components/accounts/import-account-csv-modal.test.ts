import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import ImportAccountCsvModal from './import-account-csv-modal.svelte';
import { ModalState } from '@/utils/modal-state.svelte';
import { accountClient } from '$lib/api/accountClient';
import { brokerClient } from '$lib/api/brokerClient';
import { AccountType, type CsvDiscoveredAccount } from '@/types/account';
import type { BackendInstitution } from '@/types/broker/broker';

vi.mock('$lib/api/accountClient', () => ({
	accountClient: {
		inspectCsv: vi.fn(),
		importAccountsCsv: vi.fn()
	}
}));

vi.mock('$lib/api/brokerClient', () => ({
	brokerClient: {
		getAvailableInstitutions: vi.fn()
	}
}));

describe('ImportAccountCsvModal', () => {
	let modalState: ModalState<void>;
	let mockOnSuccess = vi.fn();

	const mockInstitutions: BackendInstitution[] = [
		{
			id: '1',
			name: 'Wealthsimple',
			logo: null,
			auth_type: 'oauth',
			created_at: '2026-01-01',
			csv_import_enabled: true,
			csv_format: 'wealthsimple'
		},
		{
			id: '2',
			name: 'Questrade',
			logo: null,
			auth_type: 'oauth',
			created_at: '2026-01-01',
			csv_import_enabled: false
		},
		{
			id: '3',
			name: 'Interactive Brokers',
			logo: null,
			auth_type: 'oauth',
			created_at: '2026-01-01',
			csv_import_enabled: true,
			csv_format: 'ibkr'
		}
	];

	const mockDiscoveredAccounts: CsvDiscoveredAccount[] = [
		{
			account_number: 'W123456789',
			account_name: 'My TFSA',
			account_type_id: AccountType.TFSA,
			account_type_name: 'TFSA',
			currency: 'CAD',
			positions_count: 5
		},
		{
			account_number: 'W987654321',
			account_name: 'My RRSP',
			account_type_id: AccountType.RRSP,
			account_type_name: 'RRSP',
			currency: 'USD',
			positions_count: 2
		}
	];

	beforeEach(() => {
		vi.clearAllMocks();
		modalState = new ModalState<void>();
		mockOnSuccess = vi.fn();
		vi.mocked(brokerClient.getAvailableInstitutions).mockResolvedValue(mockInstitutions);
	});

	it('filters broker selection: only brokers with csv_import_enabled === true appear', async () => {
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
			const options = Array.from(select.options).map((o) => o.text);
			expect(options).toContain('Wealthsimple');
			expect(options).toContain('Interactive Brokers');
			expect(options).not.toContain('Questrade');
		});
	});

	it('auto-selects the broker if exactly one institution is csv_import_enabled', async () => {
		vi.mocked(brokerClient.getAvailableInstitutions).mockResolvedValue([
			{
				id: '1',
				name: 'Wealthsimple',
				logo: null,
				auth_type: 'oauth',
				created_at: '2026-01-01',
				csv_import_enabled: true
			},
			{
				id: '2',
				name: 'Questrade',
				logo: null,
				auth_type: 'oauth',
				created_at: '2026-01-01',
				csv_import_enabled: false
			}
		]);

		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select.value).toBe('1');
		});
	});

	it('rejects non-CSV files and displays client-side validation error', async () => {
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		const file = new File(['dummy'], 'statement.pdf', { type: 'application/pdf' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;

		await fireEvent.change(input, { target: { files: [file] } });

		expect(screen.getByText('Please select a valid CSV file (.csv).')).toBeInTheDocument();
		const previewBtn = screen.getByRole('button', { name: 'Preview accounts' });
		expect(previewBtn).toBeDisabled();
	});

	it('rejects files larger than 10MB and displays client-side validation error', async () => {
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		const largeFile = new File(['dummy'], 'huge.csv', { type: 'text/csv' });
		Object.defineProperty(largeFile, 'size', { value: 11 * 1024 * 1024 });

		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [largeFile] } });

		expect(screen.getByText('File size exceeds 10MB limit.')).toBeInTheDocument();
		const previewBtn = screen.getByRole('button', { name: 'Preview accounts' });
		expect(previewBtn).toBeDisabled();
	});

	it('inspects CSV and renders discovered accounts preview table with checkboxes', async () => {
		vi.mocked(accountClient.inspectCsv).mockResolvedValue(mockDiscoveredAccounts);
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'wealthsimple.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		const previewBtn = screen.getByRole('button', { name: 'Preview accounts' });
		expect(previewBtn).not.toBeDisabled();

		await fireEvent.click(previewBtn);

		expect(accountClient.inspectCsv).toHaveBeenCalledWith('1', file);

		await waitFor(() => {
			expect(screen.getByText('Select accounts to import')).toBeInTheDocument();
			expect(screen.getByText('W123456789')).toBeInTheDocument();
			expect(screen.getByText('My TFSA')).toBeInTheDocument();
			expect(screen.getByText('TFSA')).toBeInTheDocument();
			expect(screen.getByText('5')).toBeInTheDocument();

			expect(screen.getByText('W987654321')).toBeInTheDocument();
			expect(screen.getByText('My RRSP')).toBeInTheDocument();
			expect(screen.getByText('RRSP')).toBeInTheDocument();
			expect(screen.getByText('2')).toBeInTheDocument();
		});

		const importBtn = screen.getByRole('button', { name: 'Import selected (2)' });
		expect(importBtn).not.toBeDisabled();
	});

	it('toggles selection with individual row checkboxes and select-all header checkbox', async () => {
		vi.mocked(accountClient.inspectCsv).mockResolvedValue(mockDiscoveredAccounts);
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		const previewBtn = screen.getByRole('button', { name: 'Preview accounts' });
		await fireEvent.click(previewBtn);

		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Import selected (2)' })).toBeInTheDocument();
		});

		// Deselect one account
		const rowCheckbox = screen.getByRole('checkbox', { name: 'Select account W123456789' });
		await fireEvent.click(rowCheckbox);

		expect(screen.getByRole('button', { name: 'Import selected (1)' })).toBeInTheDocument();

		// Deselect second account -> 0 selected -> button disabled
		const rowCheckbox2 = screen.getByRole('checkbox', { name: 'Select account W987654321' });
		await fireEvent.click(rowCheckbox2);

		const disabledImportBtn = screen.getByRole('button', { name: 'Import selected (0)' });
		expect(disabledImportBtn).toBeDisabled();

		// Toggle select-all header checkbox -> all selected again
		const selectAllCheckbox = screen.getByRole('checkbox', { name: 'Select all accounts' });
		await fireEvent.click(selectAllCheckbox);

		expect(screen.getByRole('button', { name: 'Import selected (2)' })).not.toBeDisabled();
	});

	it('submits import: calls accountClient.importAccountsCsv, closes modal, and invokes onSuccess', async () => {
		vi.mocked(accountClient.inspectCsv).mockResolvedValue(mockDiscoveredAccounts);
		vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Preview accounts' }));

		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Import selected (2)' })).toBeInTheDocument();
		});

		// Uncheck account 2
		const rowCheckbox2 = screen.getByRole('checkbox', { name: 'Select account W987654321' });
		await fireEvent.click(rowCheckbox2);

		const importBtn = screen.getByRole('button', { name: 'Import selected (1)' });
		await fireEvent.click(importBtn);

		expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W123456789']);

		await waitFor(() => {
			expect(mockOnSuccess).toHaveBeenCalledTimes(1);
			expect(modalState.isOpen).toBe(false);
		});
	});

	it('supports back button from Step 2 to return to Step 1 without losing file/broker state', async () => {
		vi.mocked(accountClient.inspectCsv).mockResolvedValue(mockDiscoveredAccounts);
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Preview accounts' }));

		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Back' })).toBeInTheDocument();
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Back' }));

		expect(screen.getByText('Import accounts from CSV')).toBeInTheDocument();
		expect(screen.getByTestId('selected-file-name')).toHaveTextContent('test.csv');
		const selectAfterBack = document.getElementById('broker-select') as HTMLSelectElement;
		expect(selectAfterBack.value).toBe('1');
	});

	it('displays API error message when inspectCsv fails', async () => {
		vi.mocked(accountClient.inspectCsv).mockRejectedValue(new Error('Invalid CSV headers'));
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'bad.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Preview accounts' }));

		await waitFor(() => {
			expect(screen.getByText('Invalid CSV headers')).toBeInTheDocument();
		});

		expect(screen.queryByText('Select accounts to import')).not.toBeInTheDocument();
	});

	it('displays API error message when importAccountsCsv fails', async () => {
		vi.mocked(accountClient.inspectCsv).mockResolvedValue(mockDiscoveredAccounts);
		vi.mocked(accountClient.importAccountsCsv).mockRejectedValue(
			new Error('Account already exists')
		);
		modalState.open();

		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Preview accounts' }));

		await waitFor(() => {
			expect(screen.getByRole('button', { name: 'Import selected (2)' })).toBeInTheDocument();
		});

		await fireEvent.click(screen.getByRole('button', { name: 'Import selected (2)' }));

		await waitFor(() => {
			expect(screen.getByText('Account already exists')).toBeInTheDocument();
		});

		expect(modalState.isOpen).toBe(true);
		expect(mockOnSuccess).not.toHaveBeenCalled();
	});

	it('supports bind:open prop without modalState', async () => {
		render(ImportAccountCsvModal, {
			props: {
				open: true,
				onSuccess: () => mockOnSuccess()
			}
		});

		expect(screen.getByText('Import accounts from CSV')).toBeInTheDocument();
		await waitFor(() => {
			expect(brokerClient.getAvailableInstitutions).toHaveBeenCalled();
		});
	});

	it('displays action badges indicating if accounts are existing (update) or new (create)', async () => {
		const mixedDiscoveredAccounts: CsvDiscoveredAccount[] = [
			{
				account_number: 'W123456789',
				account_name: 'Existing TFSA',
				account_type_id: AccountType.TFSA,
				account_type_name: 'TFSA',
				currency: 'CAD',
				positions_count: 3,
				exists: true
			},
			{
				account_number: 'W987654321',
				account_name: 'New RRSP',
				account_type_id: AccountType.RRSP,
				account_type_name: 'RRSP',
				currency: 'USD',
				positions_count: 1,
				exists: false
			}
		];
		vi.mocked(accountClient.inspectCsv).mockResolvedValue(mixedDiscoveredAccounts);

		modalState.open();
		render(ImportAccountCsvModal, {
			props: {
				modalState,
				onSuccess: () => mockOnSuccess()
			}
		});

		await waitFor(() => {
			const select = document.getElementById('broker-select') as HTMLSelectElement;
			expect(select).toBeInTheDocument();
		});

		const select = document.getElementById('broker-select') as HTMLSelectElement;
		await fireEvent.change(select, { target: { value: '1' } });

		const file = new File(['content'], 'test.csv', { type: 'text/csv' });
		const input = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(input, { target: { files: [file] } });

		await fireEvent.click(screen.getByRole('button', { name: 'Preview accounts' }));

		await waitFor(() => {
			expect(screen.getByText('Update holdings')).toBeInTheDocument();
			expect(screen.getByText('Create account')).toBeInTheDocument();
		});
	});
});
