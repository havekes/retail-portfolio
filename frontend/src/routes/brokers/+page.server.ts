import { getBrokerService } from '$lib/components/brokers/brokerService.svelte';
import { deleteAuthCookie } from '$lib/server/auth-cookie';
import { error, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
	const brokerService = getBrokerService(fetch);
	const token = cookies.get('auth_token');
	try {
		const users = await brokerService.getBrokerUsers(token);
		return {
			users
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
