"""限流 / 配额中间件：Redis 滑动窗口（每用户每分钟）+ 每角色每日配额。"""
from __future__ import annotations

from datetime import date

from fastapi import Depends, Request

from src.config.settings import settings
from src.constants import error_codes as codes
from src.middlewares.auth import get_current_user
from src.models.account import User
from src.utils.errors import AppError
from src.utils.redis_client import get_redis

ROLE_QUOTA = {
    "admin": settings.quota_admin_daily,
    "analyst": settings.quota_analyst_daily,
    "viewer": settings.quota_viewer_daily,
}


def _check_minute(user_id: int, path: str) -> None:
    import time

    now_ts = time.time()
    key = f"paritycheck:ratelimit:{user_id}:{path}"
    client = get_redis()
    pipeline = client.pipeline()
    pipeline.zremrangebyscore(key, 0, now_ts - 60)
    pipeline.zadd(key, {f"{now_ts}": now_ts})
    pipeline.zcard(key)
    pipeline.expire(key, 60)
    results = pipeline.execute()
    count = int(results[2])
    if count > settings.rate_limit_per_minute:
        raise AppError(
            codes.RATE_LIMITED,
            "请求过于频繁，请稍后重试",
            f"count={count} limit={settings.rate_limit_per_minute}",
            extra={"retry_after": 60},
        )


def _check_daily(user: User) -> None:
    limit = ROLE_QUOTA.get(user.role, 500)
    key = f"paritycheck:quota:{user.role}:{user.id}:{date.today().isoformat()}"
    client = get_redis()
    used = int(client.incr(key))
    if used == 1:
        client.expire(key, 86400 + 3600)
    if used > limit:
        raise AppError(
            codes.QUOTA_EXCEEDED,
            "已达当前角色每日配额，请明日再试",
            f"role={user.role} used={used} limit={limit}",
            extra={"quota": limit},
        )


def rate_limit_guard(request: Request, user: User = Depends(get_current_user)) -> None:
    _check_minute(user.id, request.url.path)
    _check_daily(user)


def quota_snapshot(user: User) -> dict[str, int]:
    """当前用户当日配额使用情况（/auth/me 展示用）。"""
    limit = ROLE_QUOTA.get(user.role, 500)
    key = f"paritycheck:quota:{user.role}:{user.id}:{date.today().isoformat()}"
    try:
        used = int(get_redis().get(key) or 0)
    except Exception:  # noqa: BLE001 - Redis 不可用时展示 0，不影响鉴权
        used = 0
    return {"daily_limit": limit, "daily_used": used, "per_minute_limit": settings.rate_limit_per_minute}
