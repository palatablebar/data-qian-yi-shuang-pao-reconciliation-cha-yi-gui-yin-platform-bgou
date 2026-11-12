import { download, get } from './client';
import type { Diff, DiffSummary, Paged } from '../types/models';

export interface DiffQuery {
  batch_id?: number;
  pair_code?: string;
  field_name?: string;
  diff_type?: string;
  bucket_no?: number;
  limit?: number;
  offset?: number;
}

export function listDiffs(query: DiffQuery): Promise<Paged<Diff>> {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '' && value !== null) params.set(key, String(value));
  });
  return get<Paged<Diff>>(`/diffs?${params.toString()}`);
}

export function getSummary(batchId: number): Promise<DiffSummary> {
  return get<DiffSummary>(`/diffs/summary?batch_id=${batchId}`);
}

export function exportDiffs(batchId: number, pairCode?: string): Promise<void> {
  const suffix = pairCode ? `&pair_code=${pairCode}` : '';
  return download(`/diffs/export.csv?batch_id=${batchId}${suffix}`, `paritycheck-diffs-${batchId}.csv`);
}
