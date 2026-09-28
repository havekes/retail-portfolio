import { getPortfolioClient } from '$lib/api/portfolioClient';
import { deleteAuthCookie } from '$lib/server/auth-cookie';
import { error, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
	const token = cookies.get('auth_token');
	try {
		const portfolios = await getPortfolioClient(fetch).getPortfolios(token);
		return {
			portfolios
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
