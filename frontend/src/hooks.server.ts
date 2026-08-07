import { redirect, type Handle } from '@sveltejs/kit';
import { jwtVerify } from 'jose';
import { JWT_SECRET } from '$env/static/private';
import { deleteAuthCookie } from '$lib/server/auth-cookie';

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.user = null;

	const token = event.cookies.get('auth_token');

	if (token) {
		try {
			const secret = new TextEncoder().encode(JWT_SECRET);
			const { payload } = await jwtVerify(token, secret, { algorithms: ['HS256'] });
			if (payload.exp && payload.exp > Date.now() / 1000) {
				event.locals.user = {
					id: payload.user_id as string,
					email: payload.sub as string
				};
			} else {
				deleteAuthCookie(event.cookies);
			}
		} catch {
			deleteAuthCookie(event.cookies);
		}
	}

	const isAuthRoute = event.url.pathname.startsWith('/auth');

	if (!event.locals.user && !isAuthRoute) {
		throw redirect(303, '/auth/login');
	}

	// If the session was just cleared (a dead token redirected here with
	// clear_session=true), drop any surviving token and render the login page
	// instead of bouncing an "authenticated" visitor straight back to '/'
	// (which previously caused a redirect loop when the stale cookie survived).
	if (
		event.url.searchParams.get('clear_session') === 'true' &&
		(event.url.pathname === '/auth/login' || event.url.pathname === '/auth/signup')
	) {
		deleteAuthCookie(event.cookies);
		event.locals.user = null;
		return resolve(event);
	}

	if (
		event.locals.user &&
		(event.url.pathname === '/auth/login' || event.url.pathname === '/auth/signup')
	) {
		throw redirect(303, '/');
	}

	return resolve(event);
};
