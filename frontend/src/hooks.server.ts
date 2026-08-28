import { redirect, type Handle } from '@sveltejs/kit';
import { jwtVerify } from 'jose';
import { JWT_SECRET } from '$env/static/private';
import { deleteAuthCookie } from '$lib/server/auth-cookie';

// Token verification uses the shared HS256 secret (JWT_SECRET). In a
// single-deployment architecture this is acceptable — the frontend server
// and backend run on the same infrastructure. If the architecture moves to
// separate deployments, migrate to RS256 (public key only) or a backend
// introspection endpoint. See ARCH-T09 for context.
// TODO: ARCH-T09
export const handle: Handle = async ({ event, resolve }) => {
	event.locals.user = null;

	const token = event.cookies.get('auth_token');

	if (token) {
		try {
			const secret = new TextEncoder().encode(JWT_SECRET);
			const { payload } = await jwtVerify(token, secret, { algorithms: ['HS256'] });
			// Reject non-access tokens (e.g. mfa_pending) — mirrors backend's
			// get_current_user_from_token scope check.
			if (payload.scope !== 'access') {
				deleteAuthCookie(event.cookies);
			} else {
				event.locals.user = {
					id: payload.user_id as string,
					email: payload.sub as string
				};
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
