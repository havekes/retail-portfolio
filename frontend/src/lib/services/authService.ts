import { BaseService } from './baseService';
import { userStore } from '$lib/stores/userStore';
import type { User } from '$lib/types/user';

export interface LoginRequest {
	email: string;
	password: string;
}

export interface SignupRequest {
	email: string;
	password: string;
}

export interface AuthResponse {
	access_token: string;
	token_type: string;
	user: User;
}

export class AuthService extends BaseService {
	async login(credentials: LoginRequest): Promise<AuthResponse> {
		const response = await this.post<AuthResponse, LoginRequest>('/auth/login', credentials);
		userStore.setUser(response.user, response.access_token);
		return response;
	}

	async signup(credentials: SignupRequest): Promise<AuthResponse> {
		const response = await this.post<AuthResponse, SignupRequest>('/auth/signup', credentials);
		userStore.setUser(response.user, response.access_token);
		return response;
	}

	logout(): void {
		userStore.clearUser();
	}
}

export const authService = new AuthService();
