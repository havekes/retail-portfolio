import '@testing-library/jest-dom/vitest';
import { afterAll, vi } from 'vitest';

// bits-ui's dismissible-layer (used by Dialog, Popover, etc.) schedules
// `afterSleep` timers that read derived state after the layer's effects have
// been destroyed (e.g. when a dialog closes and its content unmounts). In jsdom
// tests this fires svelte's DEV-only "derived_inert" warning. It is library-
// internal noise — there is no app code that can prevent it — so drop just that
// specific warning while forwarding everything else.
const originalWarn = console.warn;
vi.spyOn(console, 'warn').mockImplementation((...args: unknown[]) => {
	const message = typeof args[0] === 'string' ? args[0] : '';
	if (message.includes('derived_inert')) {
		return;
	}
	originalWarn(...args);
});

// bits-ui's body-scroll-lock (used by Dialog.Content) schedules a short
// `setTimeout` (~24ms) to restore the body style when the last lock is released
// on unmount. If the timer is still pending when vitest tears down the jsdom
// environment, its callback throws `ReferenceError: document is not defined`
// and vitest fails the run. This is a race that shows up on slow CI machines.
// Waiting in afterAll (after testing-library's cleanup unmounted everything,
// but before the environment is destroyed) lets the timer fire safely.
afterAll(() => {
	return new Promise((resolve) => setTimeout(resolve, 50));
});

// Mock window.location
if (typeof window !== 'undefined') {
	const url = new URL('http://localhost/');
	vi.stubGlobal('location', {
		href: url.href,
		origin: url.origin,
		protocol: url.protocol,
		host: url.host,
		hostname: url.hostname,
		port: url.port,
		pathname: url.pathname,
		search: url.search,
		hash: url.hash,
		assign: vi.fn(),
		replace: vi.fn(),
		reload: vi.fn(),
		toString: () => url.href
	});
}
