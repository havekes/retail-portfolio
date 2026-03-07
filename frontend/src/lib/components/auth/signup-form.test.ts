import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SignupForm from './signup-form.svelte';
import { SignupFormState } from './signup-form.svelte.js';
import { authService, type SignupResponse } from '$lib/services/authService';
import { APIError } from '$lib/services/baseService';
import { userStore } from '$lib/stores/userStore';
import { goto } from '$app/navigation';

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

vi.mock('$lib/services/authService', () => ({
	authService: {
		signup: vi.fn()
	}
}));

vi.mock('$lib/stores/userStore', () => ({
	userStore: {
		setUser: vi.fn()
	}
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
		expect(authService.signup).not.toHaveBeenCalled();
	});

	it('shows HTML validation loading state during submission', async () => {
		vi.mocked(authService.signup).mockImplementation(
			() => new Promise((resolve) => setTimeout(resolve, 100))
		);
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

	it('navigates to confirmation page on successful signup', async () => {
		const mockResponse: SignupResponse = {
			message: 'Signup successful'
		};
		vi.mocked(authService.signup).mockResolvedValueOnce(mockResponse);

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

		await vi.waitUntil(() => vi.mocked(authService.signup).mock.calls.length > 0);

		expect(authService.signup).toHaveBeenCalledWith({
			email: 'test@example.com',
			password: 'password123'
		});
		expect(userStore.setUser).not.toHaveBeenCalled();
		expect(goto).toHaveBeenCalledWith('/auth/signup/confirmation');
	});

	it('shows error when signup fails', async () => {
		vi.mocked(authService.signup).mockRejectedValueOnce(new Error('Signup failed'));

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

		expect(await screen.findByText('Signup failed. Please try again.')).toBeInTheDocument();
	});
	it('shows specific error when email already exists (409)', async () => {
		const apiError = new APIError(409, 'Conflict');
		vi.mocked(authService.signup).mockRejectedValueOnce(apiError);

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

		expect(await screen.findByText('Account with this email already exists.')).toBeInTheDocument();
		expect(goto).not.toHaveBeenCalled();
	});
});

describe('SignupFormState Class', () => {
	it('initializes with default values', () => {
		const state = new SignupFormState();
		expect(state.email).toBe('');
		expect(state.password).toBe('');
		expect(state.confirmPassword).toBe('');
		expect(state.isLoading).toBe(false);
		expect(state.error).toBeNull();
	});
});
