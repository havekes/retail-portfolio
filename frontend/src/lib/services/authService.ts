import { BaseService } from './baseService';
<<<<<<< HEAD
import { userStore } from '$lib/stores/userStore';
import type { User } from '$lib/types/user';
=======
>>>>>>> 6019a5f (setup front for login)

export interface LoginRequest {
  email: string;
  password: string;
}

<<<<<<< HEAD
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
    const response = await this.post<AuthResponse>('/auth/login', credentials);
    userStore.setUser(response.user, response.access_token);
    return response;
  }

  async signup(credentials: SignupRequest): Promise<AuthResponse> {
    const response = await this.post<AuthResponse>('/auth/signup', credentials);
    userStore.setUser(response.user, response.access_token);
    return response;
  }

  logout(): void {
    userStore.clearUser();
=======
export interface LoginResponse {
  access_token: string;
  user: {
    id: number;
    email: string;
    name: string;
  };
}

export class AuthService extends BaseService {
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    return this.post<LoginResponse>('/login', credentials);
>>>>>>> 6019a5f (setup front for login)
  }
}

export const authService = new AuthService();