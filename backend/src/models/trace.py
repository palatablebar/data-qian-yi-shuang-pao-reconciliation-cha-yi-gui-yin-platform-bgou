"""差异明细与修复单。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, now


class DiffDetail(Base):
    __tablename__ = "diff_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bucket_no: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pair_code: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    primary_key_value: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    src_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    tgt_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    similarity: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    attribution: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    suggestion: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)


class RepairTicket(Base):
    __tablename__ = "repair_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    pair_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    diff_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    diff_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
