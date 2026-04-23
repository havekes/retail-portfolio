import { redirect } from '@sveltejs/kit';
import type { PageServerLoad, Actions } from './$types';

const logout = (cookies: any) => {
	// Be very aggressive about deleting the cookie
	cookies.delete('auth_token', { path: '/' });

	// Also set it to empty with immediate expiration just in case
	cookies.set('auth_token', '', {
		path: '/',
		expires: new Date(0),
		httpOnly: true,
		sameSite: 'lax',
		secure: false
	});
};

export const load: PageServerLoad = async ({ cookies }) => {
	logout(cookies);
	throw redirect(303, '/auth/login');
};

export const actions: Actions = {
	default: async ({ cookies }) => {
		logout(cookies);
		throw redirect(303, '/auth/login');
	}
};
