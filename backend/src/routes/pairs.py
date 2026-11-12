from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ROLE_ADMIN
from src.controllers import pair_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.middlewares.rbac import require_role
from src.schemas.pair import PairUpdateRequest

router = APIRouter(prefix="/pairs", tags=["pairs"], dependencies=[Depends(rate_limit_guard)])


@router.get("")
def list_pairs(user=Depends(require_role(ROLE_ADMIN, "analyst", "viewer")), db: Session = Depends(get_db)) -> dict:
    return pair_controller.list_pairs(user, db)


@router.get("/{pair_id}")
def get_pair(pair_id: int, user=Depends(require_role(ROLE_ADMIN, "analyst", "viewer")), db: Session = Depends(get_db)) -> dict:
    return pair_controller.get_pair(pair_id, user, db)


@router.patch("/{pair_id}")
def update_pair(
    pair_id: int,
    payload: PairUpdateRequest,
    request: Request,
    user=Depends(require_role(ROLE_ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    return pair_controller.update_pair(pair_id, payload, request, user, db)
