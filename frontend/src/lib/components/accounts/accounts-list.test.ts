import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import AccountsList from './accounts-list.svelte';
import { AccountsListState } from './accounts-list.svelte.js';
import { accountClient } from '$lib/api/accountClient';
import { brokerClient } from '$lib/api/brokerClient';
import { toast } from '$lib/components/ui/toast';
import { AccountType, Institution, type Account } from '@/types/account';

vi.mock('$lib/api/accountClient', () => ({
	accountClient: {
		getAccounts: vi.fn(),
		getSyncStatus: vi.fn().mockResolvedValue({ account_ids: [] }),
		syncPositions: vi.fn(),
		deleteAccount: vi.fn(),
		getAccountTotals: vi.fn().mockResolvedValue({
			value: { value: '100', units: 100, nanos: 0, currencyCode: 'CAD' },
			cost: { value: '50', units: 50, nanos: 0, currencyCode: 'CAD' }
		})
	}
}));

vi.mock('$lib/api/brokerClient', () => ({
	brokerClient: {
		getAvailableInstitutions: vi.fn().mockResolvedValue([])
	}
}));

vi.mock('$lib/api/authService', () => ({
	authService: {
		getWsTicket: vi.fn().mockResolvedValue({ ticket: 'mock-ticket' })
	}
}));

vi.mock('$lib/components/ui/toast', () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		info: vi.fn(),
		warning: vi.fn(),
		toasts: []
	}
}));

const mockAccounts: Account[] = [
	{
		id: 'acc-1',
		name: 'My TFSA',
		external_id: 'W123456',
		account_type_id: AccountType.TFSA,
		institution_id: Institution.Wealthsimple,
		currency: 'CAD',
		is_active: true,
		api_sync_enabled: true,
		created_at: new Date('2026-01-01')
	}
];

describe('AccountsList - CSV Import entry point', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		class MockWebSocket {
			onopen: (() => void) | null = null;
			onmessage: ((e: MessageEvent) => void) | null = null;
			onclose: (() => void) | null = null;
			close = vi.fn();
		}
		global.WebSocket = MockWebSocket as unknown as typeof WebSocket;

		vi.mocked(accountClient.getAccounts).mockResolvedValue(mockAccounts);
		vi.mocked(accountClient.getSyncStatus).mockResolvedValue({ account_ids: [] });
		vi.mocked(brokerClient.getAvailableInstitutions).mockResolvedValue([
			{
				id: '1',
				name: 'Wealthsimple',
				logo: null,
				auth_type: 'oauth',
				created_at: '2026-01-01',
				csv_import_enabled: true
			}
		]);
	});

	it('renders "Import CSV" button in the accounts header and clicking it opens the CSV import modal', async () => {
		render(AccountsList, {
			props: {
				accounts: mockAccounts
			}
		});

		const importCsvBtn = screen.getByRole('button', { name: 'Import CSV' });
		expect(importCsvBtn).toBeInTheDocument();

		// Initially modal dialog is not visible
		expect(screen.queryByText('Import accounts from CSV')).not.toBeInTheDocument();

		await fireEvent.click(importCsvBtn);

		// Modal should open
		await waitFor(() => {
			expect(screen.getByText('Import accounts from CSV')).toBeInTheDocument();
		});
	});
});

describe('AccountsListState.deleteAccount', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		class MockWebSocket {
			onopen: (() => void) | null = null;
			onmessage: ((e: MessageEvent) => void) | null = null;
			onclose: (() => void) | null = null;
			close = vi.fn();
		}
		global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
	});

	it('deletes account successfully, updates accounts, selection, sync tracking, and shows success toast', async () => {
		vi.mocked(accountClient.deleteAccount).mockResolvedValue();

		const initialAccounts: Account[] = [
			{
				id: 'acc-1',
				name: 'Account 1',
				external_id: 'ext-1',
				account_type_id: AccountType.TFSA,
				institution_id: Institution.Wealthsimple,
				currency: 'CAD',
				is_active: true,
				api_sync_enabled: true,
				created_at: new Date('2026-01-01')
			},
			{
				id: 'acc-2',
				name: 'Account 2',
				external_id: 'ext-2',
				account_type_id: AccountType.RRSP,
				institution_id: Institution.Questrade,
				currency: 'CAD',
				is_active: true,
				api_sync_enabled: false,
				created_at: new Date('2026-01-01')
			}
		];

		const state = new AccountsListState(initialAccounts);
		state.selectedAccounts = ['acc-1', 'acc-2'];
		state.syncingAccountIds.add('acc-1');
		state.syncErrors['acc-1'] = 'Some error';

		await state.deleteAccount('acc-1');

		expect(accountClient.deleteAccount).toHaveBeenCalledWith('acc-1');
		expect(state.accounts.map((a) => a.id)).toEqual(['acc-2']);
		expect(state.selectedAccounts).toEqual(['acc-2']);
		expect(state.syncingAccountIds.has('acc-1')).toBe(false);
		expect(state.syncErrors['acc-1']).toBeUndefined();
		expect(toast.success).toHaveBeenCalledWith('Account deleted successfully');
	});

	it('shows error toast and retains account in accounts list on API error', async () => {
		vi.mocked(accountClient.deleteAccount).mockRejectedValue(new Error('Network error'));

		const initialAccounts: Account[] = [
			{
				id: 'acc-1',
				name: 'Account 1',
				external_id: 'ext-1',
				account_type_id: AccountType.TFSA,
				institution_id: Institution.Wealthsimple,
				currency: 'CAD',
				is_active: true,
				api_sync_enabled: true,
				created_at: new Date('2026-01-01')
			}
		];

		const state = new AccountsListState(initialAccounts);

		await state.deleteAccount('acc-1');

		expect(accountClient.deleteAccount).toHaveBeenCalledWith('acc-1');
		expect(state.accounts).toHaveLength(1);
		expect(state.accounts[0].id).toBe('acc-1');
		expect(toast.error).toHaveBeenCalledWith('Failed to delete account. Please try again.');
	});
});

describe('AccountsList - Account deletion flow', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		class MockWebSocket {
			onopen: (() => void) | null = null;
			onmessage: ((e: MessageEvent) => void) | null = null;
			onclose: (() => void) | null = null;
			close = vi.fn();
		}
		global.WebSocket = MockWebSocket as unknown as typeof WebSocket;

		vi.mocked(accountClient.getAccounts).mockResolvedValue(mockAccounts);
		vi.mocked(accountClient.getSyncStatus).mockResolvedValue({ account_ids: [] });
		vi.mocked(brokerClient.getAvailableInstitutions).mockResolvedValue([]);
	});

	it('triggers deletion via overflow menu and confirmation modal, calling deleteAccount and removing item from list', async () => {
		vi.mocked(accountClient.deleteAccount).mockResolvedValue();

		render(AccountsList, {
			props: {
				accounts: mockAccounts
			}
		});

		// Wait for the account item to be rendered
		const accountTitle = await screen.findByText('My TFSA');
		expect(accountTitle).toBeInTheDocument();

		// Find and click the overflow menu button
		const actionsBtn = screen.getByRole('button', { name: 'Account actions' });
		await fireEvent.click(actionsBtn);

		// Click "Delete account" option
		const deleteOption = await screen.findByText('Delete account');
		await fireEvent.click(deleteOption);

		// Confirmation modal should appear
		await waitFor(() => {
			expect(screen.getByRole('heading', { name: 'Delete account' })).toBeInTheDocument();
			expect(
				screen.getByText(`Are you sure you want to delete "My TFSA"? This action cannot be undone.`)
			).toBeInTheDocument();
		});

		// Click Confirm button
		const confirmBtn = screen.getByRole('button', { name: 'Confirm' });
		await fireEvent.click(confirmBtn);

		// Verify API was called
		expect(accountClient.deleteAccount).toHaveBeenCalledWith('acc-1');

		// Verify account is removed from the DOM
		await waitFor(() => {
			expect(screen.queryByText('My TFSA')).not.toBeInTheDocument();
		});

		expect(toast.success).toHaveBeenCalledWith('Account deleted successfully');
	});
});
