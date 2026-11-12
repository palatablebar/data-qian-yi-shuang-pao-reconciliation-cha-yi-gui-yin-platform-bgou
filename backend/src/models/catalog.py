"""表对（源表 / 目标表 / 主键 / 字段规则 / 负责人）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, now


class TablePair(Base):
    __tablename__ = "table_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    src_table: Mapped[str] = mapped_column(String(64), nullable=False)
    tgt_table: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_key: Mapped[str] = mapped_column(String(64), nullable=False)
    field_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    owner: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    row_estimate_src: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_estimate_tgt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
