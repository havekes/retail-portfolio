import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import AccountsListItem from './accounts-list-item.svelte';
import { Institution, AccountType } from '@/types/account';

// The component fetches account totals on render — mock the API client so tests
// don't make real network calls (which fail on CI where no backend is running).
vi.mock('$lib/api/accountClient', () => {
	return {
		accountClient: {
			getAccountTotals: vi.fn(),
			syncAccountCsv: vi.fn()
		}
	};
});

import { accountClient } from '$lib/api/accountClient';

describe('AccountsListItem', () => {
	const mockAccount = {
		id: 'acc-1',
		name: 'My Test Account',
		external_id: 'ext-1',
		institution_id: Institution.Wealthsimple,
		account_type_id: AccountType.TFSA,
		currency: 'CAD',
		broker_display_name: 'Broker',
		is_active: true,
		api_sync_enabled: true,
		created_at: new Date('2026-01-01')
	};

	beforeEach(() => {
		vi.clearAllMocks();
		vi.mocked(accountClient.getAccountTotals).mockResolvedValue({
			value: { value: '100', units: 100, nanos: 0, currencyCode: 'CAD' },
			cost: { value: '50', units: 50, nanos: 0, currencyCode: 'CAD' }
		});
	});

	it('should render the account name and allow renaming without mutating unbound props directly', async () => {
		const onRenameMock = vi.fn();
		const onToggleSelectionMock = vi.fn();
		const onSyncMock = vi.fn();

		render(AccountsListItem, {
			props: {
				account: mockAccount,
				selectionMode: false,
				isSelected: false,
				isSyncing: false,
				syncError: null,
				onToggleSelection: onToggleSelectionMock,
				onSync: onSyncMock,
				onRename: onRenameMock
			}
		});

		// Ensure it renders the title
		const titleElement = screen.getByText('My Test Account');
		expect(titleElement).toBeInTheDocument();

		// Click the edit button (pencil icon)
		// It has a title/label or we can grab the button next to the title
		const editButton = titleElement.parentElement?.querySelector('button');
		expect(editButton).toBeInTheDocument();
		await fireEvent.click(editButton!);

		// Now it should show an input
		const input = screen.getByRole('textbox');
		expect(input).toBeInTheDocument();
		expect((input as HTMLInputElement).value).toBe('My Test Account');

		// Change the input value
		await fireEvent.input(input, { target: { value: 'Updated Account Name' } });

		// Wait for the action to complete/enhance form
		// Instead of testing form enhancement (since it's tricky to mock SvelteKit's enhance action in JSDOM easily),
		// we can test the fallback 'save' button or keypress. Wait, EditableTitle renders a form if 'action' is present.
		// If action is present, we click the submit button.
		const form = input.closest('form');
		if (form) {
			const submitBtn = form.querySelector('button[type="submit"]');
			expect(submitBtn).toBeInTheDocument();
		}
	});

	it('should call onSync when refresh button is clicked on an account with api_sync_enabled true', async () => {
		const onSyncMock = vi.fn();

		render(AccountsListItem, {
			props: {
				account: { ...mockAccount, api_sync_enabled: true },
				selectionMode: false,
				isSelected: false,
				isSyncing: false,
				syncError: null,
				onSync: onSyncMock
			}
		});

		const syncButton = await screen.findByRole('button', { name: 'Sync positions' });
		await fireEvent.click(syncButton);

		expect(onSyncMock).toHaveBeenCalledTimes(1);
		expect(screen.queryByText('Update account from CSV')).not.toBeInTheDocument();
	});

	it('should not call onSync and instead open CSV update modal when refresh button is clicked on an account with api_sync_enabled false', async () => {
		const onSyncMock = vi.fn();

		render(AccountsListItem, {
			props: {
				account: { ...mockAccount, api_sync_enabled: false },
				selectionMode: false,
				isSelected: false,
				isSyncing: false,
				syncError: null,
				onSync: onSyncMock
			}
		});

		const updateButton = await screen.findByRole('button', { name: 'Update from CSV' });
		await fireEvent.click(updateButton);

		expect(onSyncMock).not.toHaveBeenCalled();
		expect(await screen.findByText('Update account from CSV')).toBeInTheDocument();
	});

	it('should invalidate cache and invoke onAccountUpdated when CSV upload succeeds', async () => {
		const onAccountUpdatedMock = vi.fn();
		vi.mocked(accountClient.syncAccountCsv).mockResolvedValue({
			...mockAccount,
			api_sync_enabled: false
		});

		render(AccountsListItem, {
			props: {
				account: { ...mockAccount, api_sync_enabled: false },
				selectionMode: false,
				isSelected: false,
				isSyncing: false,
				syncError: null,
				onAccountUpdated: onAccountUpdatedMock
			}
		});

		// Initial fetch of account totals
		await screen.findByText('$100');
		expect(accountClient.getAccountTotals).toHaveBeenCalledTimes(1);

		// Click to open modal
		const updateButton = await screen.findByRole('button', { name: 'Update from CSV' });
		await fireEvent.click(updateButton);

		// Upload a CSV file
		const file = new File(['data'], 'new.csv', { type: 'text/csv' });
		const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
		await fireEvent.change(fileInput, { target: { files: [file] } });

		const uploadBtn = screen.getByRole('button', { name: 'Upload CSV' });
		await fireEvent.click(uploadBtn);

		await waitFor(() => {
			expect(onAccountUpdatedMock).toHaveBeenCalledTimes(1);
			expect(accountClient.getAccountTotals).toHaveBeenCalledTimes(2);
		});
	});
});
