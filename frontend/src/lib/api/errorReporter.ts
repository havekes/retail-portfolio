/**
 * Browser error reporting into the shared observability error inbox (F-OBS-T19).
 *
 * Unhandled `window` errors, unhandled promise rejections and SvelteKit
 * `handleError` failures are POSTed to
 * `/api/v1/observability/exceptions`, where the backend funnels them through the
 * same `capture_exception` sink as backend and worker failures (F-OBS-T17) with
 * `service_name="frontend"`. The records therefore land in the same HyperDX
 * error inbox and inherit the backend `deploy_id`/`release` tags.
 *
 * The payload is an explicit whitelist (error name, message, first stack lines,
 * correlation id, pathname) — never form values, storage contents or raw request
 * data. Reporting is best effort: it must never throw into application code or
 * mask the original failure.
 *
 * Test conventions (frontend `AGENTS.md`): tests never touch the network. They
 * inject a mock `ErrorTransport` into `reportError`/`trackGlobalErrors`, and
 * `installGlobalErrorHandlers()` is a no-op under vitest so stray jsdom errors
 * cannot produce reports.
 */

import { browser } from '$app/environment';
import { ApiClient, ApiError } from './apiClient';
import { currentTraceId } from './traceContext';
import { toast } from '$lib/components/ui/toast';

/** Endpoint appended to the `ApiClient` base URL (`/api/v1`). */
export const FRONTEND_ERROR_ENDPOINT = '/observability/exceptions';

/** Bounds mirrored by the backend `FrontendExceptionRequest` model. */
const MAX_NAME_LENGTH = 100;
const MAX_MESSAGE_LENGTH = 500;
const MAX_STACK_LINES = 30;
const MAX_STACK_LENGTH = 4000;
const MAX_ROUTE_LENGTH = 300;

const SAFE_ERROR_NAME_PATTERN = /^[A-Za-z0-9_.]{1,100}$/;
const SAFE_ROUTE_PATTERN = /^\/[^\s?#]*$/;
const TRACE_ID_PATTERN = /^[0-9a-f]{32}$/;

export interface FrontendExceptionPayload {
	name: string;
	message: string;
	stack?: string;
	correlation_id?: string;
	route?: string;
}

/** Extra correlation context for a report. */
export interface ErrorContext {
	/** Explicit correlation id; falls back to the error/registry trace id. */
	correlationId?: string;
	/** Explicit route; falls back to `location.pathname`. */
	route?: string;
}

/** Sends one sanitised report. Injected in tests to avoid real network calls. */
export type ErrorTransport = (payload: FrontendExceptionPayload) => Promise<unknown>;

/** Reporter invoked for every captured browser error. */
export type ErrorReporter = (error: unknown, context?: ErrorContext) => void;

/**
 * `ApiClient` subclass used for reports, so they carry the same
 * `traceparent`/`X-Request-ID` headers and cookie credentials as any other call.
 */
export class ErrorReportClient extends ApiClient {
	async report(payload: FrontendExceptionPayload): Promise<void> {
		const response = await this.fetch(`${this.baseUrl}${FRONTEND_ERROR_ENDPOINT}`, {
			method: 'POST',
			credentials: 'include',
			headers: this.buildHeaders(undefined, undefined, { json: true }),
			body: JSON.stringify(payload)
		});

		if (!response.ok) {
			throw new Error(`Error report rejected with status ${response.status}`);
		}
	}
}

export const errorReportClient = new ErrorReportClient();

/** Creates a report client, optionally with a custom `fetch` (tests). */
export const getErrorReportClient = (customFetch?: typeof fetch) =>
	new ErrorReportClient(customFetch);

/** Default transport: POST through the API client (browser only). */
export const httpErrorTransport: ErrorTransport = (payload) => errorReportClient.report(payload);

/**
 * Transport used when none is injected.
 *
 * Disabled under vitest: tests must never emit reports over the network, so they
 * exercise the reporter with an explicit mock transport instead. Combined with
 * `installGlobalErrorHandlers()` being inert under vitest, no test can
 * accidentally dial the backend.
 */
const defaultTransport: ErrorTransport | null =
	import.meta.env.MODE === 'test' ? null : httpErrorTransport;

function truncate(value: string, max: number): string {
	return value.length > max ? value.slice(0, max) : value;
}

/** Screens an error class name; anything unexpected degrades to `Error`. */
function safeErrorName(value: unknown): string {
	const candidate = typeof value === 'string' ? truncate(value.trim(), MAX_NAME_LENGTH) : '';
	return SAFE_ERROR_NAME_PATTERN.test(candidate) ? candidate : 'Error';
}

/** Keeps only a pathname: no query string, hash or absolute URL. */
function safeRoute(value: unknown): string | undefined {
	if (typeof value !== 'string') return undefined;

	const candidate = value.trim();
	if (!candidate || candidate.length > MAX_ROUTE_LENGTH) return undefined;

	return SAFE_ROUTE_PATTERN.test(candidate) ? candidate : undefined;
}

/** Accepts a 32-hex (or dashed UUID) trace id, normalised to lowercase hex. */
function safeCorrelationId(value: unknown): string | undefined {
	if (typeof value !== 'string') return undefined;

	const candidate = value.trim().toLowerCase().replace(/-/g, '');
	return TRACE_ID_PATTERN.test(candidate) ? candidate : undefined;
}

function currentRoute(): string | undefined {
	if (!browser || typeof location === 'undefined') return undefined;
	return safeRoute(location.pathname);
}

function firstStackLines(stack: string): string | undefined {
	const lines = stack.split('\n').slice(0, MAX_STACK_LINES).join('\n').trim();
	if (!lines) return undefined;
	return truncate(lines, MAX_STACK_LENGTH);
}

/** Correlation id for an error: the API request id, else the current trace id. */
export function correlationIdFor(error: unknown): string | undefined {
	if (error instanceof ApiError && error.requestId) {
		const requestId = safeCorrelationId(error.requestId);
		if (requestId) return requestId;
	}
	return safeCorrelationId(currentTraceId());
}

/**
 * Builds the whitelisted report payload for an error. Nothing outside the
 * listed fields is ever included, so credentials and user input cannot leak.
 */
export function toExceptionPayload(
	error: unknown,
	context: ErrorContext = {}
): FrontendExceptionPayload {
	const message = truncate(
		error instanceof Error ? error.message : String(error ?? ''),
		MAX_MESSAGE_LENGTH
	);
	const stack =
		error instanceof Error && typeof error.stack === 'string'
			? firstStackLines(error.stack)
			: undefined;
	const correlationId = safeCorrelationId(context.correlationId) ?? correlationIdFor(error);
	const route = safeRoute(context.route) ?? currentRoute();

	const payload: FrontendExceptionPayload = {
		name: safeErrorName(error instanceof Error ? error.name : undefined),
		message
	};

	if (stack) payload.stack = stack;
	if (correlationId) payload.correlation_id = correlationId;
	if (route) payload.route = route;

	return payload;
}

/**
 * Reports one error. Best effort by design: transport failures are swallowed so
 * error reporting can never break the UI or mask the original failure. A `null`
 * transport disables reporting (used by tests).
 */
export async function reportError(
	error: unknown,
	context: ErrorContext = {},
	transport: ErrorTransport | null = defaultTransport
): Promise<void> {
	if (!browser || !transport) return;

	try {
		await transport(toExceptionPayload(error, context));
	} catch {
		// Reporting is telemetry: never surface transport failures to the user.
	}
}

/** Installed reporters, keyed by the reporter that owns the listeners. */
const installedReporters = new Map<ErrorReporter, () => void>();

/**
 * Wires `window` error + unhandled rejection capture to `reporter`, returning a
 * disposer. Idempotent per reporter instance: a second call returns the existing
 * disposer instead of installing duplicate listeners (which would double report).
 *
 * `addEventListener('error')` is used instead of `window.onerror` because both
 * fire for the same uncaught error and would produce two reports.
 */
export function trackGlobalErrors(reporter: ErrorReporter = reportError): () => void {
	if (!browser) return () => {};

	const existing = installedReporters.get(reporter);
	if (existing) return existing;

	const onError = (event: ErrorEvent) => {
		reporter(event.error ?? event.message, { route: currentRoute() });
	};
	const onUnhandledRejection = (event: PromiseRejectionEvent) => {
		reporter(event.reason, { route: currentRoute() });
	};

	window.addEventListener('error', onError);
	window.addEventListener('unhandledrejection', onUnhandledRejection);

	const dispose = () => {
		window.removeEventListener('error', onError);
		window.removeEventListener('unhandledrejection', onUnhandledRejection);
		installedReporters.delete(reporter);
	};

	installedReporters.set(reporter, dispose);
	return dispose;
}

/**
 * Installs the global capture used by `hooks.client.ts`.
 *
 * Deliberately inert under vitest (`import.meta.env.MODE === 'test'`) and during
 * SSR: stray jsdom errors must not turn into reports or real network calls.
 */
export function installGlobalErrorHandlers(): () => void {
	if (!browser || import.meta.env.MODE === 'test') return () => {};
	return trackGlobalErrors();
}

/**
 * Minimal toast surface needed for error feedback. Compatible with `ToastState`.
 */
export interface ErrorToastTarget {
	error: (message: string, options?: { correlationId?: string }) => unknown;
}

/**
 * Shows the standard error toast for a failed call and reports the failure.
 *
 * For an `ApiError` the backend correlation id (`ApiError.requestId`, F-OBS-T18)
 * is rendered in the toast so support can paste it straight into HyperDX; for
 * anything else the last browser trace id is used as context. The caller keeps
 * ownership of the user-facing message.
 */
export function showToastForApiError(
	error: unknown,
	fallbackMessage: string,
	target: ErrorToastTarget = toast
): unknown {
	const correlationId = correlationIdFor(error);

	void reportError(error, { correlationId });

	return correlationId
		? target.error(fallbackMessage, { correlationId })
		: target.error(fallbackMessage);
}
