/** 把 ApiError / 未知异常收敛成审计口吻的一行说明。 */
import { ApiError } from '../api/client';

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const trace = error.detail ? `（${error.detail}）` : '';
    return `${error.code} · ${error.message}${trace}`;
  }
  if (error instanceof Error) return error.message;
  return '未知错误，请稍后重试';
}
