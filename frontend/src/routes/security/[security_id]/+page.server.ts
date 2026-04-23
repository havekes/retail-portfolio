import { getMarketService } from '@/api/marketService';
import { error, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params, fetch, cookies }) => {
	const { security_id } = params;

	if (!security_id) {
		throw error(400, 'Security ID is required');
	}

	const marketService = getMarketService(fetch);
	const token = cookies.get('auth_token');

	try {
		const from = '2000-01-03';
		const to = new Date().toISOString().split('T')[0];

		const [security, priceResponse] = await Promise.all([
			marketService.getSecurity(security_id, token),
			marketService.getPrices(security_id, from, to, token)
		]);

		if (!priceResponse.prices || priceResponse.prices.length === 0) {
			throw error(404, 'No price data available for this security');
		}

		return {
			security,
			prices: priceResponse.prices
		};
	} catch (err) {
		if (err instanceof ApiError) {
			if (err.status === 401) {
				cookies.delete('auth_token', { path: '/' });
				throw redirect(303, '/auth/login?clear_session=true');
			}
			throw error(err.status, err.message);
		}
		// If it's already a SvelteKit error (e.g. the 404 we threw above), re-throw it
		if (err && typeof err === 'object' && 'status' in err && 'body' in err) {
			throw err;
		}
		throw error(500, err instanceof Error ? err.message : 'Internal Server Error');
	}
};
