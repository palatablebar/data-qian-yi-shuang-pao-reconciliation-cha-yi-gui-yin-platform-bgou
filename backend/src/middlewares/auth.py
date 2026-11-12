"""认证中间件：Bearer → request.state.user；/health、/auth/login 白名单。"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants import error_codes as codes
from src.models.account import User
from src.utils.errors import AppError
from src.utils.jwt import decode_token

PUBLIC_PATHS = (
    "/health",
    "/api/health",
    "/auth/login",
    "/api/auth/login",
    "/auth/refresh",
    "/api/auth/refresh",
    "/docs",
    "/openapi.json",
)


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    return header.split(" ", 1)[1].strip()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = _extract_bearer(request)
    if not token:
        raise AppError(codes.AUTH_REQUIRED, "请先登录", "missing Authorization header")
    payload = decode_token(token)
    try:
        user_id = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        user_id = 0
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(codes.AUTH_INVALID, "登录状态无效，请重新登录", "user missing/inactive")
    request.state.user = user
    request.state.actor_kind = "user"
    return user


def audit_context(request: Request) -> dict[str, object]:
    return {
        "ip": getattr(request.state, "client_ip", None),
        "trace_id": getattr(request.state, "trace_id", None),
    }
