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

		expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W123456789'], {
			currencies: expect.objectContaining({ W123456789: 'CAD' }),
			netDeposits: {}
		});

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

	it('allows user to change account currency before importing', async () => {
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
			const currencySelects = screen.getAllByTestId('account-currency-select');
			expect(currencySelects.length).toBe(2);
		});

		const currencySelects = screen.getAllByTestId('account-currency-select') as HTMLSelectElement[];
		// Change the first account currency from CAD to USD
		await fireEvent.change(currencySelects[0], { target: { value: 'USD' } });

		const importBtn = screen.getByRole('button', { name: 'Import selected (2)' });
		await fireEvent.click(importBtn);

		expect(accountClient.importAccountsCsv).toHaveBeenCalledWith(
			'1',
			file,
			['W123456789', 'W987654321'],
			{
				currencies: { W123456789: 'USD', W987654321: 'USD' },
				netDeposits: {}
			}
		);
	});

	describe('net deposits', () => {
		const existingAccount: CsvDiscoveredAccount = {
			account_number: 'W123456789',
			account_name: 'Existing TFSA',
			account_type_id: AccountType.TFSA,
			account_type_name: 'TFSA',
			currency: 'CAD',
			positions_count: 5,
			exists: true,
			net_deposits: 1000
		};

		const newAccount: CsvDiscoveredAccount = {
			account_number: 'W987654321',
			account_name: 'New RRSP',
			account_type_id: AccountType.RRSP,
			account_type_name: 'RRSP',
			currency: 'USD',
			positions_count: 2,
			exists: false,
			net_deposits: null
		};

		async function openStep2(accounts: CsvDiscoveredAccount[]): Promise<File> {
			vi.mocked(accountClient.inspectCsv).mockResolvedValue(accounts);
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
				expect(screen.getByRole('button', { name: /Import selected/ })).toBeInTheDocument();
			});

			return file;
		}

		function netDepositInputs(): HTMLInputElement[] {
			return screen.getAllByTestId('account-net-deposits-input') as HTMLInputElement[];
		}

		it('prefills an existing account with "Still correct?" and submits the edited value', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			const file = await openStep2([existingAccount]);

			const inputs = netDepositInputs();
			expect(inputs[0]).toHaveValue('1000');
			expect(screen.getByText('Still correct?')).toBeInTheDocument();

			await fireEvent.input(inputs[0], { target: { value: '1200' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Import selected (1)' }));

			expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W123456789'], {
				currencies: expect.objectContaining({ W123456789: 'CAD' }),
				netDeposits: { W123456789: 1200 }
			});
		});

		it('renders an empty Optional input for a new account and omits the key when left empty', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			const file = await openStep2([newAccount]);

			const inputs = netDepositInputs();
			expect(inputs[0]).toHaveValue('');
			expect(inputs[0]).toHaveAttribute('placeholder', 'Optional');

			await fireEvent.click(screen.getByRole('button', { name: 'Import selected (1)' }));

			expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W987654321'], {
				currencies: expect.objectContaining({ W987654321: 'USD' }),
				netDeposits: {}
			});
		});

		it('submits a typed value for a new account', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			const file = await openStep2([newAccount]);

			await fireEvent.input(netDepositInputs()[0], { target: { value: '500' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Import selected (1)' }));

			expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W987654321'], {
				currencies: expect.objectContaining({ W987654321: 'USD' }),
				netDeposits: { W987654321: 500 }
			});
		});

		it('sends null when a prefilled value is cleared', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			const file = await openStep2([existingAccount]);

			await fireEvent.input(netDepositInputs()[0], { target: { value: '' } });
			await fireEvent.click(screen.getByRole('button', { name: 'Import selected (1)' }));

			expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W123456789'], {
				currencies: expect.objectContaining({ W123456789: 'CAD' }),
				netDeposits: { W123456789: null }
			});
		});

		it('never includes unselected accounts in net deposits', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			const file = await openStep2([existingAccount, { ...newAccount, net_deposits: 500 }]);

			await fireEvent.click(screen.getByRole('checkbox', { name: 'Select account W987654321' }));
			await fireEvent.click(screen.getByRole('button', { name: 'Import selected (1)' }));

			expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W123456789'], {
				currencies: expect.objectContaining({ W123456789: 'CAD' }),
				netDeposits: { W123456789: 1000 }
			});
		});

		it('allows negative net deposits (withdrawals)', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			const file = await openStep2([existingAccount]);

			await fireEvent.input(netDepositInputs()[0], { target: { value: '-500' } });
			const importBtn = screen.getByRole('button', { name: 'Import selected (1)' });
			expect(importBtn).not.toBeDisabled();

			await fireEvent.click(importBtn);

			expect(accountClient.importAccountsCsv).toHaveBeenCalledWith('1', file, ['W123456789'], {
				currencies: expect.objectContaining({ W123456789: 'CAD' }),
				netDeposits: { W123456789: -500 }
			});
		});

		it('blocks submit with an inline error for non-numeric input', async () => {
			vi.mocked(accountClient.importAccountsCsv).mockResolvedValue([]);

			await openStep2([existingAccount]);

			await fireEvent.input(netDepositInputs()[0], { target: { value: 'abc' } });

			expect(screen.getByTestId('account-net-deposits-error')).toBeInTheDocument();
			const importBtn = screen.getByRole('button', { name: 'Import selected (1)' });
			expect(importBtn).toBeDisabled();

			await fireEvent.click(importBtn);
			expect(accountClient.importAccountsCsv).not.toHaveBeenCalled();
		});
	});
});
