from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import signoff_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.schemas.signoff import SignoffCreateRequest, SignoffSignRequest

router = APIRouter(prefix="/signoffs", tags=["signoffs"], dependencies=[Depends(rate_limit_guard)])


@router.get("")
def list_signoffs(
    status: str | None = None,
    user=Depends(signoff_controller.require_permission("signoffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return signoff_controller.list_signoffs(status, user, db)


@router.post("")
def create_signoff(
    payload: SignoffCreateRequest,
    request: Request,
    user=Depends(signoff_controller.require_permission("signoffs:create")),
    db: Session = Depends(get_db),
) -> dict:
    return signoff_controller.create_signoff(payload, request, user, db)


@router.get("/{signoff_id}")
def get_signoff(
    signoff_id: int,
    user=Depends(signoff_controller.require_permission("signoffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return signoff_controller.get_signoff(signoff_id, user, db)


@router.post("/{signoff_id}/refresh")
def refresh_signoff(
    signoff_id: int,
    request: Request,
    user=Depends(signoff_controller.require_permission("signoffs:create")),
    db: Session = Depends(get_db),
) -> dict:
    return signoff_controller.refresh_signoff(signoff_id, request, user, db)


@router.post("/{signoff_id}/sign")
def sign_signoff(
    signoff_id: int,
    payload: SignoffSignRequest,
    request: Request,
    user=Depends(signoff_controller.require_permission("signoffs:sign")),
    db: Session = Depends(get_db),
) -> dict:
    return signoff_controller.sign_signoff(signoff_id, payload, request, user, db)


@router.post("/{signoff_id}/resign")
def resign_signoff(
    signoff_id: int,
    request: Request,
    user=Depends(signoff_controller.require_permission("signoffs:create")),
    db: Session = Depends(get_db),
) -> dict:
    return signoff_controller.resign_signoff(signoff_id, request, user, db)


@router.get("/{signoff_id}/export.csv")
def export_signoff_csv(
    signoff_id: int,
    user=Depends(signoff_controller.require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    return signoff_controller.export_signoff_csv(signoff_id, user, db)
