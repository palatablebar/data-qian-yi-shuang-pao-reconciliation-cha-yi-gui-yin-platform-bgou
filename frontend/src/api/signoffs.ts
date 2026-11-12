import { download, get, post } from './client';
import type { Signoff } from '../types/models';

export function listSignoffs(status?: string): Promise<{ items: Signoff[]; total: number }> {
  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return get<{ items: Signoff[]; total: number }>(`/signoffs${query}`);
}

export function getSignoff(id: number): Promise<Signoff> {
  return get<Signoff>(`/signoffs/${id}`);
}

export interface CreateSignoffPayload {
  batch_ids: number[];
  title?: string;
  note?: string;
}

export function createSignoff(payload: CreateSignoffPayload): Promise<Signoff> {
  return post<Signoff>('/signoffs', payload);
}

export function refreshSignoff(id: number): Promise<Signoff> {
  return post<Signoff>(`/signoffs/${id}/refresh`);
}

export function signSignoff(id: number, note: string): Promise<Signoff> {
  return post<Signoff>(`/signoffs/${id}/sign`, { note });
}

export function resignSignoff(id: number): Promise<Signoff> {
  return post<Signoff>(`/signoffs/${id}/resign`);
}

export function exportSignoff(id: number): Promise<void> {
  return download(`/signoffs/${id}/export.csv`, `paritycheck-signoff-${id}.csv`);
}
