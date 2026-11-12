from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import auth_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.middlewares.rbac import require_role
from src.constants.roles import ROLE_ADMIN
from src.schemas.auth import LoginRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    return auth_controller.login(request, payload, db)


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    return auth_controller.refresh(payload, db)


@router.get("/me", dependencies=[Depends(rate_limit_guard)])
def me(user=Depends(auth_controller.get_current_user), db: Session = Depends(get_db)) -> dict:
    return auth_controller.me(user, db)


@router.get("/users", dependencies=[Depends(rate_limit_guard)])
def list_users(user=Depends(require_role(ROLE_ADMIN)), db: Session = Depends(get_db)) -> dict:
    return auth_controller.list_users(user, db)
