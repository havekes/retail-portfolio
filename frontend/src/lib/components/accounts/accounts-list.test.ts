import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import AccountsList from './accounts-list.svelte';
import { accountClient } from '$lib/api/accountClient';
import { brokerClient } from '$lib/api/brokerClient';
import { AccountType, Institution, type Account } from '@/types/account';

vi.mock('$lib/api/accountClient', () => ({
	accountClient: {
		getAccounts: vi.fn(),
		getSyncStatus: vi.fn().mockResolvedValue({ account_ids: [] }),
		syncPositions: vi.fn()
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

describe('AccountsList - CSV Import entry point', () => {
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
