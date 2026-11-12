from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class BatchCreateRequest(BaseModel):
    pair_codes: list[str] = Field(min_length=1, max_length=10)
    strategy: str = Field(default="checksum", pattern="^(checksum|row_hash)$")
    bucket_count: int = Field(default=128)
    sample_rate: int = Field(default=5, ge=1, le=100)
    window_days: int = Field(default=30, ge=1, le=90)
    note: str = Field(default="", max_length=500)

    @field_validator("bucket_count")
    @classmethod
    def _bucket_allowed(cls, value: int) -> int:
        if value not in (64, 128, 256):
            raise ValueError("bucket_count 只能取 64 / 128 / 256")
        return value


def serialize_batch(batch: Any, include_pairs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "pair_codes": batch.pair_codes,
        "pairs": include_pairs or [],
        "strategy": batch.strategy,
        "bucket_count": batch.bucket_count,
        "sample_rate": batch.sample_rate,
        "window_days": batch.window_days,
        "status": batch.status,
        "buckets_total": batch.buckets_total,
        "buckets_matched": batch.buckets_matched,
        "buckets_mismatched": batch.buckets_mismatched,
        "buckets_empty": batch.buckets_empty,
        "src_rows": batch.src_rows,
        "tgt_rows": batch.tgt_rows,
        "skip_rate": float(batch.skip_rate or 0),
        "diff_count": batch.diff_count,
        "failure_reason": batch.failure_reason,
        "params_json": batch.params_json,
        "scan_cost_json": batch.scan_cost_json,
        "created_by": batch.created_by,
        "started_at": batch.started_at.isoformat() if isinstance(batch.started_at, datetime) else batch.started_at,
        "finished_at": batch.finished_at.isoformat() if isinstance(batch.finished_at, datetime) else batch.finished_at,
        "created_at": batch.created_at.isoformat() if isinstance(batch.created_at, datetime) else batch.created_at,
    }


def serialize_bucket(bucket: Any) -> dict[str, Any]:
    return {
        "id": bucket.id,
        "batch_id": bucket.batch_id,
        "bucket_no": bucket.bucket_no,
        "src_count": bucket.src_count,
        "tgt_count": bucket.tgt_count,
        "src_checksum": bucket.src_checksum,
        "tgt_checksum": bucket.tgt_checksum,
        "status": bucket.status,
        "pair_breakdown": bucket.pair_breakdown,
        "compared_rows": bucket.compared_rows,
        "elapsed_ms": bucket.elapsed_ms,
    }
