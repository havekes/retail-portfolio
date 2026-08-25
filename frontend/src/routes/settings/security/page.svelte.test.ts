import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import { securityClient } from '$lib/api/securityClient';
import { startRegistration, browserSupportsWebAuthn } from '@simplewebauthn/browser';

vi.mock('$lib/api/securityClient', () => {
	const mock = {
		get2FaStatus: vi.fn(),
		getPasskeys: vi.fn(),
		setupTotp: vi.fn(),
		activateTotp: vi.fn(),
		disableTotp: vi.fn(),
		regenerateRecoveryCodes: vi.fn(),
		getPasskeyRegistrationOptions: vi.fn(),
		verifyPasskeyRegistration: vi.fn(),
		renamePasskey: vi.fn(),
		deletePasskey: vi.fn()
	};
	return {
		securityClient: mock,
		getSecurityClient: () => mock
	};
});

vi.mock('@simplewebauthn/browser', () => {
	return {
		browserSupportsWebAuthn: vi.fn().mockReturnValue(true),
		startRegistration: vi.fn()
	};
});

vi.mock('qrcode', () => {
	return {
		default: {
			toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,mockqr')
		}
	};
});

describe('Security Settings Page (+page.svelte)', () => {
	const mockInitialData = {
		user: { id: 'u-1', email: 'user@example.com' },
		sidebar_open: true,
		status: {
			totp_enabled: false,
			recovery_codes_remaining: 0
		},
		passkeys: [
			{
				id: 'pk-1',
				name: 'MacBook Touch ID',
				created_at: '2026-08-25T10:00:00Z',
				last_used_at: '2026-08-25T12:00:00Z',
				transports: ['internal']
			}
		]
	};

	beforeEach(() => {
		vi.clearAllMocks();
		Object.assign(navigator, {
			clipboard: {
				writeText: vi.fn().mockResolvedValue(undefined)
			}
		});
		vi.mocked(browserSupportsWebAuthn).mockReturnValue(true);
	});

	it('renders security settings header, 2FA status card, and passkeys card', async () => {
		render(Page, {
			props: {
				data: mockInitialData
			}
		});

		await waitFor(() => {
			expect(screen.getByText('Security settings')).toBeInTheDocument();
			expect(screen.getByText('Manage two-factor authentication and passkeys')).toBeInTheDocument();
			expect(screen.getByText('Two-Factor Authentication (2FA)')).toBeInTheDocument();
			expect(screen.getByText('Disabled')).toBeInTheDocument();
			expect(screen.getByText('Passkeys')).toBeInTheDocument();
			expect(screen.getByText('MacBook Touch ID')).toBeInTheDocument();
		});
	});

	it('renders 2FA enabled card with recovery codes count when totp_enabled is true', async () => {
		render(Page, {
			props: {
				data: {
					user: { id: 'u-1', email: 'user@example.com' },
					sidebar_open: true,
					status: {
						totp_enabled: true,
						recovery_codes_remaining: 6
					},
					passkeys: []
				}
			}
		});

		await waitFor(() => {
			expect(screen.getByText('Enabled')).toBeInTheDocument();
			expect(screen.getByText('6 codes remaining')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: /Disable 2FA/i })).toBeInTheDocument();
			expect(screen.getByRole('button', { name: /Regenerate codes/i })).toBeInTheDocument();
		});
	});

	it('disables 2FA when disable modal is confirmed', async () => {
		vi.mocked(securityClient.disableTotp).mockResolvedValue({
			message: 'TOTP disabled'
		});

		render(Page, {
			props: {
				data: {
					user: { id: 'u-1', email: 'user@example.com' },
					sidebar_open: true,
					status: {
						totp_enabled: true,
						recovery_codes_remaining: 8
					},
					passkeys: []
				}
			}
		});

		await waitFor(() => {
			expect(screen.getByRole('button', { name: /Disable 2FA/i })).toBeInTheDocument();
		});

		const disableBtn = screen.getByRole('button', { name: /Disable 2FA/i });
		await fireEvent.click(disableBtn);

		await waitFor(() => {
			expect(
				screen.getByRole('heading', { name: 'Disable two-factor authentication' })
			).toBeInTheDocument();
		});

		const confirmDisableBtn = screen.getAllByRole('button', { name: /Disable 2FA/i })[1];
		await fireEvent.click(confirmDisableBtn);

		expect(securityClient.disableTotp).toHaveBeenCalled();

		await waitFor(() => {
			expect(screen.getByText('Disabled')).toBeInTheDocument();
		});
	});

	it('registers a new passkey via WebAuthn and adds it to the list', async () => {
		vi.mocked(securityClient.getPasskeyRegistrationOptions).mockResolvedValue({
			challenge: 'mock-challenge'
		} as never);
		vi.mocked(startRegistration).mockResolvedValue({
			id: 'cred-123',
			rawId: 'raw-123',
			response: {} as never,
			type: 'public-key',
			clientExtensionResults: {}
		});
		vi.mocked(securityClient.verifyPasskeyRegistration).mockResolvedValue({
			id: 'pk-new',
			name: 'YubiKey 5C',
			created_at: '2026-08-25T11:00:00Z',
			last_used_at: null,
			transports: ['usb']
		});

		render(Page, {
			props: {
				data: {
					user: { id: 'u-1', email: 'user@example.com' },
					sidebar_open: true,
					status: {
						totp_enabled: false,
						recovery_codes_remaining: 0
					},
					passkeys: []
				}
			}
		});

		await waitFor(() => {
			expect(screen.getByText('No passkeys registered')).toBeInTheDocument();
		});

		const addPasskeyBtn = screen.getByRole('button', { name: /Add Passkey/i });
		await fireEvent.click(addPasskeyBtn);

		await waitFor(() => {
			expect(screen.getByText('Add new passkey')).toBeInTheDocument();
		});

		const nameInput = screen.getByLabelText('Passkey name');
		await fireEvent.input(nameInput, { target: { value: 'YubiKey 5C' } });

		const continueBtn = screen.getByRole('button', { name: 'Continue' });
		await fireEvent.click(continueBtn);

		expect(securityClient.getPasskeyRegistrationOptions).toHaveBeenCalled();
		expect(startRegistration).toHaveBeenCalled();
		expect(securityClient.verifyPasskeyRegistration).toHaveBeenCalledWith(
			{
				credential: expect.any(Object),
				name: 'YubiKey 5C'
			},
			undefined
		);

		await waitFor(() => {
			expect(screen.getByText('YubiKey 5C')).toBeInTheDocument();
			expect(screen.getByText(/usb/i)).toBeInTheDocument();
		});
	});
});
