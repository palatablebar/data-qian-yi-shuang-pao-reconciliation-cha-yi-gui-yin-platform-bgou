"""认证服务：PBKDF2 口令校验 + JWT 签发。"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants import error_codes as codes
from src.models.account import User
from src.utils.errors import AppError
from src.utils.jwt import create_access_token, create_refresh_token, decode_token

PBKDF2_ITERATIONS = 120000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
    ).hex()
    return hmac.compare_digest(candidate, digest)


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AppError(codes.AUTH_INVALID, "邮箱或密码不正确", f"email={email}")
    return user


def issue_tokens(user: User) -> dict[str, object]:
    return {
        "access_token": create_access_token(str(user.id), user.role, user.email),
        "refresh_token": create_refresh_token(str(user.id), user.role, user.email),
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
    }


def refresh(db: Session, refresh_token: str) -> dict[str, object]:
    payload = decode_token(refresh_token, expected_type="refresh")
    user = db.get(User, int(payload.get("sub") or 0))
    if user is None or not user.is_active:
        raise AppError(codes.AUTH_INVALID, "登录状态无效，请重新登录", "refresh user inactive")
    return issue_tokens(user)
