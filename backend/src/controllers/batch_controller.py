"""批次 controller：创建 / 运行 / 详情 / 桶矩阵 / 预估 / 归因导出。"""
from __future__ import annotations

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers.auth_controller import write_audit
from src.middlewares.rbac import require_permission
from src.models.account import User
from src.schemas.batch import BatchCreateRequest
from src.services import batch_service, diff_service


def create_batch(
    payload: BatchCreateRequest,
    request: Request,
    user: User = Depends(require_permission("batches:create")),
    db: Session = Depends(get_db),
) -> dict:
    batch = batch_service.create_batch(db, payload, user.id)
    write_audit(
        db,
        request,
        action="batch.create",
        entity_type="ReconBatch",
        entity_id=str(batch.id),
        user=user,
        payload={
            "batch_no": batch.batch_no,
            "pair_codes": batch.pair_codes,
            "bucket_count": batch.bucket_count,
            "sample_rate": batch.sample_rate,
        },
    )
    return batch_service.serialize_detail(db, batch)


def run_batch(
    batch_id: int,
    request: Request,
    user: User = Depends(require_permission("batches:run")),
    db: Session = Depends(get_db),
) -> dict:
    batch = batch_service.get_batch(db, batch_id)
    result = batch_service.dispatch_run(db, batch)
    write_audit(
        db,
        request,
        action="batch.run",
        entity_type="ReconBatch",
        entity_id=str(batch.id),
        user=user,
        payload={"batch_no": batch.batch_no, "task_id": result.get("task_id")},
    )
    return result


def list_batches(user: User = Depends(require_permission("batches:read")), db: Session = Depends(get_db)) -> dict:
    batches = [batch_service.serialize_detail(db, batch) for batch in batch_service.list_batches(db)]
    return {"items": batches, "total": len(batches)}


def get_batch(batch_id: int, user: User = Depends(require_permission("batches:read")), db: Session = Depends(get_db)) -> dict:
    return batch_service.serialize_detail(db, batch_service.get_batch(db, batch_id))


def list_buckets(
    batch_id: int,
    status: str | None = None,
    user: User = Depends(require_permission("batches:read")),
    db: Session = Depends(get_db),
) -> dict:
    return batch_service.list_buckets(db, batch_id, status)


def estimate(
    pair_codes: str = "",
    bucket_count: int = 128,
    sample_rate: int = 5,
    user: User = Depends(require_permission("batches:read")),
    db: Session = Depends(get_db),
) -> dict:
    codes = [code for code in pair_codes.split(",") if code]
    return batch_service.estimate(db, codes, bucket_count, sample_rate)


def attribution(
    batch_id: int,
    user: User = Depends(require_permission("diffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return diff_service.summary(db, batch_id)


def export_attribution(
    batch_id: int,
    user: User = Depends(require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    csv_text = diff_service.export_attribution_csv(db, batch_id)
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="paritycheck-attribution-{batch_id}.csv"'},
    )
