import { AuthService } from '$lib/api/authService';
import { ApiError } from '$lib/api/apiClient';
import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
	default: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const email = data.get('email');
		const password = data.get('password');

		if (typeof email !== 'string' || typeof password !== 'string' || !email || !password) {
			return fail(400, { email, message: 'Email and password are required' });
		}

		const authService = new AuthService(fetch);

		try {
			const response = await authService.login({ email, password });

			// Sync with backend cookie settings in src/auth/router.py
			cookies.set('auth_token', response.access_token, {
				path: '/',
				httpOnly: true, // Should be true for security
				sameSite: 'lax',
				secure: false, // Set to true in prod
				maxAge: 60 * 60 * 24 * 7 // 1 week
			});
		} catch (err) {
			let message = 'Login failed. Please check your credentials.';
			let status = 500;
			if (err instanceof ApiError) {
				status = err.status;
				if (err.status === 403) {
					message = 'Email not verified. Please check your inbox for a verification link.';
				}
			}
			return fail(status, {
				email,
				message
			});
		}

		throw redirect(303, '/');
	}
};
