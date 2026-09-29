import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { ApiError } from './apiClient';
import {
	FRONTEND_ERROR_ENDPOINT,
	correlationIdFor,
	getErrorReportClient,
	installGlobalErrorHandlers,
	reportError,
	showToastForApiError,
	toExceptionPayload,
	trackGlobalErrors,
	type ErrorTransport,
	type FrontendExceptionPayload
} from './errorReporter';
import {
	forgetCurrentTraceId,
	rememberCurrentTraceId,
	traceIdFromTraceparent
} from './traceContext';
import { toast } from '$lib/components/ui/toast';

const TRACE_ID = '4bf92f3577b34da6a3ce929d0e0e4736';
const PAYLOAD_KEYS = ['name', 'message', 'stack', 'correlation_id', 'route'];

/** Dispatches an uncaught `window` error, as the browser would. */
function dispatchWindowError(error: unknown, message = 'boom') {
	const event = new ErrorEvent('error', { error, message });
	window.dispatchEvent(event);
}

/** Dispatches an unhandled rejection, as the browser would. */
function dispatchUnhandledRejection(reason: unknown) {
	const event = new Event('unhandledrejection') as Event & {
		reason?: unknown;
		promise?: Promise<unknown>;
	};
	Object.defineProperty(event, 'reason', { value: reason });
	Object.defineProperty(event, 'promise', { value: Promise.resolve() });
	window.dispatchEvent(event);
}

describe('errorReporter', () => {
	let transport: Mock<ErrorTransport>;
	let disposers: (() => void)[];

	beforeEach(() => {
		transport = vi.fn<ErrorTransport>().mockResolvedValue(undefined);
		disposers = [];
		forgetCurrentTraceId();
		toast.clear();
	});

	afterEach(() => {
		for (const dispose of disposers) dispose();
		vi.restoreAllMocks();
		toast.clear();
		forgetCurrentTraceId();
	});

	describe('toExceptionPayload', () => {
		it('keeps only the whitelisted fields', () => {
			const payload = toExceptionPayload(new TypeError('Cannot read properties of null'));

			expect(payload.name).toBe('TypeError');
			expect(payload.message).toBe('Cannot read properties of null');
			expect(payload.route).toBe('/');
			expect(Object.keys(payload).every((key) => PAYLOAD_KEYS.includes(key))).toBe(true);
		});

		it('never carries credentials or form values from a thrown object', () => {
			const thrown = {
				message: 'Request failed',
				token: 'secret-token-value',
				authorization: 'Bearer secret-token-value',
				password: 'hunter2',
				formData: { email: 'operator@example.com' }
			};

			const payload = toExceptionPayload(thrown);
			const serialised = JSON.stringify(payload);

			expect(Object.keys(payload).every((key) => PAYLOAD_KEYS.includes(key))).toBe(true);
			for (const secret of [
				'secret-token-value',
				'hunter2',
				'operator@example.com',
				'authorization',
				'password',
				'formData'
			]) {
				expect(serialised).not.toContain(secret);
			}
		});

		it('caps the message length and the stack to the first lines', () => {
			const error = new Error('m'.repeat(600));
			error.stack = Array.from({ length: 60 }, (_, index) => `at frame-${index}`).join('\n');

			const payload = toExceptionPayload(error);

			expect(payload.message).toHaveLength(500);
			expect(payload.stack?.split('\n')).toHaveLength(30);
			expect(payload.stack).toContain('frame-0');
			expect(payload.stack).not.toContain('frame-40');
		});

		it('drops malformed correlation ids and routes', () => {
			const payload = toExceptionPayload(new Error('x'), {
				correlationId: 'not-a-trace-id',
				route: 'https://evil.example.com/steal?token=abc'
			});

			expect(payload.correlation_id).toBeUndefined();
			expect(payload.route).toBe('/');
		});
	});

	describe('correlation ids', () => {
		it('uses the ApiError request id when present', () => {
			const error = new ApiError(500, 'Boom', undefined, TRACE_ID);

			expect(correlationIdFor(error)).toBe(TRACE_ID);
			expect(toExceptionPayload(error).correlation_id).toBe(TRACE_ID);
		});

		it('falls back to the current browser trace id for non-API errors', () => {
			rememberCurrentTraceId(TRACE_ID.toUpperCase());

			expect(toExceptionPayload(new TypeError('boom')).correlation_id).toBe(TRACE_ID);
		});

		it('has no correlation id when nothing has been recorded', () => {
			expect(correlationIdFor(new TypeError('boom'))).toBeUndefined();
			expect(toExceptionPayload(new TypeError('boom')).correlation_id).toBeUndefined();
		});
	});

	describe('global capture', () => {
		it('reports an uncaught window error exactly once with route and correlation id', async () => {
			rememberCurrentTraceId(TRACE_ID);
			disposers.push(
				trackGlobalErrors((error, context) => void reportError(error, context, transport))
			);

			dispatchWindowError(new TypeError('render failed'));
			await vi.waitFor(() => expect(transport).toHaveBeenCalledTimes(1));

			const payload = transport.mock.calls[0][0] as FrontendExceptionPayload;
			expect(payload.name).toBe('TypeError');
			expect(payload.message).toBe('render failed');
			expect(payload.correlation_id).toBe(TRACE_ID);
			expect(payload.route).toBe('/');
		});

		it('reports an unhandled promise rejection exactly once', async () => {
			disposers.push(
				trackGlobalErrors((error, context) => void reportError(error, context, transport))
			);

			dispatchUnhandledRejection(new ApiError(502, 'Bad gateway', undefined, TRACE_ID));
			await vi.waitFor(() => expect(transport).toHaveBeenCalledTimes(1));

			const payload = transport.mock.calls[0][0] as FrontendExceptionPayload;
			expect(payload.name).toBe('ApiError');
			expect(payload.message).toBe('Bad gateway');
			expect(payload.correlation_id).toBe(TRACE_ID);
		});

		it('is idempotent per reporter and stops reporting once disposed', async () => {
			const reporter = vi.fn();
			const first = trackGlobalErrors(reporter);
			const second = trackGlobalErrors(reporter);
			disposers.push(first);

			expect(second).toBe(first);

			dispatchWindowError(new TypeError('once'));
			dispatchUnhandledRejection(new Error('once'));

			expect(reporter).toHaveBeenCalledTimes(2);

			first();
			dispatchWindowError(new TypeError('after dispose'));
			expect(reporter).toHaveBeenCalledTimes(2);
		});

		it('uses the injected transport, never fetch', async () => {
			const fetchSpy = vi.spyOn(global, 'fetch');
			disposers.push(
				trackGlobalErrors((error, context) => void reportError(error, context, transport))
			);

			dispatchWindowError(new Error('offline'));

			await vi.waitFor(() => expect(transport).toHaveBeenCalledTimes(1));
			expect(fetchSpy).not.toHaveBeenCalled();
		});
	});

	describe('transport safety', () => {
		it('does nothing when the transport is not installed', async () => {
			const fetchSpy = vi.spyOn(global, 'fetch');

			await expect(reportError(new Error('boom'), {}, null)).resolves.toBeUndefined();

			expect(fetchSpy).not.toHaveBeenCalled();
		});

		it('swallows transport failures', async () => {
			const failing = vi.fn<ErrorTransport>().mockRejectedValue(new Error('offline'));

			await expect(reportError(new Error('boom'), {}, failing)).resolves.toBeUndefined();
		});

		it('is inert by default under vitest so no test dials the backend', async () => {
			const fetchSpy = vi.spyOn(global, 'fetch');

			await reportError(new Error('boom'));

			expect(fetchSpy).not.toHaveBeenCalled();
		});

		it('does not install window handlers under vitest', () => {
			const addSpy = vi.spyOn(window, 'addEventListener');

			const dispose = installGlobalErrorHandlers();

			expect(addSpy).not.toHaveBeenCalled();
			dispose();
		});

		it('reports through the API client endpoint path when one is installed', () => {
			expect(FRONTEND_ERROR_ENDPOINT).toBe('/observability/exceptions');
		});

		it('POSTs the report to the error inbox with the same trace headers as any call', async () => {
			const fetchMock = vi.fn().mockResolvedValue({
				ok: true,
				status: 204,
				headers: new Headers()
			});
			const client = getErrorReportClient(fetchMock as unknown as typeof fetch);

			await client.report({ name: 'TypeError', message: 'boom', route: '/' });

			expect(fetchMock).toHaveBeenCalledTimes(1);
			const [url, init] = fetchMock.mock.calls[0];
			expect(String(url)).toContain(FRONTEND_ERROR_ENDPOINT);
			expect(init?.method).toBe('POST');
			expect(JSON.parse(String(init?.body))).toEqual({
				name: 'TypeError',
				message: 'boom',
				route: '/'
			});

			const headers = init?.headers as Record<string, string>;
			expect(headers.traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$/);
			expect(headers['X-Request-ID']).toBe(traceIdFromTraceparent(headers.traceparent));
		});
	});

	describe('showToastForApiError', () => {
		it('surfaces the ApiError correlation id in the toast', () => {
			const errorSpy = vi.spyOn(toast, 'error');
			const error = new ApiError(500, 'Boom', undefined, TRACE_ID);

			showToastForApiError(error, 'Failed to delete account. Please try again.');

			expect(errorSpy).toHaveBeenCalledWith('Failed to delete account. Please try again.', {
				correlationId: TRACE_ID
			});
		});

		it('shows the fallback message without a correlation id when none is known', () => {
			const errorSpy = vi.spyOn(toast, 'error');

			showToastForApiError(new Error('Network error'), 'Failed to save chart snapshot');

			expect(errorSpy).toHaveBeenCalledWith('Failed to save chart snapshot');
		});
	});
});
