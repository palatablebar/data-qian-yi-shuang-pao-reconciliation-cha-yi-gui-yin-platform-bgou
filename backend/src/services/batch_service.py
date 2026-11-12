"""对账批次服务：创建 / 触发 Celery / 详情 / 桶矩阵 / 预估。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.config.celery_app import TASK_RUN_RECON_BATCH, celery_app
from src.constants import error_codes as codes
from src.constants.enums import BatchStatus, BucketStatus
from src.models.base import now
from src.models.catalog import TablePair
from src.models.recon import BucketResult, ReconBatch
from src.schemas.batch import BatchCreateRequest, serialize_batch, serialize_bucket
from src.schemas.pair import serialize_pair
from src.services.recon_engine import estimate_scan_cost
from src.utils.errors import AppError
from src.utils.logger import get_logger

logger = get_logger("paritycheck.batch_service")


def _next_batch_no(db: Session) -> str:
    prefix = f"PC-{datetime.now():%Y%m%d}-"
    last = (
        db.query(ReconBatch)
        .filter(ReconBatch.batch_no.like(f"{prefix}%"))
        .order_by(ReconBatch.id.desc())
        .first()
    )
    sequence = 1
    if last is not None:
        try:
            sequence = int(last.batch_no.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            sequence = db.query(ReconBatch).count() + 1
    return f"{prefix}{sequence:04d}"


def create_batch(db: Session, payload: BatchCreateRequest, user_id: int) -> ReconBatch:
    codes_set = list(dict.fromkeys(payload.pair_codes))
    pairs = db.query(TablePair).filter(TablePair.code.in_(codes_set)).all()
    found = {pair.code for pair in pairs}
    missing = [code for code in codes_set if code not in found]
    if missing:
        raise AppError(codes.NOT_FOUND, "表对不存在", f"missing_pair_codes={missing}")
    inactive = [pair.code for pair in pairs if pair.status != "active"]
    if inactive:
        raise AppError(codes.PAIR_INACTIVE, "存在已暂停的表对，不能发起批次", f"paused={inactive}")
    if not codes_set:
        raise AppError(codes.BATCH_NO_PAIRS, "批次必须至少选择一张表对", "pair_codes empty")

    batch = ReconBatch(
        batch_no=_next_batch_no(db),
        pair_codes=codes_set,
        strategy=payload.strategy,
        bucket_count=payload.bucket_count,
        sample_rate=payload.sample_rate,
        window_days=payload.window_days,
        status=BatchStatus.PENDING.value,
        created_by=user_id,
        params_json={"note": payload.note},
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def dispatch_run(db: Session, batch: ReconBatch, force: bool = False) -> dict[str, Any]:
    if batch.status == BatchStatus.RUNNING.value:
        raise AppError(codes.BATCH_ALREADY_RUNNING, "批次正在运行中", f"batch_id={batch.id}")
    if batch.status == BatchStatus.COMPLETED.value and not force:
        raise AppError(codes.BATCH_INVALID_STATE, "批次已完成，请新建批次重跑", f"batch_id={batch.id}")
    # 先落 running 再投递：worker 可能秒级完成，避免入队后本地 commit 把 completed 覆盖回 running
    batch.status = BatchStatus.RUNNING.value
    batch.started_at = batch.started_at or now()
    if force:
        # 重跑：清空完成态与失败原因，引擎内部会先删旧桶/旧差异再重算
        batch.failure_reason = None
        batch.finished_at = None
    db.commit()
    try:
        async_result = celery_app.send_task(
            TASK_RUN_RECON_BATCH, args=[batch.id], kwargs={"force": force}
        )
    except Exception as exc:  # noqa: BLE001 - broker 不可用时回滚状态并给出明确错误
        batch.status = BatchStatus.PENDING.value
        batch.started_at = None
        db.commit()
        logger.error("enqueue recon batch failed batch_id=%s error=%s", batch.id, exc)
        raise AppError(codes.INTERNAL_ERROR, "任务入队失败，请稍后重试", str(exc)) from exc
    return {"batch_id": batch.id, "task_id": getattr(async_result, "id", ""), "status": batch.status}


def list_batches(db: Session, status: str | None = None, limit: int = 50) -> list[ReconBatch]:
    query = db.query(ReconBatch)
    if status:
        query = query.filter(ReconBatch.status == status)
    return query.order_by(ReconBatch.id.desc()).limit(limit).all()


def get_batch(db: Session, batch_id: int) -> ReconBatch:
    batch = db.get(ReconBatch, batch_id)
    if batch is None:
        raise AppError(codes.NOT_FOUND, "批次不存在", f"batch_id={batch_id}")
    return batch


def batch_pairs(db: Session, batch: ReconBatch) -> list[dict[str, Any]]:
    pairs = db.query(TablePair).filter(TablePair.code.in_(batch.pair_codes or [])).all()
    return [serialize_pair(pair) for pair in pairs]


def serialize_detail(db: Session, batch: ReconBatch) -> dict[str, Any]:
    return serialize_batch(batch, batch_pairs(db, batch))


def list_buckets(db: Session, batch_id: int, status: str | None = None) -> dict[str, Any]:
    batch = get_batch(db, batch_id)
    query = db.query(BucketResult).filter(BucketResult.batch_id == batch_id)
    if status:
        query = query.filter(BucketResult.status == status)
    buckets = query.order_by(BucketResult.bucket_no.asc()).all()
    items = [serialize_bucket(bucket) for bucket in buckets]
    return {
        "batch_id": batch.id,
        "bucket_count": batch.bucket_count,
        "status_counts": {
            BucketStatus.MATCH.value: sum(1 for item in items if item["status"] == BucketStatus.MATCH.value),
            BucketStatus.MISMATCH.value: sum(
                1 for item in items if item["status"] == BucketStatus.MISMATCH.value
            ),
            BucketStatus.EMPTY.value: sum(1 for item in items if item["status"] == BucketStatus.EMPTY.value),
        },
        "items": items,
    }


def estimate(db: Session, pair_codes: list[str], bucket_count: int, sample_rate: int) -> dict[str, Any]:
    return estimate_scan_cost(db, pair_codes, bucket_count, sample_rate)
