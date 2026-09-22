import { goto } from '$app/navigation';
import { resolve } from '$app/paths';
import { ApiError } from '$lib/api/apiClient';

/**
 * Handle an error caught from an async (post-navigation) data load.
 *
 * Returns `true` when the error was handled, i.e. an `ApiError` with
 * `status === 401` navigated to `/auth/login?clear_session=true`, where
 * `hooks.server.ts` clears the surviving token. The httpOnly `auth_token`
 * cookie is NOT deleted client-side. The caller should stop and not render
 * its own error state when this returns `true`.
 *
 * Any other error returns `false`; the caller surfaces `err.message` in its
 * own in-page error alert.
 */
export async function redirectOn401(err: unknown): Promise<boolean> {
	if (err instanceof ApiError && err.status === 401) {
		await goto(resolve('/auth/login?clear_session=true'));
		return true;
	}

	return false;
}
