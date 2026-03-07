import { userStore } from '@/stores/userStore';

export class APIError extends Error {
	constructor(
		public status: number,
		public message: string,
		public response?: Response
	) {
		super(message);
		this.name = 'APIError';
	}
}

export abstract class BaseService {
	protected baseUrl: string;

	constructor() {
		this.baseUrl = import.meta.env.VITE_API_BASE_URL + '/api';
	}

	private async extractErrorMessage(response: Response): Promise<string> {
		const fallback = `Request failed with status ${response.status}`;
		try {
			const data = await response.json();
			if (data && data.detail) return String(data.detail);
		} catch {
			// Response body is not JSON or is empty
		}
		return fallback;
	}

	protected async get<T>(endpoint: string, headers?: Record<string, string>): Promise<T> {
		const token = userStore.getToken();
		const response = await fetch(`${this.baseUrl}${endpoint}`, {
			method: 'GET',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,

				...headers
			}
		});

		if (!response.ok) {
			const message = await this.extractErrorMessage(response);
			throw new APIError(response.status, message, response);
		}

		return response.json();
	}

	protected async post<T, R>(
		endpoint: string,
		payload: R,
		headers?: Record<string, string>
	): Promise<T> {
		const token = userStore.getToken();
		const response = await fetch(`${this.baseUrl}${endpoint}`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,
				...headers
			},
			body: JSON.stringify(payload)
		});

		if (!response.ok) {
			const message = await this.extractErrorMessage(response);
			throw new APIError(response.status, message, response);
		}

		return response.json();
	}

	protected async patch<T, R>(
		endpoint: string,
		payload: R,
		headers?: Record<string, string>
	): Promise<T> {
		const token = userStore.getToken();
		const response = await fetch(`${this.baseUrl}${endpoint}`, {
			method: 'PATCH',
			headers: {
				'Content-Type': 'application/json',
				Authorization: `Bearer ${token}`,

				...headers
			},
			body: JSON.stringify(payload)
		});

		if (!response.ok) {
			const message = await this.extractErrorMessage(response);
			throw new APIError(response.status, message, response);
		}

		return response.json();
	}
}
