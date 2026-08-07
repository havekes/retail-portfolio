import { dev } from '$app/environment';
import type { Cookies } from '@sveltejs/kit';

/**
 * Options for the `auth_token` cookie. Must stay in sync with the set
 * call in `frontend/src/routes/auth/login/+page.server.ts` — browsers only
 * honor a delete when the attributes (Path, HttpOnly, SameSite, Secure)
 * match the stored cookie.
 */
export const AUTH_COOKIE_OPTS = {
	path: '/',
	httpOnly: true,
	sameSite: 'lax',
	secure: !dev
} as const;

export function deleteAuthCookie(cookies: Cookies): void {
	cookies.delete('auth_token', AUTH_COOKIE_OPTS);
}
