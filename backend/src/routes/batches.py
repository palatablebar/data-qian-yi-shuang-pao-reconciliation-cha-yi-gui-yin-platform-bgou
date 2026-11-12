from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import batch_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.schemas.batch import BatchCreateRequest, BatchRunRequest

router = APIRouter(prefix="/batches", tags=["batches"], dependencies=[Depends(rate_limit_guard)])


@router.get("/estimate")
def estimate(
    pair_codes: str = "",
    bucket_count: int = 128,
    sample_rate: int = 5,
    user=Depends(batch_controller.require_permission("batches:read")),
    db: Session = Depends(get_db),
) -> dict:
    return batch_controller.estimate(pair_codes, bucket_count, sample_rate, user, db)


@router.post("")
def create_batch(
    payload: BatchCreateRequest,
    request: Request,
    user=Depends(batch_controller.require_permission("batches:create")),
    db: Session = Depends(get_db),
) -> dict:
    return batch_controller.create_batch(payload, request, user, db)


@router.get("")
def list_batches(user=Depends(batch_controller.require_permission("batches:read")), db: Session = Depends(get_db)) -> dict:
    return batch_controller.list_batches(user, db)


@router.get("/{batch_id}")
def get_batch(batch_id: int, user=Depends(batch_controller.require_permission("batches:read")), db: Session = Depends(get_db)) -> dict:
    return batch_controller.get_batch(batch_id, user, db)


@router.post("/{batch_id}/run")
def run_batch(
    batch_id: int,
    request: Request,
    payload: BatchRunRequest | None = None,
    user=Depends(batch_controller.require_permission("batches:run")),
    db: Session = Depends(get_db),
) -> dict:
    return batch_controller.run_batch(batch_id, payload or BatchRunRequest(), request, user, db)


@router.get("/{batch_id}/buckets")
def list_buckets(
    batch_id: int,
    status: str | None = None,
    user=Depends(batch_controller.require_permission("batches:read")),
    db: Session = Depends(get_db),
) -> dict:
    return batch_controller.list_buckets(batch_id, status, user, db)


@router.get("/{batch_id}/attribution")
def attribution(
    batch_id: int,
    user=Depends(batch_controller.require_permission("diffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return batch_controller.attribution(batch_id, user, db)


@router.get("/{batch_id}/export.csv")
def export_attribution(
    batch_id: int,
    user=Depends(batch_controller.require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    return batch_controller.export_attribution(batch_id, user, db)
