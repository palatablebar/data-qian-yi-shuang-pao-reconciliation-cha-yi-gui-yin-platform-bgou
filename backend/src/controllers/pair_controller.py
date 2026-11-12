"""表对 controller。"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers.auth_controller import write_audit
from src.middlewares.rbac import require_permission
from src.models.account import User
from src.schemas.pair import PairUpdateRequest, serialize_pair
from src.services import pair_service


def list_pairs(user: User = Depends(require_permission("pairs:read")), db: Session = Depends(get_db)) -> dict:
    pairs = [serialize_pair(pair) for pair in pair_service.list_pairs(db)]
    return {
        "items": pairs,
        "total_src_rows": sum(pair["row_estimate_src"] for pair in pairs),
        "total_tgt_rows": sum(pair["row_estimate_tgt"] for pair in pairs),
    }


def get_pair(pair_id: int, user: User = Depends(require_permission("pairs:read")), db: Session = Depends(get_db)) -> dict:
    return serialize_pair(pair_service.get_pair(db, pair_id))


def update_pair(
    pair_id: int,
    payload: PairUpdateRequest,
    request: Request,
    user: User = Depends(require_permission("pairs:write")),
    db: Session = Depends(get_db),
) -> dict:
    pair = pair_service.update_pair(db, pair_id, payload)
    write_audit(
        db,
        request,
        action="pair.update",
        entity_type="TablePair",
        entity_id=str(pair.id),
        user=user,
        payload=payload.model_dump(exclude_none=True),
    )
    return serialize_pair(pair)
