import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient, ApiError } from './apiClient';
import { currentTraceId, forgetCurrentTraceId, traceIdFromTraceparent } from './traceContext';

const TRACEPARENT_PATTERN = /^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$/;
const INBOUND_TRACEPARENT = '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01';

// Concrete implementation for testing
class TestClient extends ApiClient {
	async testGet() {
		return this.get('/test');
	}

	async testGetWithHeaders(headers: Record<string, string>) {
		return this.get('/test', headers);
	}

	async testPut(payload: { name: string }) {
		return this.put<{ success: boolean }, typeof payload>('/test', payload);
	}

	async testPost(payload: { name: string }) {
		return this.post<{ success: boolean }, typeof payload>('/test', payload);
	}

	async testPatch(payload: { name: string }) {
		return this.patch<{ success: boolean }, typeof payload>('/test', payload);
	}

	async testDelete() {
		return this.delete('/test');
	}

	async testPostFormData(formData: FormData) {
		return this.postFormData('/test', formData);
	}

	async testGetBlob() {
		return this.getBlob('/test');
	}
}

/** Headers of the most recent fetch call, as a plain record. */
function lastRequestHeaders(): Record<string, string> {
	const call = vi.mocked(global.fetch).mock.calls.at(-1);
	return (call?.[1]?.headers ?? {}) as Record<string, string>;
}

function okResponse(body: unknown = { success: true }): Response {
	return {
		ok: true,
		status: 200,
		headers: new Headers(),
		json: async () => body,
		blob: async () => new Blob()
	} as Response;
}

describe('ApiClient', () => {
	let client: TestClient;

	beforeEach(() => {
		vi.clearAllMocks();
		global.fetch = vi.fn();
		client = new TestClient();
	});

	it('should send PUT request correctly', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: true,
			status: 200,
			json: async () => ({ success: true })
		} as Response);

		const result = await client.testPut({ name: 'test' });
		expect(result).toEqual({ success: true });
		expect(global.fetch).toHaveBeenCalledWith(
			expect.stringContaining('/test'),
			expect.objectContaining({
				method: 'PUT',
				body: JSON.stringify({ name: 'test' })
			})
		);
	});

	it('should throw ApiError on 401', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 401,
			json: async () => ({ detail: 'Unauthorized' })
		} as Response);

		await expect(client.testGet()).rejects.toThrow(ApiError);
	});

	it('should throw ApiError on 404', async () => {
		vi.mocked(global.fetch).mockResolvedValue({
			ok: false,
			status: 404,
			json: async () => ({ detail: 'Not Found' })
		} as Response);

		await expect(client.testGet()).rejects.toThrow(ApiError);
	});

	describe('trace context propagation', () => {
		beforeEach(() => {
			vi.mocked(global.fetch).mockResolvedValue(okResponse());
		});

		it.each([
			['get', () => client.testGet()],
			['post', () => client.testPost({ name: 'test' })],
			['patch', () => client.testPatch({ name: 'test' })],
			['put', () => client.testPut({ name: 'test' })],
			['delete', () => client.testDelete()],
			['postFormData', () => client.testPostFormData(new FormData())],
			['getBlob', () => client.testGetBlob()]
		])('stamps a valid traceparent and matching X-Request-ID on %s', async (_verb, call) => {
			await call();

			const headers = lastRequestHeaders();
			expect(headers.traceparent).toMatch(TRACEPARENT_PATTERN);
			expect(headers['X-Request-ID']).toBe(traceIdFromTraceparent(headers.traceparent));
		});

		it('starts a fresh trace for each browser request', async () => {
			await client.testGet();
			const first = lastRequestHeaders().traceparent;

			await client.testGet();
			const second = lastRequestHeaders().traceparent;

			expect(first).toMatch(TRACEPARENT_PATTERN);
			expect(second).toMatch(TRACEPARENT_PATTERN);
			expect(traceIdFromTraceparent(first)).not.toBe(traceIdFromTraceparent(second));
		});

		it('continues the inbound trace context on SSR clients', async () => {
			const ssrClient = new TestClient(undefined, INBOUND_TRACEPARENT);
			await ssrClient.testGet();

			const headers = lastRequestHeaders();
			expect(headers.traceparent).toMatch(TRACEPARENT_PATTERN);
			expect(traceIdFromTraceparent(headers.traceparent)).toBe(
				traceIdFromTraceparent(INBOUND_TRACEPARENT)
			);
			expect(headers.traceparent).not.toBe(INBOUND_TRACEPARENT);
			expect(headers['X-Request-ID']).toBe(traceIdFromTraceparent(INBOUND_TRACEPARENT));
		});

		it('derives a distinct child span per SSR request under the same trace', async () => {
			const ssrClient = new TestClient(undefined, INBOUND_TRACEPARENT);
			await ssrClient.testGet();
			const first = lastRequestHeaders().traceparent;

			await ssrClient.testGet();
			const second = lastRequestHeaders().traceparent;

			expect(first).not.toBe(second);
			expect(traceIdFromTraceparent(first)).toBe(traceIdFromTraceparent(second));
		});

		it('replaces a malformed inbound traceparent instead of forwarding it', async () => {
			const ssrClient = new TestClient(undefined, 'not-a-traceparent');
			await ssrClient.testGet();

			const headers = lastRequestHeaders();
			expect(headers.traceparent).not.toBe('not-a-traceparent');
			expect(headers.traceparent).toMatch(TRACEPARENT_PATTERN);
		});

		it('lets caller-supplied headers override the generated trace context', async () => {
			await client.testGetWithHeaders({
				traceparent: INBOUND_TRACEPARENT,
				'X-Request-ID': 'custom'
			});

			const headers = lastRequestHeaders();
			expect(headers.traceparent).toBe(INBOUND_TRACEPARENT);
			expect(headers['X-Request-ID']).toBe('custom');
		});

		it('records the outgoing trace id as the current browser trace', async () => {
			forgetCurrentTraceId();

			await client.testGet();

			const headers = lastRequestHeaders();
			expect(currentTraceId()).toBe(traceIdFromTraceparent(headers.traceparent));
		});
	});

	describe('ApiError.requestId', () => {
		it('captures the response X-Request-ID header', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 500,
				headers: new Headers({ 'X-Request-ID': 'req-abc123' }),
				json: async () => ({ detail: 'Boom' })
			} as Response);

			const error = await client.testGet().catch((err: unknown) => err);
			expect(error).toBeInstanceOf(ApiError);
			expect((error as ApiError).requestId).toBe('req-abc123');
			expect((error as ApiError).message).toBe('Boom');
		});

		it('leaves requestId undefined when the header is absent', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 500,
				headers: new Headers(),
				json: async () => ({ detail: 'Boom' })
			} as Response);

			const error = await client.testGet().catch((err: unknown) => err);
			expect((error as ApiError).requestId).toBeUndefined();
		});

		it('leaves requestId undefined when the mocked response has no headers', async () => {
			vi.mocked(global.fetch).mockResolvedValue({
				ok: false,
				status: 500,
				json: async () => ({ detail: 'Boom' })
			} as Response);

			const error = await client.testGet().catch((err: unknown) => err);
			expect((error as ApiError).requestId).toBeUndefined();
		});
	});
});
