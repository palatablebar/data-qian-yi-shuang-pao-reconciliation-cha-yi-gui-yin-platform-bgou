"""Declarative base 与时间工具。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def now() -> datetime:
    """容器 TZ=Asia/Shanghai，统一用本地 naive 时间入库。"""
    return datetime.now()
