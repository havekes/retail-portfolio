import { getAccountClient } from '$lib/api/accountClient';
import { error, fail, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { PageServerLoad, Actions } from './$types';

export const load: PageServerLoad = async ({ params, cookies, fetch }) => {
	const token = cookies.get('auth_token');
	const accountClient = getAccountClient(fetch);

	try {
		const holdings = await accountClient.getAccountHoldings(params.id, token);
		return {
			holdings
		};
	} catch (err) {
		if (err instanceof ApiError) {
			if (err.status === 401) {
				cookies.delete('auth_token', { path: '/' });
				throw redirect(303, '/auth/login?clear_session=true');
			}
			throw error(err.status, err.message);
		}
		throw error(500, 'Internal Server Error');
	}
};

export const actions: Actions = {
	renameAccount: async ({ params, request, fetch }) => {
		const data = await request.formData();
		const name = data.get('name');

		if (typeof name !== 'string' || !name) {
			return fail(400, { message: 'Name is required' });
		}

		const accountClient = getAccountClient(fetch);
		try {
			await accountClient.renameAccount(params.id, name);
		} catch (err) {
			if (err instanceof ApiError) {
				return fail(err.status, { message: err.message });
			}
			return fail(500, { message: 'Failed to rename account' });
		}

		return { success: true };
	}
};
