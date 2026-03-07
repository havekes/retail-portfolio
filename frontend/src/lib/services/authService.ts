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

export interface VerifyEmailRequest {
	token: string;
}

export interface MessageResponse {
	message: string;
}

export interface AuthResponse {
	access_token: string;
	token_type: string;
	user: User;
}

export interface SignupResponse {
	message: string;
}

export class AuthService extends BaseService {
	async login(credentials: LoginRequest): Promise<AuthResponse> {
		const response = await this.post<AuthResponse, LoginRequest>('/auth/login', credentials);
		userStore.setUser(response.user, response.access_token);
		return response;
	}

	async signup(credentials: SignupRequest): Promise<SignupResponse> {
		return this.post<SignupResponse, SignupRequest>('/auth/signup', credentials);
	}

	async verifyEmail(token: string): Promise<MessageResponse> {
		return this.post<MessageResponse, VerifyEmailRequest>('/auth/verify-email', { token });
	}

	logout(): void {
		userStore.clearUser();
	}
}

export const authService = new AuthService();
