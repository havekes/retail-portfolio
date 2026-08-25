import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import PasskeyListItem from './passkey-list-item.svelte';
import { securityClient } from '$lib/api/securityClient';

vi.mock('$lib/api/securityClient', () => {
	const mock = {
		getPasskeys: vi.fn(),
		renamePasskey: vi.fn(),
		deletePasskey: vi.fn(),
		get2FaStatus: vi.fn(),
		setupTotp: vi.fn(),
		activateTotp: vi.fn(),
		disableTotp: vi.fn(),
		regenerateRecoveryCodes: vi.fn(),
		getPasskeyRegistrationOptions: vi.fn(),
		verifyPasskeyRegistration: vi.fn()
	};
	return {
		securityClient: mock,
		getSecurityClient: () => mock
	};
});

describe('PasskeyListItem', () => {
	const mockPasskey = {
		id: 'pk-test-123',
		name: 'MacBook Pro Touch ID',
		created_at: '2026-08-25T10:00:00Z',
		last_used_at: '2026-08-25T12:30:00Z',
		transports: ['internal']
	};

	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders passkey name, creation date, last used date, and transports badge', () => {
		render(PasskeyListItem, {
			props: {
				passkey: mockPasskey
			}
		});

		expect(screen.getByText('MacBook Pro Touch ID')).toBeInTheDocument();
		expect(screen.getByText(/Created/i)).toBeInTheDocument();
		expect(screen.getByText(/Last used/i)).toBeInTheDocument();
		expect(screen.getByText(/internal/i)).toBeInTheDocument();
	});

	it('opens rename modal and updates passkey name', async () => {
		vi.mocked(securityClient.renamePasskey).mockResolvedValue({
			...mockPasskey,
			name: 'Work MacBook'
		});

		render(PasskeyListItem, {
			props: {
				passkey: mockPasskey
			}
		});

		const renameBtn = screen.getByRole('button', { name: /Rename/i });
		await fireEvent.click(renameBtn);

		await waitFor(() => {
			expect(screen.getByText('Rename passkey')).toBeInTheDocument();
		});

		const input = screen.getByLabelText('Passkey name');
		expect((input as HTMLInputElement).value).toBe('MacBook Pro Touch ID');

		await fireEvent.input(input, { target: { value: 'Work MacBook' } });

		const saveBtn = screen.getByRole('button', { name: 'Save changes' });
		await fireEvent.click(saveBtn);

		expect(securityClient.renamePasskey).toHaveBeenCalledWith(
			'pk-test-123',
			'Work MacBook',
			undefined
		);
	});

	it('opens delete confirmation modal and calls deletePasskey on confirmation', async () => {
		vi.mocked(securityClient.deletePasskey).mockResolvedValue({
			message: 'Passkey deleted'
		});

		render(PasskeyListItem, {
			props: {
				passkey: mockPasskey
			}
		});

		const deleteBtn = screen.getByRole('button', { name: /Delete/i });
		await fireEvent.click(deleteBtn);

		await waitFor(() => {
			expect(screen.getByText('Delete passkey')).toBeInTheDocument();
			expect(
				screen.getByText(
					/Are you sure you want to delete "MacBook Pro Touch ID"\? You will no longer be able to use it to sign in\./i
				)
			).toBeInTheDocument();
		});

		const confirmBtn = screen.getByRole('button', { name: 'Confirm' });
		await fireEvent.click(confirmBtn);

		expect(securityClient.deletePasskey).toHaveBeenCalledWith('pk-test-123', undefined);
	});
});
