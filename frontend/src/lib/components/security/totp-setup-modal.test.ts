import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import TotpSetupModal from './totp-setup-modal.svelte';
import { securityClient } from '$lib/api/securityClient';
import QRCode from 'qrcode';

vi.mock('$lib/api/securityClient', () => {
	const mock = {
		setupTotp: vi.fn(),
		activateTotp: vi.fn(),
		get2FaStatus: vi.fn(),
		disableTotp: vi.fn(),
		regenerateRecoveryCodes: vi.fn(),
		getPasskeyRegistrationOptions: vi.fn(),
		verifyPasskeyRegistration: vi.fn(),
		getPasskeys: vi.fn(),
		renamePasskey: vi.fn(),
		deletePasskey: vi.fn()
	};
	return {
		securityClient: mock,
		getSecurityClient: () => mock
	};
});

vi.mock('qrcode', () => {
	return {
		default: {
			toDataURL: vi.fn().mockResolvedValue('data:image/png;base64,mockqrcodeimage')
		}
	};
});

describe('TotpSetupModal', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		Object.assign(navigator, {
			clipboard: {
				writeText: vi.fn().mockResolvedValue(undefined)
			}
		});
		vi.mocked(securityClient.setupTotp).mockResolvedValue({
			secret: 'TESTSECRETKEY123',
			provisioning_uri: 'otpauth://totp/RetailPortfolio:user@example.com?secret=TESTSECRETKEY123'
		});
	});

	it('renders QR code and secret key when opened', async () => {
		render(TotpSetupModal, {
			props: {
				open: true
			}
		});

		await waitFor(() => {
			expect(screen.getByText('Set up two-factor authentication')).toBeInTheDocument();
			expect(screen.getByDisplayValue('TESTSECRETKEY123')).toBeInTheDocument();
		});

		expect(QRCode.toDataURL).toHaveBeenCalledWith(
			'otpauth://totp/RetailPortfolio:user@example.com?secret=TESTSECRETKEY123',
			expect.any(Object)
		);
	});

	it('copies secret key to clipboard when copy button is clicked', async () => {
		render(TotpSetupModal, {
			props: {
				open: true
			}
		});

		await waitFor(() => {
			expect(screen.getByDisplayValue('TESTSECRETKEY123')).toBeInTheDocument();
		});

		const copyBtn = screen.getByTitle('Copy secret key');
		await fireEvent.click(copyBtn);

		expect(navigator.clipboard.writeText).toHaveBeenCalledWith('TESTSECRETKEY123');
	});

	it('verifies 6-digit code and displays backup recovery codes on success', async () => {
		const mockRecoveryCodes = [
			'code-1',
			'code-2',
			'code-3',
			'code-4',
			'code-5',
			'code-6',
			'code-7',
			'code-8'
		];
		vi.mocked(securityClient.activateTotp).mockResolvedValue({
			recovery_codes: mockRecoveryCodes,
			message: 'TOTP enabled'
		});

		const oncompleteMock = vi.fn();
		render(TotpSetupModal, {
			props: {
				open: true,
				oncomplete: oncompleteMock
			}
		});

		await waitFor(() => {
			expect(screen.getByPlaceholderText('123456')).toBeInTheDocument();
		});

		const input = screen.getByPlaceholderText('123456');
		await fireEvent.input(input, { target: { value: '654321' } });

		const submitBtn = screen.getByRole('button', { name: 'Verify & activate' });
		await fireEvent.click(submitBtn);

		expect(securityClient.activateTotp).toHaveBeenCalledWith('654321', undefined);

		await waitFor(() => {
			expect(screen.getByText('Two-factor authentication enabled')).toBeInTheDocument();
			expect(screen.getByText('code-1')).toBeInTheDocument();
			expect(screen.getByText('code-8')).toBeInTheDocument();
		});

		expect(oncompleteMock).toHaveBeenCalled();
	});

	it('copies recovery codes when Copy all codes is clicked', async () => {
		const mockRecoveryCodes = ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8'];
		vi.mocked(securityClient.activateTotp).mockResolvedValue({
			recovery_codes: mockRecoveryCodes,
			message: 'TOTP enabled'
		});

		render(TotpSetupModal, {
			props: {
				open: true
			}
		});

		await waitFor(() => {
			expect(screen.getByPlaceholderText('123456')).toBeInTheDocument();
		});

		const input = screen.getByPlaceholderText('123456');
		await fireEvent.input(input, { target: { value: '112233' } });
		const submitBtn = screen.getByRole('button', { name: 'Verify & activate' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(screen.getByText('Copy all codes')).toBeInTheDocument();
		});

		const copyAllBtn = screen.getByRole('button', { name: /Copy all codes/i });
		await fireEvent.click(copyAllBtn);

		expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockRecoveryCodes.join('\n'));
	});

	it('shows error when activation fails with invalid code', async () => {
		vi.mocked(securityClient.activateTotp).mockRejectedValue(
			new Error('Invalid TOTP verification code')
		);

		render(TotpSetupModal, {
			props: {
				open: true
			}
		});

		await waitFor(() => {
			expect(screen.getByPlaceholderText('123456')).toBeInTheDocument();
		});

		const input = screen.getByPlaceholderText('123456');
		await fireEvent.input(input, { target: { value: '000000' } });
		const submitBtn = screen.getByRole('button', { name: 'Verify & activate' });
		await fireEvent.click(submitBtn);

		await waitFor(() => {
			expect(screen.getByText('Invalid TOTP verification code')).toBeInTheDocument();
		});
	});
});
