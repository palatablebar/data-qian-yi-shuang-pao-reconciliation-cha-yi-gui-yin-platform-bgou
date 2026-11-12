/** 与后端 schemas 一一对应的领域类型。 */
export type Role = 'admin' | 'analyst' | 'viewer';

export interface QuotaInfo {
  daily_limit: number;
  daily_used: number;
  per_minute_limit: number;
}

export interface User {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  role_label?: string;
  quota?: QuotaInfo;
}

export interface FieldRule {
  name: string;
  type: 'string' | 'numeric' | 'datetime';
  compare: string;
}

export interface Pair {
  id: number;
  code: string;
  display_name: string;
  src_table: string;
  tgt_table: string;
  primary_key: string;
  field_rules: FieldRule[];
  field_count: number;
  status: 'active' | 'paused';
  is_core: boolean;
  owner: string;
  row_estimate_src: number;
  row_estimate_tgt: number;
  description: string;
  created_at?: string;
}

export interface Batch {
  id: number;
  batch_no: string;
  pair_codes: string[];
  pairs: Pair[];
  strategy: string;
  bucket_count: number;
  sample_rate: number;
  window_days: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  buckets_total: number;
  buckets_matched: number;
  buckets_mismatched: number;
  buckets_empty: number;
  src_rows: number;
  tgt_rows: number;
  skip_rate: number;
  diff_count: number;
  failure_reason: string | null;
  params_json: Record<string, unknown>;
  scan_cost_json: Record<string, number | string | Record<string, number>>;
  created_by: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface Bucket {
  id: number;
  batch_id: number;
  bucket_no: number;
  src_count: number;
  tgt_count: number;
  src_checksum: number;
  tgt_checksum: number;
  status: 'match' | 'mismatch' | 'empty';
  pair_breakdown: Array<{
    pair_code: string;
    src_count: number;
    tgt_count: number;
    src_checksum: number;
    tgt_checksum: number;
    status: string;
  }>;
  compared_rows: number;
  elapsed_ms: number;
}

export interface Diff {
  id: number;
  batch_id: number;
  bucket_no: number;
  pair_code: string;
  primary_key_value: string;
  field_name: string;
  src_value: string | null;
  tgt_value: string | null;
  diff_type: string;
  similarity: number;
  attribution: string;
  suggestion: string;
  created_at: string;
}

export interface AttributionGroup {
  pair_code: string;
  table: string;
  field_name: string;
  field_label: string;
  diff_type: string;
  count: number;
  ratio: number;
  root_cause: string;
  suggestion: string;
}

export interface DiffSummary {
  batch_id: number;
  batch_no: string;
  total_diffs: number;
  by_type: Array<{ diff_type: string; label: string; count: number }>;
  groups: AttributionGroup[];
  top_group: AttributionGroup | null;
}

export interface Ticket {
  id: number;
  ticket_no: string;
  title: string;
  batch_id: number | null;
  pair_codes: string[];
  diff_scope_json: {
    diff_ids?: number[];
    by_type?: Record<string, number>;
    by_pair?: Record<string, number>;
    by_field?: Record<string, number>;
  };
  diff_count: number;
  status: 'draft' | 'submitted' | 'approved' | 'rejected';
  note: string;
  decision_note: string;
  created_by: number | null;
  approver_id: number | null;
  submitted_at: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface Estimate {
  pair_count: number;
  bucket_count: number;
  sample_rate: number;
  src_rows: number;
  tgt_rows: number;
  rows_per_bucket: number;
  estimated_sampled_rows: number;
  estimated_scan_ms: number;
  source_batch: string | null;
}

export type SignoffStatusValue = 'draft' | 'signed';
export type SignoffFreshness = 'fresh' | 'stale';

export interface StaleReason {
  reason: string;
  label: string;
  detail: Record<string, unknown>;
}

export interface SignoffPairVerdict {
  pair_code: string;
  display_name: string;
  is_core: boolean;
  verdict: 'acceptable' | 'blocked';
  diff_total: number;
  exempted_count: number;
  blocking_count: number;
}

export interface SignoffExemption {
  ticket_id: number;
  ticket_no: string;
  title: string;
  status: string;
  approver_id: number | null;
  decided_at: string | null;
  exempted_diff_count: number;
  by_pair: Record<string, number>;
  by_type: Record<string, number>;
  diff_ids: number[];
}

export interface SignoffBlockingDiff {
  diff_id: number;
  batch_id: number;
  pair_code: string;
  field_name: string;
  primary_key_value: string;
  diff_type: string;
  bucket_no: number;
}

export interface SignoffSnapshot {
  frozen_at: string;
  batch_ids: number[];
  batches: Array<{
    batch_id: number;
    batch_no: string;
    status: string;
    pair_codes: string[];
    bucket_count: number;
    sample_rate: number;
    window_days: number;
    buckets_matched: number;
    buckets_mismatched: number;
    diff_count: number;
    finished_at: string | null;
    fingerprint: string;
  }>;
  core_pair_codes: string[];
  covered_pair_codes: string[];
  pair_verdicts: SignoffPairVerdict[];
  acceptable_pair_codes: string[];
  blocking_diffs: SignoffBlockingDiff[];
  exemptions: SignoffExemption[];
  ticket_fingerprints: Array<{ ticket_id: number; ticket_no: string; status: string; fingerprint: string }>;
  validation: {
    passable: boolean;
    blocking_reasons: string[];
    uncovered_core_pairs: string[];
    blocking_diff_count: number;
    exempted_diff_count: number;
    checked_at: string;
  };
}

export interface Signoff {
  id: number;
  signoff_no: string;
  title: string;
  batch_ids: number[];
  batch_set_hash: string;
  status: SignoffStatusValue;
  snapshot_json: SignoffSnapshot;
  validation_json: SignoffSnapshot['validation'];
  note: string;
  sign_note: string;
  created_by: number | null;
  signed_by: number | null;
  signed_at: string | null;
  created_at: string;
  freshness: {
    freshness: SignoffFreshness;
    stale_reasons: StaleReason[];
    evaluated_at: string;
  } | null;
}

export interface Paged<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}
