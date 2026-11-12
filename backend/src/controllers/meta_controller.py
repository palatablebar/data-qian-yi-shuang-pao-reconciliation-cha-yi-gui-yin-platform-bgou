"""元信息 controller：健康检查 / 枚举字典 / 审计日志。"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.config.settings import settings
from src.constants.enums import (
    DIFF_TYPE_LABELS,
    BatchStatus,
    BucketStatus,
    DiffType,
    PairStatus,
    TicketStatus,
)
from src.constants.roles import ROLE_LABELS
from src.middlewares.rbac import require_permission
from src.models.account import User
from src.services import audit_service
from src.utils.redis_client import redis_ping


def health(db: Session = Depends(get_db)) -> dict:
    from src.config.database import ping_db

    return {
        "status": "ok",
        "service": "paritycheck-backend",
        "db": "ok" if ping_db() else "down",
        "redis": "ok" if redis_ping() else "down",
        "seed_demo": settings.seed_demo,
    }


def enums(user: User = Depends(require_permission("pairs:read"))) -> dict:
    return {
        "batch_status": [item.value for item in BatchStatus],
        "bucket_status": [item.value for item in BucketStatus],
        "diff_type": [item.value for item in DiffType],
        "diff_type_labels": DIFF_TYPE_LABELS,
        "ticket_status": [item.value for item in TicketStatus],
        "pair_status": [item.value for item in PairStatus],
        "role_labels": ROLE_LABELS,
    }


def audit_logs(
    limit: int = 100,
    user: User = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
) -> dict:
    return {"items": audit_service.list_logs(db, min(limit, 200))}
