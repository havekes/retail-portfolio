import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SignupForm from './signup-form.svelte';

vi.mock('$app/forms', () => ({
	enhance: vi.fn(() => ({
		destroy: vi.fn()
	}))
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

describe('SignupForm Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders signup form properly', () => {
		render(SignupForm);
		expect(screen.getByPlaceholderText('m@example.com')).toBeInTheDocument();
		expect(screen.getByLabelText('Password')).toBeInTheDocument();
		expect(screen.getByLabelText('Confirm Password')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Sign Up' })).toBeInTheDocument();
	});

	it('shows error when passwords do not match', async () => {
		// Mock enhance to run client-side validation
		const { enhance } = await import('$app/forms');
		vi.mocked(enhance).mockImplementation((node, submit) => {
			const handler = async (e: Event) => {
				e.preventDefault();
				if (submit) {
					// @ts-expect-error - simplified mock for testing
					await submit({
						formElement: node,
						formData: new FormData(node),
						action: new URL(node.action || 'http://localhost/'),
						cancel: () => {}
					});
				}
			};
			node.addEventListener('submit', handler);
			return {
				destroy: () => node.removeEventListener('submit', handler)
			};
		});

		render(SignupForm);

		const emailInput = screen.getByPlaceholderText('m@example.com');
		const passwordInput = screen.getByLabelText('Password');
		const confirmInput = screen.getByLabelText('Confirm Password');
		const submitButton = screen.getByRole('button', { name: 'Sign Up' });

		const user = userEvent.setup();
		await user.type(emailInput, 'test@example.com');
		await user.type(passwordInput, 'password123');
		await user.type(confirmInput, 'password456');
		await user.click(submitButton);

		expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument();
	});

	it('shows HTML validation loading state during submission', async () => {
		// Mock enhance to simulate loading state
		const { enhance } = await import('$app/forms');
		vi.mocked(enhance).mockImplementation((node, submit) => {
			const handler = async (e: Event) => {
				e.preventDefault();
				if (submit) {
					// @ts-expect-error - simplified mock for testing
					await submit({
						formElement: node,
						formData: new FormData(node),
						action: new URL(node.action || 'http://localhost/'),
						cancel: () => {}
					});
				}
			};
			node.addEventListener('submit', handler);
			return {
				destroy: () => node.removeEventListener('submit', handler)
			};
		});

		render(SignupForm);

		const emailInput = screen.getByPlaceholderText('m@example.com');
		const passwordInput = screen.getByLabelText('Password');
		const confirmInput = screen.getByLabelText('Confirm Password');
		const submitButton = screen.getByRole('button', { name: 'Sign Up' });

		const user = userEvent.setup();
		await user.type(emailInput, 'test@example.com');
		await user.type(passwordInput, 'password123');
		await user.type(confirmInput, 'password123');

		await user.click(submitButton);

		expect(submitButton).toHaveTextContent('Signing up...');
		expect(submitButton).toBeDisabled();
	});

	it('shows error when signup fails', async () => {
		render(SignupForm, {
			props: {
				form: { message: 'Signup failed. Please try again.' }
			}
		});

		expect(await screen.findByText('Signup failed. Please try again.')).toBeInTheDocument();
	});

	it('shows specific error when email already exists (409)', async () => {
		render(SignupForm, {
			props: {
				form: { message: 'Account with this email already exists.' }
			}
		});

		expect(await screen.findByText('Account with this email already exists.')).toBeInTheDocument();
	});
});
