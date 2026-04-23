import { AuthService } from '$lib/api/authService';
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
		} catch (err: any) {
			let message = 'Signup failed. Please try again.';
			if (err.status === 409) {
				message = 'Account with this email already exists.';
			}
			return fail(err.status || 500, {
				email,
				message
			});
		}

		throw redirect(303, '/auth/signup/confirmation');
	}
};
