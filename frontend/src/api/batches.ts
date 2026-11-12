import { download, get, post } from './client';
import type { Batch, Bucket, Estimate } from '../types/models';

export function listBatches(): Promise<{ items: Batch[]; total: number }> {
  return get<{ items: Batch[]; total: number }>('/batches');
}

export function getBatch(id: number): Promise<Batch> {
  return get<Batch>(`/batches/${id}`);
}

export interface BucketMatrixResponse {
  batch_id: number;
  bucket_count: number;
  status_counts: { match: number; mismatch: number; empty: number };
  items: Bucket[];
}

export function getBuckets(id: number): Promise<BucketMatrixResponse> {
  return get<BucketMatrixResponse>(`/batches/${id}/buckets`);
}

export interface CreateBatchPayload {
  pair_codes: string[];
  strategy: string;
  bucket_count: number;
  sample_rate: number;
  window_days: number;
  note?: string;
}

export function createBatch(payload: CreateBatchPayload): Promise<Batch> {
  return post<Batch>('/batches', payload);
}

export function runBatch(id: number, force = false): Promise<{ batch_id: number; task_id: string; status: string }> {
  return post<{ batch_id: number; task_id: string; status: string }>(`/batches/${id}/run`, { force });
}

export function estimate(pairCodes: string[], bucketCount: number, sampleRate: number): Promise<Estimate> {
  const params = new URLSearchParams({
    pair_codes: pairCodes.join(','),
    bucket_count: String(bucketCount),
    sample_rate: String(sampleRate),
  });
  return get<Estimate>(`/batches/estimate?${params.toString()}`);
}

export function exportAttribution(batchId: number): Promise<void> {
  return download(`/batches/${batchId}/export.csv`, `paritycheck-attribution-${batchId}.csv`);
}
