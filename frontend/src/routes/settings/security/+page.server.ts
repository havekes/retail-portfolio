import { getSecurityClient } from '$lib/api/securityClient';
import { deleteAuthCookie } from '$lib/server/auth-cookie';
import { error, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
	const token = cookies.get('auth_token');
	if (!token) {
		throw redirect(303, '/auth/login?clear_session=true');
	}

	const securityClient = getSecurityClient(fetch);
	try {
		const [status, passkeys] = await Promise.all([
			securityClient.get2FaStatus(token),
			securityClient.getPasskeys(token)
		]);

		return {
			status,
			passkeys
		};
	} catch (err) {
		if (err instanceof ApiError) {
			if (err.status === 401) {
				deleteAuthCookie(cookies);
				throw redirect(303, '/auth/login?clear_session=true');
			}
			throw error(err.status, err.message);
		}
		throw error(500, 'Internal Server Error');
	}
};
