import { browser } from '$app/environment';
import {
	deriveChildTraceparent,
	generateTraceparent,
	traceIdFromTraceparent
} from './traceContext';

export class ApiError extends Error {
	constructor(
		public status: number,
		public message: string,
		public response?: Response,
		/** Correlation id from the response `X-Request-ID` header, when present. */
		public requestId?: string
	) {
		super(message);
		this.name = 'ApiError';
	}
}

export abstract class ApiClient {
	protected baseUrl: string;
	protected fetch: typeof fetch;
	/** Inbound page-request `traceparent` to continue from (SSR only). */
	protected inboundTraceparent?: string;

	constructor(customFetch?: typeof fetch, inboundTraceparent?: string | null) {
		const base = browser
			? import.meta.env.VITE_API_BASE_URL || ''
			: (import.meta.env.VITE_INTERNAL_API_URL ?? import.meta.env.VITE_API_BASE_URL ?? '');
		this.baseUrl = (base.endsWith('/') ? base.slice(0, -1) : base) + '/api/v1';
		this.fetch = customFetch || fetch;
		this.inboundTraceparent = inboundTraceparent ?? undefined;
	}

	/**
	 * Merges default, auth, and trace-context headers for one outgoing request.
	 *
	 * Every request carries a valid W3C `traceparent` plus an `X-Request-ID`
	 * holding the same trace id, so the backend ties its request id to the trace
	 * (`src/core/middleware.py` prefers the inbound request id over the active
	 * trace id). SSR clients continue the inbound page-request trace by deriving
	 * a child span per call; browser requests start a fresh trace. Explicit
	 * caller-supplied `headers` win over the defaults.
	 */
	protected buildHeaders(
		headers?: Record<string, string>,
		tokenOverride?: string | null,
		options?: { json?: boolean }
	): Record<string, string> {
		const traceparent = this.inboundTraceparent
			? deriveChildTraceparent(this.inboundTraceparent)
			: generateTraceparent();

		return {
			...(options?.json ? { 'Content-Type': 'application/json' } : {}),
			...(tokenOverride ? { Authorization: `Bearer ${tokenOverride}` } : {}),
			traceparent,
			'X-Request-ID': traceIdFromTraceparent(traceparent) ?? traceparent,
			...headers
		};
	}

	private async extractErrorMessage(response: Response): Promise<string> {
		const fallback = `Request failed with status ${response.status}`;

		try {
			const data = await response.json();
			if (data && data.detail) return String(data.detail);
			if (data && data.message) return String(data.message);
		} catch {
			// Response body is not JSON or is empty
		}
		return fallback;
	}

	private async handleResponse(response: Response): Promise<void> {
		if (!response.ok) {
			const message = await this.extractErrorMessage(response);
			const requestId = response.headers?.get('X-Request-ID')?.trim() || undefined;
			throw new ApiError(response.status, message, response, requestId);
		}
	}

	protected async get<T>(
		endpoint: string,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<T> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'GET',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride, { json: true })
		});

		await this.handleResponse(response);

		return response.json();
	}

	protected async post<T, R>(
		endpoint: string,
		payload: R,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<T> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'POST',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride, { json: true }),
			body: JSON.stringify(payload)
		});

		await this.handleResponse(response);

		return response.json();
	}

	protected async patch<T, R>(
		endpoint: string,
		payload: R,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<T> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'PATCH',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride, { json: true }),
			body: JSON.stringify(payload)
		});

		await this.handleResponse(response);

		return response.json();
	}

	protected async put<T, R>(
		endpoint: string,
		payload: R,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<T> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'PUT',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride, { json: true }),
			body: JSON.stringify(payload)
		});

		await this.handleResponse(response);

		return response.json();
	}

	protected async delete<T = void>(
		endpoint: string,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<T> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'DELETE',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride, { json: true })
		});

		await this.handleResponse(response);
		if (response.status === 204) {
			return undefined as T;
		}
		return response.json();
	}

	protected async postFormData<T>(
		endpoint: string,
		formData: FormData,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<T> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'POST',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride),
			body: formData
		});

		await this.handleResponse(response);

		return response.json();
	}

	protected async getBlob(
		endpoint: string,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<Blob> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'GET',
			credentials: 'include',
			headers: this.buildHeaders(headers, tokenOverride)
		});

		await this.handleResponse(response);

		return response.blob();
	}
}
