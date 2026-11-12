/** 统一 API 客户端：/api 前缀、Bearer、ApiError（code/status/detail）。 */
const TOKEN_KEY = 'paritycheck.token';
const USER_KEY = 'paritycheck.user';

export class ApiError extends Error {
  code: string;
  status: number;
  detail: string;

  constructor(status: number, payload: { code?: string; message?: string; detail?: string }) {
    super(payload.message || `HTTP ${status}`);
    this.status = status;
    this.code = payload.code || 'HTTP_ERROR';
    this.detail = payload.detail || '';
  }
}

export function readToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function writeSession(token: string, user: unknown): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function readCachedUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers || {});
  const token = readToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (!response.ok) {
    let payload: { code?: string; message?: string; detail?: string } = {};
    try {
      payload = await response.json();
    } catch {
      payload = { message: response.statusText };
    }
    throw new ApiError(response.status, payload);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
}

/** 导出 CSV：带 token 取 blob 再触发浏览器下载（HTTP 真实下载，非前端拼表）。 */
export async function download(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  const token = readToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`/api${path}`, { headers });
  if (!response.ok) {
    let payload: { code?: string; message?: string } = {};
    try {
      payload = await response.json();
    } catch {
      payload = { message: response.statusText };
    }
    throw new ApiError(response.status, payload);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
