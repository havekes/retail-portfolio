import { ApiClient } from './apiClient';
import type { User } from '@/types/user';
import type {
	PublicKeyCredentialRequestOptionsJSON,
	AuthenticationResponseJSON
} from '@simplewebauthn/browser';

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

export interface LoginChallengeResponse {
	requires_2fa: boolean;
	mfa_token: string;
}

export type LoginResponse = AuthResponse | LoginChallengeResponse;

export interface LoginVerify2FaRequest {
	mfa_token: string;
	code: string;
}

export interface PasskeyAuthenticateOptionsRequest {
	email?: string;
}

export interface PasskeyAuthenticateVerifyRequest {
	credential: AuthenticationResponseJSON | Record<string, unknown> | string;
	email?: string;
}

export interface SignupResponse {
	message: string;
}

export class AuthService extends ApiClient {
	async login(credentials: LoginRequest): Promise<LoginResponse> {
		return this.post<LoginResponse, LoginRequest>('/auth/login', credentials);
	}

	async loginVerify2Fa(request: LoginVerify2FaRequest): Promise<AuthResponse> {
		return this.post<AuthResponse, LoginVerify2FaRequest>('/auth/2fa/login-verify', request);
	}

	async getPasskeyAuthOptions(
		request?: PasskeyAuthenticateOptionsRequest
	): Promise<PublicKeyCredentialRequestOptionsJSON> {
		return this.post<PublicKeyCredentialRequestOptionsJSON, PasskeyAuthenticateOptionsRequest>(
			'/auth/passkey/authenticate/options',
			request ?? {}
		);
	}

	async verifyPasskeyAuth(request: PasskeyAuthenticateVerifyRequest): Promise<AuthResponse> {
		return this.post<AuthResponse, PasskeyAuthenticateVerifyRequest>(
			'/auth/passkey/authenticate/verify',
			request
		);
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

	async getWsTicket(): Promise<{ ticket: string }> {
		return this.post<{ ticket: string }, Record<string, never>>('/auth/ws-ticket', {});
	}
}

export const authService = new AuthService();
