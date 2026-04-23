import { redirect, type Handle } from '@sveltejs/kit';

function parseJwt(token: string) {
	try {
		const base64Url = token.split('.')[1];
		if (!base64Url) return null;
		const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
		const jsonPayload = Buffer.from(base64, 'base64').toString();
		return JSON.parse(jsonPayload);
	} catch (e) {
		return null;
	}
}

export const handle: Handle = async ({ event, resolve }) => {
	if (event.url.searchParams.get('clear_session') === 'true') {
		event.cookies.delete('auth_token', { path: '/' });
		event.locals.user = undefined;
	} else {
		const token = event.cookies.get('auth_token');

		if (token) {
			const payload = parseJwt(token);
			if (payload && payload.exp > Date.now() / 1000) {
				event.locals.user = {
					id: payload.user_id,
					email: payload.sub
				};
			} else {
				event.cookies.delete('auth_token', { path: '/' });
			}
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
