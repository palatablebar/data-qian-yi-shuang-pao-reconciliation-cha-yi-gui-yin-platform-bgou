import { get, post } from './client';
import type { User } from '../types/models';

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
  role_label: string;
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return post<LoginResponse>('/auth/login', { email, password });
}

export function me(): Promise<User> {
  return get<User>('/auth/me');
}

export function listUsers(): Promise<{ items: User[] }> {
  return get<{ items: User[] }>('/auth/users');
}
