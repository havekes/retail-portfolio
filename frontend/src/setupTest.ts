import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

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
