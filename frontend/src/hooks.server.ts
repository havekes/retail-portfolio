import { redirect, type Handle } from '@sveltejs/kit';
import { jwtVerify } from 'jose';
import { JWT_SECRET } from '$env/static/private';

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
				event.cookies.delete('auth_token', { path: '/' });
			}
		} catch {
			event.cookies.delete('auth_token', { path: '/' });
		}
	}

	const isAuthRoute = event.url.pathname.startsWith('/auth');

	if (!event.locals.user && !isAuthRoute) {
		throw redirect(303, '/auth/login');
	}

	if (
		event.locals.user &&
		(event.url.pathname === '/auth/login' || event.url.pathname === '/auth/signup')
	) {
		throw redirect(303, '/');
	}

	return resolve(event);
};
