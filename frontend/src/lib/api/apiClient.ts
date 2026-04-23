import { browser } from '$app/environment';

export class ApiError extends Error {
	constructor(
		public status: number,
		public message: string,
		public response?: Response
	) {
		super(message);
		this.name = 'ApiError';
	}
}

export abstract class ApiClient {
	protected baseUrl: string;
	protected fetch: typeof fetch;

	constructor(customFetch?: typeof fetch) {
		const base = browser
			? import.meta.env.VITE_API_BASE_URL || ''
			: (import.meta.env.VITE_INTERNAL_API_URL ?? import.meta.env.VITE_API_BASE_URL ?? '');
		this.baseUrl = (base.endsWith('/') ? base.slice(0, -1) : base) + '/api';
		this.fetch = customFetch || fetch;
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
			throw new ApiError(response.status, message, response);
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
			headers: {
				'Content-Type': 'application/json',
				...(tokenOverride ? { Authorization: `Bearer ${tokenOverride}` } : {}),
				...headers
			}
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
			headers: {
				'Content-Type': 'application/json',
				...(tokenOverride ? { Authorization: `Bearer ${tokenOverride}` } : {}),
				...headers
			},
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
			headers: {
				'Content-Type': 'application/json',
				...(tokenOverride ? { Authorization: `Bearer ${tokenOverride}` } : {}),
				...headers
			},
			body: JSON.stringify(payload)
		});

		await this.handleResponse(response);

		return response.json();
	}

	protected async delete(
		endpoint: string,
		headers?: Record<string, string>,
		tokenOverride?: string | null
	): Promise<void> {
		const response = await this.fetch(`${this.baseUrl}${endpoint}`, {
			method: 'DELETE',
			credentials: 'include',
			headers: {
				'Content-Type': 'application/json',
				...(tokenOverride ? { Authorization: `Bearer ${tokenOverride}` } : {}),
				...headers
			}
		});

		await this.handleResponse(response);
	}
}
