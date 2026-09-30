/**
 * W3C Trace Context helpers for frontend-originated requests.
 *
 * The backend extracts an inbound `traceparent` with OpenTelemetry's propagator
 * (see `src/core/middleware.py`) and returns `X-Request-ID` on every response,
 * preferring the inbound header over the active trace id. To join backend
 * traces, every request we send carries a syntactically valid `traceparent`
 * (`00-<32 hex trace id>-<16 hex span id>-<2 hex flags>`) plus an
 * `X-Request-ID` equal to that trace id.
 *
 * Deliberately dependency-free: no `@opentelemetry/api` in the browser bundle.
 */

/** `00-<32 hex trace id>-<16 hex span id>-<2 hex flags>` (version `00` only). */
const TRACEPARENT_PATTERN = /^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$/;
const TRACE_ID_PATTERN = /^[0-9a-f]{32}$/;
const ZERO_TRACE_ID = '0'.repeat(32);
const ZERO_SPAN_ID = '0'.repeat(16);

/** Sampling flag used for traces this client roots (W3C `01` = sampled). */
const DEFAULT_FLAGS = '01';

export interface TraceparentParts {
	traceId: string;
	spanId: string;
	flags: string;
}

/**
 * Generates `byteLength` random bytes as lowercase hex.
 *
 * Falls back to `Math.random` in non-secure contexts (LAN IP / older browsers)
 * where `crypto.getRandomValues` is unavailable — same guard as
 * `generateUUID()` in `$lib/utils/finance/rewind.ts`.
 */
function randomHex(byteLength: number): string {
	const bytes = new Uint8Array(byteLength);

	if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
		crypto.getRandomValues(bytes);
	} else {
		for (let i = 0; i < bytes.length; i++) {
			bytes[i] = Math.floor(Math.random() * 256);
		}
	}

	return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Parses a `traceparent` value, returning its parts when it is a valid W3C
 * trace context (all-zero trace/span ids are invalid by spec).
 */
export function parseTraceparent(value?: string | null): TraceparentParts | undefined {
	if (!value) return undefined;

	const match = TRACEPARENT_PATTERN.exec(value.trim().toLowerCase());
	if (!match) return undefined;

	const traceId = match[1];
	const spanId = match[2];
	const flags = match[3];

	if (traceId === ZERO_TRACE_ID || spanId === ZERO_SPAN_ID) return undefined;

	return { traceId, spanId, flags };
}

/** Returns true when `value` is a syntactically valid W3C `traceparent`. */
export function isValidTraceparent(value?: string | null): boolean {
	return parseTraceparent(value) !== undefined;
}

/**
 * Builds a new `traceparent`, starting a fresh trace.
 */
export function generateTraceparent(): string {
	const traceId = randomHex(16);

	return `00-${traceId}-${randomHex(8)}-${DEFAULT_FLAGS}`;
}

/**
 * Derives a child `traceparent` from an inbound one: the trace id (and the
 * sampling flag) are kept, the span id is rotated. Falls back to a fresh trace
 * when the inbound value is missing or malformed, so a bad header never
 * prevents a request from being traced.
 */
export function deriveChildTraceparent(inbound?: string | null): string {
	const parent = parseTraceparent(inbound);
	if (!parent) return generateTraceparent();

	return `00-${parent.traceId}-${randomHex(8)}-${parent.flags}`;
}

/**
 * Reads the `traceparent` header from a `Headers` instance or a plain header
 * record (case-insensitively), returning `undefined` when absent.
 */
export function extractTraceparent(
	headersLike?: Headers | Record<string, string | undefined> | null
): string | undefined {
	if (!headersLike) return undefined;

	if (typeof (headersLike as Headers).get === 'function') {
		return (headersLike as Headers).get('traceparent')?.trim() || undefined;
	}

	for (const [key, value] of Object.entries(headersLike)) {
		if (key.toLowerCase() !== 'traceparent') continue;
		if (typeof value === 'string' && value.trim()) return value.trim();
	}

	return undefined;
}

/** The trace id carried by a valid `traceparent`, or `undefined`. */
export function traceIdFromTraceparent(traceparent?: string | null): string | undefined {
	return parseTraceparent(traceparent)?.traceId;
}

/**
 * Deployment identifier used to tag frontend errors/traces, mirroring the
 * backend's `DEPLOY_ID` (`src/config/settings.py`, default `dev`). Evaluated at
 * build/dev-server start, so changing the compose env needs a service restart.
 */
export const deployId: string = import.meta.env.VITE_DEPLOY_ID || 'dev';

/**
 * Browser-only registry of the trace id of the most recent outgoing request.
 *
 * `ApiClient.buildHeaders` records the trace it just stamped on a request so a
 * later failure that is *not* an `ApiError` (an unhandled `TypeError`, say) can
 * still be correlated to the request that preceded it. It holds a single
 * client-side value and must never be written during SSR — module state is
 * shared across requests on the server (see frontend `AGENTS.md`, Gotcha 3).
 */
let lastBrowserTraceId: string | undefined;

/**
 * Records the trace id of the most recent browser request. No-op for anything
 * that is not a valid, non-zero 32-hex trace id. Call from the browser only.
 */
export function rememberCurrentTraceId(traceId?: string | null): void {
	if (!traceId) return;

	const candidate = traceId.trim().toLowerCase();
	if (!TRACE_ID_PATTERN.test(candidate) || candidate === ZERO_TRACE_ID) return;

	lastBrowserTraceId = candidate;
}

/** The last browser-request trace id, or `undefined` when none was seen yet. */
export function currentTraceId(): string | undefined {
	return lastBrowserTraceId;
}

/** Clears the registry (used by tests to avoid leaking state between cases). */
export function forgetCurrentTraceId(): void {
	lastBrowserTraceId = undefined;
}
