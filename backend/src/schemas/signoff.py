from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SignoffCreateRequest(BaseModel):
    batch_ids: list[int] = Field(min_length=1, max_length=20)
    title: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=2000)


class SignoffSignRequest(BaseModel):
    note: str = Field(default="", max_length=2000)


def _dt(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else value


def serialize_signoff(record: Any, freshness: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": record.id,
        "signoff_no": record.signoff_no,
        "title": record.title,
        "batch_ids": record.batch_ids,
        "batch_set_hash": record.batch_set_hash,
        "status": record.status,
        "snapshot_json": record.snapshot_json,
        "validation_json": record.validation_json,
        "note": record.note,
        "sign_note": record.sign_note,
        "created_by": record.created_by,
        "signed_by": record.signed_by,
        "signed_at": _dt(record.signed_at),
        "created_at": _dt(record.created_at),
        # 读时实时计算的新鲜度；不传则只给状态（兼容内部调用）
        "freshness": freshness,
    }
