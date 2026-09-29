import type { ClientInit, HandleClientError } from '@sveltejs/kit';
import { installGlobalErrorHandlers, reportError } from '$lib/api/errorReporter';

/**
 * Installs the browser-wide error capture (unhandled errors and unhandled
 * promise rejections) once the app starts in the browser. Inert under vitest.
 */
export const init: ClientInit = () => {
	installGlobalErrorHandlers();
};

/**
 * SvelteKit client error hook: report client-side failures (load/render errors
 * that SvelteKit catches) to the shared error inbox. The returned `{ message }`
 * matches SvelteKit's default shape for `+error.svelte`.
 *
 * Deliberately does not toast: the failing call site already owns user feedback,
 * so toasting here would double-notify.
 */
export const handleError: HandleClientError = ({ error, message }) => {
	void reportError(error);

	return { message };
};
