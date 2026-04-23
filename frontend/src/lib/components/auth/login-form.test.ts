import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginForm from './login-form.svelte';
import { authService, type AuthResponse } from '$lib/api/authService';

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$lib/api/authService', () => ({
	authService: {
		login: vi.fn()
	}
}));

describe('LoginForm Component', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		window.location.href = '';
	});

	it('renders login form properly', () => {
		render(LoginForm);
		expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
		expect(screen.getByPlaceholderText('Password')).toBeInTheDocument();
		expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument();
	});

	it('shows loading state during submission', async () => {
		vi.mocked(authService.login).mockImplementation(
			() => new Promise((resolve) => setTimeout(resolve, 100))
		);
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

	it('reloads page on successful login', async () => {
		const mockResponse: AuthResponse = {
			user: { id: 1, email: 'test@example.com' },
			access_token: 'token-abc',
			token_type: 'bearer'
		};
		vi.mocked(authService.login).mockResolvedValueOnce(mockResponse);

		render(LoginForm);
		const emailInput = screen.getByPlaceholderText('Email');
		const passwordInput = screen.getByPlaceholderText('Password');
		const submitButton = screen.getByRole('button', { name: 'Login' });

		const user = userEvent.setup();
		await user.type(emailInput, 'test@example.com');
		await user.type(passwordInput, 'password123');
		await user.click(submitButton);

		// Await for assertions
		await vi.waitUntil(() => vi.mocked(authService.login).mock.calls.length > 0);

		expect(authService.login).toHaveBeenCalledWith({
			email: 'test@example.com',
			password: 'password123'
		});
		expect(window.location.href).toBe('/');
	});

	it('shows error when login fails', async () => {
		vi.mocked(authService.login).mockRejectedValueOnce(new Error('Auth failed'));

		render(LoginForm);
		const emailInput = screen.getByPlaceholderText('Email');
		const passwordInput = screen.getByPlaceholderText('Password');
		const submitButton = screen.getByRole('button', { name: 'Login' });

		const user = userEvent.setup();
		await user.type(emailInput, 'test@example.com');
		await user.type(passwordInput, 'password123');
		await user.click(submitButton);

		expect(
			await screen.findByText('Login failed. Please check your credentials.')
		).toBeInTheDocument();
	});
});
