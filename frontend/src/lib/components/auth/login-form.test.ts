import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginForm from './login-form.svelte';
import {
	startAuthentication,
	browserSupportsWebAuthn,
	type PublicKeyCredentialRequestOptionsJSON,
	type AuthenticationResponseJSON
} from '@simplewebauthn/browser';
import { authService } from '$lib/api/authService';
import { goto } from '$app/navigation';
import { deserialize } from '$app/forms';

vi.mock('$app/forms', () => ({
	enhance: vi.fn(() => ({
		destroy: vi.fn()
	})),
	deserialize: vi.fn()
}));

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('@simplewebauthn/browser', () => ({
	browserSupportsWebAuthn: vi.fn(),
	startAuthentication: vi.fn()
}));

vi.mock('$lib/api/authService', () => ({
	authService: {
		getPasskeyAuthOptions: vi.fn(),
		verifyPasskeyAuth: vi.fn()
	}
}));

describe('LoginForm Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		vi.mocked(browserSupportsWebAuthn).mockReturnValue(true);
	});

	it('renders standard login form with passkey button properly', () => {
		render(LoginForm);
		expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
		expect(screen.getByRole('button', { name: /Sign in with a Passkey/i })).toBeInTheDocument();
	});

	it('shows loading state during submission', async () => {
		const { enhance } = await import('$app/forms');
		vi.mocked(enhance).mockImplementation((node, submit) => {
			const handler = async (e: Event) => {
				e.preventDefault();
				if (submit) {
					// @ts-expect-error - simplified mock for testing
					await submit({
						formElement: node,
						formData: new FormData(node),
						action: new URL(node.action, 'http://localhost'),
						cancel: () => {}
					});
				}
			};
			node.addEventListener('submit', handler);
			return {
				destroy: () => node.removeEventListener('submit', handler)
			};
		});

		render(LoginForm);

		const emailInput = screen.getByPlaceholderText('Email');
		const passwordInput = screen.getByPlaceholderText('Password');
		const submitButton = screen.getByRole('button', { name: 'Login' });

		const user = userEvent.setup();
		await user.type(emailInput, 'test@example.com');
		await user.type(passwordInput, 'password123');
		await user.click(submitButton);

		expect(submitButton).toHaveTextContent('Logging in...');
		expect(submitButton).toBeDisabled();
	});

	it('shows error when standard login fails', async () => {
		render(LoginForm, {
			props: {
				form: { message: 'Login failed. Please check your credentials.' }
			}
		});

		expect(screen.getByText('Login failed. Please check your credentials.')).toBeInTheDocument();
	});

	describe('2FA Challenge Stage', () => {
		it('renders 2FA prompt when form has requires2fa', () => {
			render(LoginForm, {
				props: {
					form: {
						requires2fa: true,
						mfaToken: 'mfa-token-123',
						email: 'user@example.com'
					}
				}
			});

			expect(screen.getByText('Two-Factor Authentication')).toBeInTheDocument();
			expect(
				screen.getByText('Enter the 6-digit verification code from your authenticator app.')
			).toBeInTheDocument();
			expect(screen.getByPlaceholderText('6-digit code')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Verify' })).toBeInTheDocument();
			expect(
				screen.getByRole('button', { name: 'Use a recovery code instead' })
			).toBeInTheDocument();
			expect(screen.getByRole('button', { name: /Back to login/i })).toBeInTheDocument();
			expect(screen.queryByPlaceholderText('Email')).not.toBeInTheDocument();
		});

		it('toggles between TOTP code input and recovery code input', async () => {
			const user = userEvent.setup();
			render(LoginForm, {
				props: {
					form: {
						requires2fa: true,
						mfaToken: 'mfa-token-123',
						email: 'user@example.com'
					}
				}
			});

			const toggleButton = screen.getByRole('button', { name: 'Use a recovery code instead' });
			await user.click(toggleButton);

			expect(screen.getByText('Enter an 8-character recovery code.')).toBeInTheDocument();
			expect(screen.getByPlaceholderText('Recovery Code (e.g. 1a2b3c4d)')).toBeInTheDocument();
			expect(
				screen.getByRole('button', { name: 'Use authenticator app instead' })
			).toBeInTheDocument();

			await user.click(screen.getByRole('button', { name: 'Use authenticator app instead' }));
			expect(screen.getByPlaceholderText('6-digit code')).toBeInTheDocument();
		});

		it('switches back to standard login on Back to login click', async () => {
			const user = userEvent.setup();
			render(LoginForm, {
				props: {
					form: {
						requires2fa: true,
						mfaToken: 'mfa-token-123',
						email: 'user@example.com'
					}
				}
			});

			const backButton = screen.getByRole('button', { name: /Back to login/i });
			await user.click(backButton);

			expect(screen.queryByText('Two-Factor Authentication')).not.toBeInTheDocument();
			expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
			expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
			expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
		});

		it('displays error in 2FA mode when verification fails', () => {
			render(LoginForm, {
				props: {
					form: {
						requires2fa: true,
						mfaToken: 'mfa-token-123',
						email: 'user@example.com',
						message: 'Invalid 2FA code'
					}
				}
			});

			expect(screen.getByText('Invalid 2FA code')).toBeInTheDocument();
		});
	});

	describe('Passkey Sign-In Ceremony', () => {
		it('displays error if WebAuthn is not supported by the browser', async () => {
			vi.mocked(browserSupportsWebAuthn).mockReturnValue(false);
			const user = userEvent.setup();

			render(LoginForm);

			const passkeyBtn = screen.getByRole('button', { name: /Sign in with a Passkey/i });
			await user.click(passkeyBtn);

			expect(
				screen.getByText('WebAuthn is not supported on this device or browser')
			).toBeInTheDocument();
			expect(authService.getPasskeyAuthOptions).not.toHaveBeenCalled();
		});

		it('handles user cancelling the passkey prompt gracefully (NotAllowedError)', async () => {
			const user = userEvent.setup();
			vi.mocked(authService.getPasskeyAuthOptions).mockResolvedValue({
				challenge: 'test-challenge',
				rpId: 'localhost'
			} as unknown as PublicKeyCredentialRequestOptionsJSON);

			const cancelError = new Error('The operation either timed out or was not allowed');
			cancelError.name = 'NotAllowedError';
			vi.mocked(startAuthentication).mockRejectedValue(cancelError);

			render(LoginForm);

			const passkeyBtn = screen.getByRole('button', { name: /Sign in with a Passkey/i });
			await user.click(passkeyBtn);

			expect(
				screen.getByText('Passkey authentication was cancelled or timed out')
			).toBeInTheDocument();
			expect(passkeyBtn).not.toBeDisabled();
		});

		it('handles passkey ceremony general error', async () => {
			const user = userEvent.setup();
			vi.mocked(authService.getPasskeyAuthOptions).mockResolvedValue({
				challenge: 'test-challenge',
				rpId: 'localhost'
			} as unknown as PublicKeyCredentialRequestOptionsJSON);
			vi.mocked(startAuthentication).mockRejectedValue(new Error('Hardware security key error'));

			render(LoginForm);

			const passkeyBtn = screen.getByRole('button', { name: /Sign in with a Passkey/i });
			await user.click(passkeyBtn);

			expect(screen.getByText('Hardware security key error')).toBeInTheDocument();
		});

		it('executes successful passkey login and redirects', async () => {
			const user = userEvent.setup();
			const mockOptions = {
				challenge: 'auth-challenge',
				rpId: 'localhost'
			} as unknown as PublicKeyCredentialRequestOptionsJSON;
			const mockAssertion = {
				id: 'cred-123',
				rawId: 'raw-123',
				type: 'public-key'
			} as unknown as AuthenticationResponseJSON;

			vi.mocked(authService.getPasskeyAuthOptions).mockResolvedValue(mockOptions);
			vi.mocked(startAuthentication).mockResolvedValue(mockAssertion);

			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				text: async () => '{"type":"redirect","status":303,"location":"/"}'
			} as Response);

			vi.mocked(deserialize).mockReturnValue({
				type: 'redirect',
				status: 303,
				location: '/'
			});

			render(LoginForm);

			const emailInput = screen.getByPlaceholderText('Email');
			await user.type(emailInput, 'passkey-user@example.com');

			const passkeyBtn = screen.getByRole('button', { name: /Sign in with a Passkey/i });
			await user.click(passkeyBtn);

			expect(authService.getPasskeyAuthOptions).toHaveBeenCalledWith({
				email: 'passkey-user@example.com'
			});
			expect(startAuthentication).toHaveBeenCalledWith({
				optionsJSON: mockOptions
			});
			expect(global.fetch).toHaveBeenCalledWith(
				'?/passkeyLogin',
				expect.objectContaining({
					method: 'POST'
				})
			);
			expect(goto).toHaveBeenCalledWith('/');
		});

		it('handles passkeyLogin server action failure', async () => {
			const user = userEvent.setup();
			vi.mocked(authService.getPasskeyAuthOptions).mockResolvedValue({
				challenge: 'c'
			} as unknown as PublicKeyCredentialRequestOptionsJSON);
			vi.mocked(startAuthentication).mockResolvedValue({
				id: 'cred-1'
			} as unknown as AuthenticationResponseJSON);

			vi.mocked(global.fetch).mockResolvedValue({
				ok: true,
				text: async () =>
					'{"type":"failure","status":400,"data":{"message":"Passkey not recognized"}}'
			} as Response);

			vi.mocked(deserialize).mockReturnValue({
				type: 'failure',
				status: 400,
				data: { message: 'Passkey not recognized' }
			});

			render(LoginForm);

			const passkeyBtn = screen.getByRole('button', { name: /Sign in with a Passkey/i });
			await user.click(passkeyBtn);

			expect(screen.getByText('Passkey not recognized')).toBeInTheDocument();
		});
	});
});
