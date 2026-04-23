import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginForm from './login-form.svelte';

vi.mock('$app/forms', () => ({
	enhance: vi.fn(() => ({
		destroy: vi.fn()
	}))
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

describe('LoginForm Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders login form properly', () => {
		render(LoginForm);
		expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
	});

	it('shows loading state during submission', async () => {
		// Mock enhance to simulate loading state
		const { enhance } = await import('$app/forms');
		vi.mocked(enhance).mockImplementation((node, submit) => {
			const handler = async (e: Event) => {
				e.preventDefault();
				if (submit) {
					// @ts-expect-error - simplified mock for testing
					const updateFunc = await submit({
						formElement: node,
						formData: new FormData(node),
						action: new URL(node.action),
						cancel: () => {}
					});
					// We don't call updateFunc here to stay in loading state
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

	it('shows error when login fails', async () => {
		render(LoginForm, {
			props: {
				form: { message: 'Login failed. Please check your credentials.' }
			}
		});

		expect(screen.getByText('Login failed. Please check your credentials.')).toBeInTheDocument();
	});
});
