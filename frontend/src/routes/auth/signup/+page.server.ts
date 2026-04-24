import { AuthService } from '$lib/api/authService';
import { ApiError } from '$lib/api/apiClient';
import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
	default: async ({ request, fetch }) => {
		const data = await request.formData();
		const email = data.get('email');
		const password = data.get('password');
		const confirmPassword = data.get('confirmPassword');

		if (
			typeof email !== 'string' ||
			typeof password !== 'string' ||
			typeof confirmPassword !== 'string' ||
			!email ||
			!password ||
			!confirmPassword
		) {
			return fail(400, { email, message: 'All fields are required' });
		}

		if (password !== confirmPassword) {
			return fail(400, { email, message: 'Passwords do not match' });
		}

		const authService = new AuthService(fetch);

		try {
			await authService.signup({ email, password });
		} catch (err) {
			let message = 'Signup failed. Please try again.';
			let status = 500;
			if (err instanceof ApiError) {
				status = err.status;
				if (err.status === 409) {
					message = 'Account with this email already exists.';
				}
			}
			return fail(status, {
				email,
				message
			});
		}

		throw redirect(303, '/auth/signup/confirmation');
	}
};
