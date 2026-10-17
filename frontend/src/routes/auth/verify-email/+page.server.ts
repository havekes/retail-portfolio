import { AuthService } from '$lib/api/authService';
import { extractTraceparent } from '$lib/api/traceContext';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url, fetch, request }) => {
	const token = url.searchParams.get('token');

	if (!token) {
		return {
			status: 'error',
			message: 'No verification token provided. Please check your email link.'
		};
	}

	const authService = new AuthService(fetch, extractTraceparent(request.headers));

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
