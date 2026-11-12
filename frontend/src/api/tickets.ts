import { get, post } from './client';
import type { Ticket } from '../types/models';

export function listTickets(): Promise<{ items: Ticket[]; total: number }> {
  return get<{ items: Ticket[]; total: number }>('/tickets');
}

export interface CreateTicketPayload {
  batch_id?: number;
  pair_codes: string[];
  diff_ids: number[];
  title: string;
  note?: string;
}

export function createTicket(payload: CreateTicketPayload): Promise<Ticket> {
  return post<Ticket>('/tickets', payload);
}

export function submitTicket(id: number): Promise<Ticket> {
  return post<Ticket>(`/tickets/${id}/submit`);
}

export function approveTicket(id: number, note: string): Promise<Ticket> {
  return post<Ticket>(`/tickets/${id}/approve`, { note });
}

export function rejectTicket(id: number, note: string): Promise<Ticket> {
  return post<Ticket>(`/tickets/${id}/reject`, { note });
}
