import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

vi.mock('$app/paths', () => ({
	resolve: (path: string) => path
}));

import { goto } from '$app/navigation';
import { ApiError } from '$lib/api/apiClient';
import { redirectOn401 } from './async-data';

describe('redirectOn401', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('redirects to login and reports handled when the error is a 401 ApiError', async () => {
		const handled = await redirectOn401(new ApiError(401, 'Unauthorized'));

		expect(handled).toBe(true);
		expect(goto).toHaveBeenCalledTimes(1);
		expect(goto).toHaveBeenCalledWith('/auth/login?clear_session=true');
	});

	it('does not redirect and reports unhandled for a non-401 ApiError', async () => {
		const handled = await redirectOn401(new ApiError(503, 'Service Unavailable'));

		expect(handled).toBe(false);
		expect(goto).not.toHaveBeenCalled();
	});

	it('does not redirect and reports unhandled for a plain Error', async () => {
		const handled = await redirectOn401(new Error('Network down'));

		expect(handled).toBe(false);
		expect(goto).not.toHaveBeenCalled();
	});

	it('does not redirect and reports unhandled for null', async () => {
		const handled = await redirectOn401(null);

		expect(handled).toBe(false);
		expect(goto).not.toHaveBeenCalled();
	});
});
