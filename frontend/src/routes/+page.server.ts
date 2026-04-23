import { getAccountClient } from '$lib/api/accountClient';
import { error, fail, redirect } from '@sveltejs/kit';
import { ApiError } from '$lib/api/apiClient';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, cookies }) => {
	const accountClient = getAccountClient(fetch);
	const token = cookies.get('auth_token');
	try {
		const accounts = await accountClient.getAccounts(token);
		return {
			accounts
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
	renameAccount: async ({ request, fetch }) => {
		const data = await request.formData();
		const name = data.get('name');
		const id = data.get('id'); // We need the id if we are on the home page

		if (typeof name !== 'string' || !name) {
			return fail(400, { message: 'Name is required' });
		}
		
		if (typeof id !== 'string' || !id) {
			return fail(400, { message: 'Account ID is required' });
		}

		const accountClient = getAccountClient(fetch);
		try {
			await accountClient.renameAccount(id, name);
		} catch (err: any) {
			return fail(err.status || 500, { message: err.message || 'Failed to rename account' });
		}

		return { success: true };
	}
};
