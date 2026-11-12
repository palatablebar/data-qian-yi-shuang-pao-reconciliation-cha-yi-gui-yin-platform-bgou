from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import diff_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.middlewares.rbac import require_permission

router = APIRouter(prefix="/diffs", tags=["diffs"], dependencies=[Depends(rate_limit_guard)])


@router.get("/summary")
def summary(
    batch_id: int,
    user=Depends(require_permission("diffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return diff_controller.summary(batch_id, user, db)


@router.get("/export.csv")
def export_diffs(
    batch_id: int | None = None,
    pair_code: str | None = None,
    request: Request = None,
    user=Depends(require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    return diff_controller.export_diffs(request, batch_id, pair_code, user, db)


@router.get("")
def list_diffs(
    batch_id: int | None = None,
    pair_code: str | None = None,
    field_name: str | None = None,
    diff_type: str | None = None,
    bucket_no: int | None = None,
    limit: int = 100,
    offset: int = 0,
    user=Depends(require_permission("diffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return diff_controller.list_diffs(
        batch_id, pair_code, field_name, diff_type, bucket_no, limit, offset, user, db
    )
