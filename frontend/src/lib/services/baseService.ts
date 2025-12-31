export abstract class BaseService {
  protected baseUrl: string;

  constructor() {
    this.baseUrl = import.meta.env.VITE_API_BASE_URL;
  }

  protected async get<T>(endpoint: string, headers?: Record<string, string>): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    });

    if (!response.ok) {
      throw new Error(`GET ${endpoint} failed: ${response.statusText}`);
    }

    return response.json();
  }

  protected async post<T>(endpoint: string, body: any, headers?: Record<string, string>): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`POST ${endpoint} failed: ${response.statusText}`);
    }

    return response.json();
  }
}