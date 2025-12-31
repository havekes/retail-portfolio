import { BaseService } from './baseService';

export interface LoginRequest {
  email: string;
  password: string;
}

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
  }
}

export const authService = new AuthService();