import { ApiClient } from './apiClient';
import type { User } from '@/types/user';

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

export class AuthService extends ApiClient {
	async login(credentials: LoginRequest): Promise<AuthResponse> {
		return this.post<AuthResponse, LoginRequest>('/auth/login', credentials);
	}

	async signup(credentials: SignupRequest): Promise<SignupResponse> {
		return this.post<SignupResponse, SignupRequest>('/auth/signup', credentials);
	}

	async verifyEmail(token: string): Promise<MessageResponse> {
		return this.post<MessageResponse, VerifyEmailRequest>('/auth/verify-email', { token });
	}

	async logout(): Promise<void> {
		await this.post('/auth/logout', {});
	}
}

export const authService = new AuthService();
