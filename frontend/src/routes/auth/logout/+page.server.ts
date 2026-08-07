import { redirect, type Cookies } from '@sveltejs/kit';
import type { Actions } from './$types';
import { deleteAuthCookie, AUTH_COOKIE_OPTS } from '$lib/server/auth-cookie';

const logout = (cookies: Cookies) => {
	// Be very aggressive about deleting the cookie
	deleteAuthCookie(cookies);

	// Also set it to empty with immediate expiration just in case
	cookies.set('auth_token', '', {
		...AUTH_COOKIE_OPTS,
		expires: new Date(0)
	});
};

export const actions: Actions = {
	default: async ({ cookies }) => {
		logout(cookies);
		throw redirect(303, '/auth/login');
	}
};
