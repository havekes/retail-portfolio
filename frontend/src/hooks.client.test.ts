import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/api/errorReporter', () => ({
	installGlobalErrorHandlers: vi.fn(),
	reportError: vi.fn()
}));

import { installGlobalErrorHandlers, reportError } from '$lib/api/errorReporter';
import { handleError, init } from './hooks.client';

describe('hooks.client', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('installs the global error capture on init', () => {
		init();

		expect(installGlobalErrorHandlers).toHaveBeenCalledTimes(1);
	});

	it('reports client-side errors and keeps the default message shape', () => {
		const error = new TypeError('Cannot read properties of undefined');

		const result = handleError({
			error,
			event: {} as never,
			status: 500,
			message: 'Cannot read properties of undefined'
		});

		expect(reportError).toHaveBeenCalledWith(error);
		expect(result).toEqual({ message: 'Cannot read properties of undefined' });
	});
});
