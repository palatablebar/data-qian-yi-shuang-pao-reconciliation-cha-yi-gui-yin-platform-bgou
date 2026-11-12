"""对账批次与桶结果。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, now


class ReconBatch(Base):
    __tablename__ = "recon_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    pair_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="checksum")
    bucket_count: Mapped[int] = mapped_column(Integer, nullable=False, default=128)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    buckets_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buckets_matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buckets_mismatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    buckets_empty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    src_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tgt_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    diff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    params_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    scan_cost_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False, index=True)


class BucketResult(Base):
    __tablename__ = "bucket_results"
    __table_args__ = (UniqueConstraint("batch_id", "bucket_no", name="uq_bucket_batch_no"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bucket_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    src_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tgt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    src_checksum: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tgt_checksum: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="match")
    pair_breakdown: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    compared_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
