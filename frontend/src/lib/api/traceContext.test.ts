import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
	deployId,
	deriveChildTraceparent,
	extractTraceparent,
	generateTraceparent,
	isValidTraceparent,
	parseTraceparent,
	traceIdFromTraceparent
} from './traceContext';

const TRACEPARENT_PATTERN = /^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$/;

describe('traceContext', () => {
	describe('generateTraceparent', () => {
		it('generates a syntactically valid W3C traceparent', () => {
			const traceparent = generateTraceparent();
			expect(traceparent).toMatch(TRACEPARENT_PATTERN);
			expect(isValidTraceparent(traceparent)).toBe(true);
		});

		it('generates a fresh trace id and span id on every call', () => {
			const first = generateTraceparent();
			const second = generateTraceparent();

			expect(first).not.toBe(second);
			expect(traceIdFromTraceparent(first)).not.toBe(traceIdFromTraceparent(second));
		});

		it('reuses a supplied valid trace id while rotating the span id', () => {
			const traceId = '4bf92f3577b34da6a3ce929d0e0e4736';
			const first = generateTraceparent(traceId);
			const second = generateTraceparent(traceId);

			expect(traceIdFromTraceparent(first)).toBe(traceId);
			expect(traceIdFromTraceparent(second)).toBe(traceId);
			expect(parseTraceparent(first)?.spanId).not.toBe(parseTraceparent(second)?.spanId);
		});

		it('ignores a malformed or all-zero supplied trace id', () => {
			expect(traceIdFromTraceparent(generateTraceparent('not-a-trace-id'))).not.toBe(
				'not-a-trace-id'
			);
			expect(traceIdFromTraceparent(generateTraceparent('0'.repeat(32)))).not.toBe('0'.repeat(32));
		});

		it('derives deterministic ids from a mocked crypto source', () => {
			const getRandomValues = vi
				.spyOn(crypto, 'getRandomValues')
				.mockImplementation(<T extends ArrayBufferView | null>(array: T): T => {
					const view = array as unknown as Uint8Array;
					view.fill(0xab);
					return array;
				});

			try {
				expect(generateTraceparent()).toBe(`00-${'ab'.repeat(16)}-${'ab'.repeat(8)}-01`);
			} finally {
				getRandomValues.mockRestore();
			}
		});
	});

	describe('parseTraceparent / isValidTraceparent', () => {
		it('parses a valid value into its parts', () => {
			const value = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01';
			expect(parseTraceparent(value)).toEqual({
				traceId: '4bf92f3577b34da6a3ce929d0e0e4736',
				spanId: '00f067aa0ba902b7',
				flags: '01'
			});
		});

		it.each([
			['', 'empty string'],
			['not-a-traceparent', 'garbage'],
			['00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7', 'missing flags'],
			['01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01', 'unsupported version'],
			['00-4bf92f3577b34da6a3ce929d0e0e473-00f067aa0ba902b7-01', 'short trace id'],
			['00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902-01', 'short span id'],
			[`00-${'0'.repeat(32)}-00f067aa0ba902b7-01`, 'all-zero trace id'],
			[`00-4bf92f3577b34da6a3ce929d0e0e4736-${'0'.repeat(16)}-01`, 'all-zero span id']
		])('rejects %s (%s)', (value) => {
			expect(isValidTraceparent(value)).toBe(false);
			expect(parseTraceparent(value)).toBeUndefined();
		});

		it('handles undefined and null', () => {
			expect(isValidTraceparent(undefined)).toBe(false);
			expect(isValidTraceparent(null)).toBe(false);
			expect(parseTraceparent(null)).toBeUndefined();
		});
	});

	describe('deriveChildTraceparent', () => {
		it('keeps the inbound trace id and sampling flag but rotates the span id', () => {
			const inbound = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01';
			const child = deriveChildTraceparent(inbound);

			expect(child).toMatch(TRACEPARENT_PATTERN);
			expect(parseTraceparent(child)?.traceId).toBe('4bf92f3577b34da6a3ce929d0e0e4736');
			expect(parseTraceparent(child)?.flags).toBe('01');
			expect(parseTraceparent(child)?.spanId).not.toBe('00f067aa0ba902b7');
		});

		it('preserves a not-sampled flag from the inbound value', () => {
			const inbound = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-00';
			expect(parseTraceparent(deriveChildTraceparent(inbound))?.flags).toBe('00');
		});

		it('starts a fresh trace when the inbound value is missing or malformed', () => {
			const fromMissing = deriveChildTraceparent(undefined);
			const fromMalformed = deriveChildTraceparent('garbage');

			expect(fromMissing).toMatch(TRACEPARENT_PATTERN);
			expect(fromMalformed).toMatch(TRACEPARENT_PATTERN);
			expect(traceIdFromTraceparent(fromMalformed)).not.toBe('garbage');
		});
	});

	describe('extractTraceparent', () => {
		it('reads the header from a Headers instance', () => {
			const headers = new Headers({
				traceparent: '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
			});
			expect(extractTraceparent(headers)).toBe(
				'00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
			);
		});

		it('reads the header case-insensitively from a plain record', () => {
			expect(
				extractTraceparent({
					TraceParent: '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01'
				})
			).toBe('00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01');
		});

		it('returns undefined when the header is absent, empty, or headers are missing', () => {
			expect(extractTraceparent(new Headers())).toBeUndefined();
			expect(extractTraceparent({ traceparent: '   ' })).toBeUndefined();
			expect(extractTraceparent(undefined)).toBeUndefined();
			expect(extractTraceparent(null)).toBeUndefined();
		});
	});

	describe('deployId', () => {
		const originalEnv = import.meta.env.VITE_DEPLOY_ID;

		afterEach(() => {
			import.meta.env.VITE_DEPLOY_ID = originalEnv;
		});

		beforeEach(() => {
			vi.resetModules();
		});

		it('falls back to "dev" when VITE_DEPLOY_ID is unset, mirroring the backend default', async () => {
			delete import.meta.env.VITE_DEPLOY_ID;
			const fresh = await import('./traceContext');
			expect(fresh.deployId).toBe('dev');
		});

		it('uses VITE_DEPLOY_ID when provided', async () => {
			import.meta.env.VITE_DEPLOY_ID = 'deploy-abc123';
			const fresh = await import('./traceContext');
			expect(fresh.deployId).toBe('deploy-abc123');
		});

		it('is a non-empty string', () => {
			expect(typeof deployId).toBe('string');
			expect(deployId.length).toBeGreaterThan(0);
		});
	});
});
