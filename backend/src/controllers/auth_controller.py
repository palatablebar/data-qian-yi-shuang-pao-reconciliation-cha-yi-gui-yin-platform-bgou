"""认证 controller：登录 / 刷新 / me / 用户列表。"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.enums import ActorKind
from src.constants.roles import ROLE_LABELS
from src.middlewares.auth import get_current_user
from src.middlewares.rate_limit import quota_snapshot
from src.models.account import User
from src.schemas.auth import LoginRequest, RefreshRequest, serialize_user
from src.services import audit_service, auth_service


def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = auth_service.authenticate(db, payload.email, payload.password)
    tokens = auth_service.issue_tokens(user)
    audit_service.record(
        db,
        action="auth.login",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={"role": user.role},
        ip=getattr(request.state, "client_ip", None),
        trace_id=getattr(request.state, "trace_id", None),
    )
    return {**tokens, "user": serialize_user(user), "role_label": ROLE_LABELS.get(user.role, user.role)}


def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    return auth_service.refresh(db, payload.refresh_token)


def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    payload = serialize_user(user)
    payload["role_label"] = ROLE_LABELS.get(user.role, user.role)
    payload["quota"] = quota_snapshot(user)
    return payload


def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    users = db.query(User).order_by(User.id.asc()).all()
    return {"items": [serialize_user(row) for row in users]}


def write_audit(db: Session, request: Request, *, action: str, entity_type: str, entity_id: str, user: User, payload: dict) -> None:
    audit_service.record(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=user.id,
        actor_kind=ActorKind.USER.value,
        payload=payload,
        ip=getattr(request.state, "client_ip", None),
        trace_id=getattr(request.state, "trace_id", None),
    )
