import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import ConnectBrokerModal from './connect-broker-modal.svelte';
import { brokerClient } from '$lib/api/brokerClient';
import type { BackendInstitution } from '@/types/broker/broker';

vi.mock('$lib/api/brokerClient', () => ({
	brokerClient: {
		getAvailableInstitutions: vi.fn().mockResolvedValue([])
	},
	getBrokerClient: () => ({
		getAvailableInstitutions: vi.fn().mockResolvedValue([])
	})
}));

vi.mock('$lib/api/accountClient', () => ({
	accountClient: {
		inspectCsv: vi.fn(),
		importAccountsCsv: vi.fn()
	}
}));

describe('ConnectBrokerModal - CSV Import entry point', () => {
	const mockInstitutions: BackendInstitution[] = [
		{
			id: '1',
			name: 'Wealthsimple',
			logo: null,
			auth_type: 'oauth',
			created_at: '2026-01-01',
			csv_import_enabled: true
		}
	];

	let mockOnSuccess = vi.fn();

	beforeEach(() => {
		vi.clearAllMocks();
		mockOnSuccess = vi.fn();
		vi.mocked(brokerClient.getAvailableInstitutions).mockResolvedValue(mockInstitutions);
	});

	it('displays the CSV import action button and clicking it opens the CSV import modal', async () => {
		render(ConnectBrokerModal, {
			props: {
				open: true,
				onSuccess: () => mockOnSuccess()
			}
		});

		const csvImportBtn = screen.getByRole('button', { name: 'Import accounts from CSV' });
		expect(csvImportBtn).toBeInTheDocument();

		await fireEvent.click(csvImportBtn);

		await waitFor(() => {
			expect(screen.getByText('Import accounts from CSV')).toBeInTheDocument();
			expect(
				screen.getByText('Upload a CSV export from your broker to discover and import accounts.')
			).toBeInTheDocument();
		});
	});
});
