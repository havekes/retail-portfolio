import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import BrokersList from './brokers-list.svelte';
import { brokerClient } from '$lib/api/brokerClient';
import { accountClient } from '$lib/api/accountClient';
import { Institution } from '@/types/account';
import type { BrokerUser } from '@/types/broker/broker';

vi.mock('$lib/api/brokerClient', () => ({
	brokerClient: {
		getAvailableInstitutions: vi.fn().mockResolvedValue([]),
		getBrokerUsers: vi.fn().mockResolvedValue([]),
		getBrokerUserAccounts: vi.fn().mockResolvedValue([])
	},
	getBrokerClient: () => ({
		getAvailableInstitutions: vi.fn().mockResolvedValue([]),
		getBrokerUsers: vi.fn().mockResolvedValue([]),
		getBrokerUserAccounts: vi.fn().mockResolvedValue([])
	})
}));

vi.mock('$lib/api/accountClient', () => ({
	accountClient: {
		inspectCsv: vi.fn(),
		importAccountsCsv: vi.fn(),
		getAccounts: vi.fn().mockResolvedValue([])
	}
}));

describe('BrokersList - CSV Import entry point', () => {
	beforeEach(() => {
		vi.clearAllMocks();
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
		vi.mocked(brokerClient.getBrokerUserAccounts).mockResolvedValue([]);
		vi.mocked(accountClient.getAccounts).mockResolvedValue([]);
	});

	it('renders "Import CSV" button when brokers list is populated and clicking it opens the modal', async () => {
		const mockUsers: BrokerUser[] = [
			{
				id: 'user-1',
				displayName: 'My WS User',
				institution_id: Institution.Wealthsimple
			}
		];

		render(BrokersList, {
			props: {
				users: mockUsers
			}
		});

		const importBtn = screen.getByRole('button', { name: 'Import CSV' });
		expect(importBtn).toBeInTheDocument();

		await fireEvent.click(importBtn);

		await waitFor(() => {
			expect(screen.getByText('Import accounts from CSV')).toBeInTheDocument();
		});
	});

	it('renders "Import CSV" button when brokers list is empty and clicking it opens the modal', async () => {
		render(BrokersList, {
			props: {
				users: []
			}
		});

		const importBtn = screen.getByRole('button', { name: 'Import CSV' });
		expect(importBtn).toBeInTheDocument();

		await fireEvent.click(importBtn);

		await waitFor(() => {
			expect(screen.getByText('Import accounts from CSV')).toBeInTheDocument();
		});
	});
});
