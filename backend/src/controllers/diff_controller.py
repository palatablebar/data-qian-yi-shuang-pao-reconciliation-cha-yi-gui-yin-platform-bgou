"""差异明细 controller：筛选 / 归因摘要 / CSV 导出。"""
from __future__ import annotations

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers.auth_controller import write_audit
from src.middlewares.rbac import require_permission
from src.models.account import User
from src.services import diff_service


def list_diffs(
    batch_id: int | None = None,
    pair_code: str | None = None,
    field_name: str | None = None,
    diff_type: str | None = None,
    bucket_no: int | None = None,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(require_permission("diffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return diff_service.list_diffs(
        db,
        batch_id=batch_id,
        pair_code=pair_code,
        field_name=field_name,
        diff_type=diff_type,
        bucket_no=bucket_no,
        limit=limit,
        offset=offset,
    )


def summary(batch_id: int, user: User = Depends(require_permission("diffs:read")), db: Session = Depends(get_db)) -> dict:
    return diff_service.summary(db, batch_id)


def export_diffs(
    request: Request,
    batch_id: int | None = None,
    pair_code: str | None = None,
    user: User = Depends(require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    csv_text = diff_service.export_diffs_csv(db, batch_id, pair_code)
    write_audit(
        db,
        request,
        action="export.diffs",
        entity_type="ReconBatch",
        entity_id=str(batch_id or ""),
        user=user,
        payload={"pair_code": pair_code},
    )
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="paritycheck-diffs-{batch_id or "all"}.csv"'},
    )
