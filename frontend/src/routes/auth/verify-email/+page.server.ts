import { AuthService } from '$lib/api/authService';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url, fetch }) => {
	const token = url.searchParams.get('token');

	if (!token) {
		return {
			status: 'error',
			message: 'No verification token provided. Please check your email link.'
		};
	}

	const authService = new AuthService(fetch);

	try {
		const response = await authService.verifyEmail(token);
		return {
			status: 'success',
			message: response.message || 'Your email has been successfully verified!'
		};
	} catch (e) {
		const message =
			e instanceof Error ? e.message : 'Verification failed. The link may be expired or invalid.';
		return {
			status: 'error',
			message
		};
	}
};
