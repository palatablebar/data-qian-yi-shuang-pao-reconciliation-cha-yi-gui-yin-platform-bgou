import { get, patch } from './client';
import type { Pair } from '../types/models';

export interface PairList {
  items: Pair[];
  total_src_rows: number;
  total_tgt_rows: number;
}

export function listPairs(): Promise<PairList> {
  return get<PairList>('/pairs');
}

export function updatePair(id: number, body: Partial<Pick<Pair, 'status' | 'owner' | 'description'>>): Promise<Pair> {
  return patch<Pair>(`/pairs/${id}`, body);
}
