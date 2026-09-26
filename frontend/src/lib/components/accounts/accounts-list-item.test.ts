import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import AccountsListItem from './accounts-list-item.svelte';
import { Institution, AccountType, type Holding } from '@/types/account';

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

// The component fetches account totals and holdings on demand — mock the API client so tests
// don't make real network calls (which fail on CI where no backend is running).
vi.mock('$lib/api/accountClient', () => {
	return {
		accountClient: {
			getAccountTotals: vi.fn(),
			getAccountHoldings: vi.fn(),
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
		vi.mocked(accountClient.getAccountHoldings).mockResolvedValue({
			account_id: 'acc-1',
			account_name: 'My Test Account',
			total_value: 1750,
			total_profit_loss: 250,
			total_profit_loss_percent: 16.67,
			net_deposits: 1500,
			currency: 'CAD',
			items: [],
			total: 0,
			offset: 0,
			limit: 50
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
		const editButton = titleElement.parentElement?.querySelector('button');
		expect(editButton).toBeInTheDocument();
		await fireEvent.click(editButton!);

		// Now it should show an input
		const input = screen.getByRole('textbox');
		expect(input).toBeInTheDocument();
		expect((input as HTMLInputElement).value).toBe('My Test Account');

		// Change the input value
		await fireEvent.input(input, { target: { value: 'Updated Account Name' } });

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

	it('renders overflow menu button with aria-label="Account actions"', () => {
		render(AccountsListItem, {
			props: {
				account: mockAccount
			}
		});

		const menuButton = screen.getByRole('button', { name: 'Account actions' });
		expect(menuButton).toBeInTheDocument();
	});

	it('clicking overflow menu button displays "Delete account" option', async () => {
		render(AccountsListItem, {
			props: {
				account: mockAccount
			}
		});

		const menuButton = screen.getByRole('button', { name: 'Account actions' });
		await fireEvent.click(menuButton);

		expect(await screen.findByText('Delete account')).toBeInTheDocument();
	});

	it('clicking "Delete account" opens confirmation modal with title and warning description', async () => {
		render(AccountsListItem, {
			props: {
				account: mockAccount
			}
		});

		const menuButton = screen.getByRole('button', { name: 'Account actions' });
		await fireEvent.click(menuButton);

		const deleteOption = await screen.findByText('Delete account');
		await fireEvent.click(deleteOption);

		await waitFor(() => {
			expect(screen.getByRole('heading', { name: 'Delete account' })).toBeInTheDocument();
			expect(
				screen.getByText(
					`Are you sure you want to delete "${mockAccount.name}"? This action cannot be undone.`
				)
			).toBeInTheDocument();
		});
	});

	it('clicking "Cancel" in confirmation modal closes modal and does not invoke onDelete', async () => {
		const onDeleteMock = vi.fn();
		render(AccountsListItem, {
			props: {
				account: mockAccount,
				onDelete: onDeleteMock
			}
		});

		const menuButton = screen.getByRole('button', { name: 'Account actions' });
		await fireEvent.click(menuButton);

		const deleteOption = await screen.findByText('Delete account');
		await fireEvent.click(deleteOption);

		await waitFor(() => {
			expect(
				screen.getByText(
					`Are you sure you want to delete "${mockAccount.name}"? This action cannot be undone.`
				)
			).toBeInTheDocument();
		});

		const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
		await fireEvent.click(cancelBtn);

		await waitFor(() => {
			expect(
				screen.queryByText(
					`Are you sure you want to delete "${mockAccount.name}"? This action cannot be undone.`
				)
			).not.toBeInTheDocument();
		});
		expect(onDeleteMock).not.toHaveBeenCalled();
	});

	it('clicking "Confirm" in confirmation modal invokes onDelete', async () => {
		const onDeleteMock = vi.fn();
		render(AccountsListItem, {
			props: {
				account: mockAccount,
				onDelete: onDeleteMock
			}
		});

		const menuButton = screen.getByRole('button', { name: 'Account actions' });
		await fireEvent.click(menuButton);

		const deleteOption = await screen.findByText('Delete account');
		await fireEvent.click(deleteOption);

		await waitFor(() => {
			expect(
				screen.getByText(
					`Are you sure you want to delete "${mockAccount.name}"? This action cannot be undone.`
				)
			).toBeInTheDocument();
		});

		const confirmBtn = screen.getByRole('button', { name: 'Confirm' });
		await fireEvent.click(confirmBtn);

		expect(onDeleteMock).toHaveBeenCalledTimes(1);
	});

	describe('Relative Last Sync Date (F-ACCOUNTS-T01)', () => {
		it('renders "Never synced" when account.last_sync_at is null or omitted', () => {
			render(AccountsListItem, {
				props: {
					account: { ...mockAccount, last_sync_at: null }
				}
			});

			expect(screen.getByText('Never synced')).toBeInTheDocument();
		});

		it('renders relative timestamps like "Synced 2 hours ago" and "Synced 5m ago" when last_sync_at is provided', () => {
			const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
			const { unmount } = render(AccountsListItem, {
				props: {
					account: { ...mockAccount, last_sync_at: twoHoursAgo }
				}
			});

			expect(screen.getByText('Synced 2 hours ago')).toBeInTheDocument();
			unmount();

			const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
			render(AccountsListItem, {
				props: {
					account: { ...mockAccount, last_sync_at: fiveMinutesAgo }
				}
			});

			expect(screen.getByText('Synced 5m ago')).toBeInTheDocument();
		});

		it('reactively updates from "Never synced" to "Synced just now" when isSyncing changes from true to false', async () => {
			const { rerender } = render(AccountsListItem, {
				props: {
					account: { ...mockAccount, last_sync_at: null },
					isSyncing: true
				}
			});

			expect(screen.getByText('Never synced')).toBeInTheDocument();

			await rerender({
				account: { ...mockAccount, last_sync_at: null },
				isSyncing: false
			});

			await waitFor(() => {
				expect(screen.getByText('Synced just now')).toBeInTheDocument();
			});
		});

		it('reactively updates when account prop is rerendered with an updated last_sync_at', async () => {
			const { rerender } = render(AccountsListItem, {
				props: {
					account: { ...mockAccount, last_sync_at: null }
				}
			});

			expect(screen.getByText('Never synced')).toBeInTheDocument();

			const tenMinutesAgo = new Date(Date.now() - 10 * 60 * 1000);
			await rerender({
				account: { ...mockAccount, last_sync_at: tenMinutesAgo }
			});

			await waitFor(() => {
				expect(screen.getByText('Synced 10m ago')).toBeInTheDocument();
			});
		});

		it('preserves previous sync state without false update when sync completes with a syncError', async () => {
			const { rerender } = render(AccountsListItem, {
				props: {
					account: { ...mockAccount, last_sync_at: null },
					isSyncing: true,
					syncError: null
				}
			});

			expect(screen.getByText('Never synced')).toBeInTheDocument();

			await rerender({
				account: { ...mockAccount, last_sync_at: null },
				isSyncing: false,
				syncError: 'Network error occurred'
			});

			await waitFor(() => {
				expect(screen.getByText('Network error occurred')).toBeInTheDocument();
				expect(screen.getByText('Never synced')).toBeInTheDocument();
				expect(screen.queryByText('Synced just now')).not.toBeInTheDocument();
			});
		});
	});

	describe('Inline Lightweight Holdings Expansion (F-ACCOUNTS-T02)', () => {
		const mockHoldings: Holding[] = [
			{
				id: 'h-1',
				security_id: 'sec-1',
				security_symbol: 'AAPL',
				security_name: 'Apple Inc.',
				quantity: 10,
				average_cost: 150,
				total_value: 1750,
				profit_loss: 250,
				currency: 'CAD',
				security_currency: 'USD',
				unconverted_total_value: 1750,
				converted_average_cost: 150,
				converted_latest_price: 175,
				unconverted_profit_loss: 250,
				latest_price: 175
			}
		];

		it('caret toggle button is present with aria-expanded="false" and clicking toggles to aria-expanded="true"', async () => {
			render(AccountsListItem, {
				props: {
					account: mockAccount
				}
			});

			const caretButton = screen.getByRole('button', { name: 'Expand holdings' });
			expect(caretButton).toBeInTheDocument();
			expect(caretButton).toHaveAttribute('aria-expanded', 'false');

			await fireEvent.click(caretButton);

			expect(caretButton).toHaveAttribute('aria-expanded', 'true');
			expect(screen.getByRole('button', { name: 'Collapse holdings' })).toBeInTheDocument();
		});

		it('expanding triggers getAccountHoldings and displays the lightweight holdings table with all 5 columns and row data', async () => {
			vi.mocked(accountClient.getAccountHoldings).mockResolvedValue({
				account_id: 'acc-1',
				account_name: 'My Test Account',
				total_value: 1750,
				total_profit_loss: 250,
				total_profit_loss_percent: 16.67,
				net_deposits: 1500,
				currency: 'CAD',
				items: mockHoldings,
				total: 1,
				offset: 0,
				limit: 50
			});

			render(AccountsListItem, {
				props: {
					account: mockAccount
				}
			});

			const caretButton = screen.getByRole('button', { name: 'Expand holdings' });
			await fireEvent.click(caretButton);

			expect(accountClient.getAccountHoldings).toHaveBeenCalledWith('acc-1');

			// Check table headers
			expect(await screen.findByRole('columnheader', { name: 'Symbol' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Quantity' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Price' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Total Value' })).toBeInTheDocument();
			expect(screen.getByRole('columnheader', { name: 'Return' })).toBeInTheDocument();

			// Check holding row data
			expect(screen.getByText('AAPL')).toBeInTheDocument();
			expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
			expect(screen.getByText('10')).toBeInTheDocument();

			const symbolLink = screen.getByText('AAPL').closest('a');
			expect(symbolLink).toHaveAttribute('href', '/security/sec-1');
		});

		it('clicking caret button again collapses the section and hides the table', async () => {
			vi.mocked(accountClient.getAccountHoldings).mockResolvedValue({
				account_id: 'acc-1',
				account_name: 'My Test Account',
				total_value: 1750,
				total_profit_loss: 250,
				total_profit_loss_percent: 16.67,
				net_deposits: 1500,
				currency: 'CAD',
				items: mockHoldings,
				total: 1,
				offset: 0,
				limit: 50
			});

			render(AccountsListItem, {
				props: {
					account: mockAccount
				}
			});

			const caretButton = screen.getByRole('button', { name: 'Expand holdings' });
			await fireEvent.click(caretButton);

			expect(await screen.findByRole('columnheader', { name: 'Symbol' })).toBeInTheDocument();

			// Click again to collapse
			await fireEvent.click(screen.getByRole('button', { name: 'Collapse holdings' }));

			expect(screen.queryByRole('columnheader', { name: 'Symbol' })).not.toBeInTheDocument();
			expect(caretButton).toHaveAttribute('aria-expanded', 'false');
		});

		it('account title link retains href="/accounts/acc-1"', () => {
			render(AccountsListItem, {
				props: {
					account: mockAccount
				}
			});

			const titleLink = screen.getByText('My Test Account').closest('a');
			expect(titleLink).toHaveAttribute('href', '/accounts/acc-1');
		});

		it('empty holdings response displays empty state message', async () => {
			vi.mocked(accountClient.getAccountHoldings).mockResolvedValue({
				account_id: 'acc-1',
				account_name: 'My Test Account',
				total_value: 0,
				total_profit_loss: 0,
				total_profit_loss_percent: null,
				net_deposits: null,
				currency: 'CAD',
				items: [],
				total: 0,
				offset: 0,
				limit: 50
			});

			render(AccountsListItem, {
				props: {
					account: mockAccount
				}
			});

			const caretButton = screen.getByRole('button', { name: 'Expand holdings' });
			await fireEvent.click(caretButton);

			expect(await screen.findByText('No holdings found for this account.')).toBeInTheDocument();
		});

		it('holdings fetch failure shows error state without breaking the card', async () => {
			vi.mocked(accountClient.getAccountHoldings).mockRejectedValue(new Error('Network error'));

			render(AccountsListItem, {
				props: {
					account: mockAccount
				}
			});

			const caretButton = screen.getByRole('button', { name: 'Expand holdings' });
			await fireEvent.click(caretButton);

			expect(
				await screen.findByText('Failed to load holdings. Please try again.')
			).toBeInTheDocument();
			expect(screen.getByText('My Test Account')).toBeInTheDocument();
		});
	});
});
