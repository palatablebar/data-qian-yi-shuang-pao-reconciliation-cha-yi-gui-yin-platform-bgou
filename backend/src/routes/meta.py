from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import meta_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.middlewares.rbac import require_permission

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    return meta_controller.health(db)


@router.get("/meta/enums", dependencies=[Depends(rate_limit_guard)])
def enums(user=Depends(require_permission("pairs:read"))) -> dict:
    return meta_controller.enums(user)


@router.get("/audit/logs", dependencies=[Depends(rate_limit_guard)])
def audit_logs(
    limit: int = 100,
    user=Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
) -> dict:
    return meta_controller.audit_logs(limit, user, db)
