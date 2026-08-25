import { dev } from '$app/environment';
import { AuthService, type PasskeyAuthenticateVerifyRequest } from '$lib/api/authService';
import { ApiError } from '$lib/api/apiClient';
import { fail, redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
	login: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const email = data.get('email');
		const password = data.get('password');

		if (typeof email !== 'string' || typeof password !== 'string' || !email || !password) {
			return fail(400, {
				email: typeof email === 'string' ? email : '',
				message: 'Email and password are required'
			});
		}

		const authService = new AuthService(fetch);

		try {
			const response = await authService.login({ email, password });

			if ('requires_2fa' in response && response.requires_2fa) {
				return {
					requires2fa: true,
					mfaToken: response.mfa_token,
					email
				};
			}

			if ('access_token' in response) {
				cookies.set('auth_token', response.access_token, {
					path: '/',
					httpOnly: true,
					sameSite: 'lax',
					secure: !dev,
					maxAge: 60 * 60 * 24 * 7 // 1 week
				});
			}
		} catch (err) {
			if (err && typeof err === 'object' && 'status' in err && 'location' in err) {
				throw err;
			}
			let message = 'Login failed. Please check your credentials.';
			let status = 500;
			if (err instanceof ApiError) {
				status = err.status;
				if (err.status === 403) {
					message = 'Email not verified. Please check your inbox for a verification link.';
				} else if (err.message) {
					message = err.message;
				}
			}
			return fail(status, {
				email,
				message
			});
		}

		throw redirect(303, '/');
	},

	verify2fa: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const mfaToken = data.get('mfaToken') ?? data.get('mfa_token');
		const code = data.get('code');
		const email = data.get('email');

		const emailStr = typeof email === 'string' ? email : '';
		const mfaTokenStr = typeof mfaToken === 'string' ? mfaToken : '';

		if (!mfaTokenStr || typeof code !== 'string' || !code.trim()) {
			return fail(400, {
				requires2fa: true,
				mfaToken: mfaTokenStr,
				email: emailStr,
				message: 'Verification code is required'
			});
		}

		const authService = new AuthService(fetch);

		try {
			const response = await authService.loginVerify2Fa({
				mfa_token: mfaTokenStr,
				code: code.trim()
			});

			cookies.set('auth_token', response.access_token, {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				secure: !dev,
				maxAge: 60 * 60 * 24 * 7 // 1 week
			});
		} catch (err) {
			if (err && typeof err === 'object' && 'status' in err && 'location' in err) {
				throw err;
			}
			let message = 'Invalid or expired verification code';
			let status = 500;
			if (err instanceof ApiError) {
				status = err.status;
				if (err.message) {
					message = err.message;
				}
			}
			return fail(status, {
				requires2fa: true,
				mfaToken: mfaTokenStr,
				email: emailStr,
				message
			});
		}

		throw redirect(303, '/');
	},

	passkeyLogin: async ({ request, cookies, fetch }) => {
		const data = await request.formData();
		const credential = data.get('credential');
		const email = data.get('email');

		if (typeof credential !== 'string' || !credential) {
			return fail(400, { message: 'Passkey credential is required' });
		}

		let parsedCredential: unknown;
		try {
			parsedCredential = JSON.parse(credential);
		} catch {
			return fail(400, { message: 'Invalid credential payload' });
		}

		const authService = new AuthService(fetch);

		try {
			const response = await authService.verifyPasskeyAuth({
				credential: parsedCredential as PasskeyAuthenticateVerifyRequest['credential'],
				email: typeof email === 'string' && email.trim() ? email.trim() : undefined
			});

			cookies.set('auth_token', response.access_token, {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				secure: !dev,
				maxAge: 60 * 60 * 24 * 7 // 1 week
			});
		} catch (err) {
			if (err && typeof err === 'object' && 'status' in err && 'location' in err) {
				throw err;
			}
			let message = 'Passkey authentication failed';
			let status = 500;
			if (err instanceof ApiError) {
				status = err.status;
				if (err.message) {
					message = err.message;
				}
			}
			return fail(status, { message });
		}

		throw redirect(303, '/');
	}
};
