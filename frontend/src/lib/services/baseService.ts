import { userStore } from '@/stores/userStore';

export abstract class BaseService {
	protected baseUrl: string;

	constructor() {
		this.baseUrl = import.meta.env.VITE_API_BASE_URL + '/api';
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

		return response.json();
	}
}
