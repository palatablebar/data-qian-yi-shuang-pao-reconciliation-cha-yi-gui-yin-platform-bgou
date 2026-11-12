from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PairUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(active|paused)$")
    owner: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=2000)


def serialize_pair(pair: Any) -> dict[str, Any]:
    return {
        "id": pair.id,
        "code": pair.code,
        "display_name": pair.display_name,
        "src_table": pair.src_table,
        "tgt_table": pair.tgt_table,
        "primary_key": pair.primary_key,
        "field_rules": pair.field_rules,
        "field_count": len(pair.field_rules or []),
        "status": pair.status,
        "owner": pair.owner,
        "row_estimate_src": pair.row_estimate_src,
        "row_estimate_tgt": pair.row_estimate_tgt,
        "description": pair.description,
        "created_at": pair.created_at.isoformat() if isinstance(pair.created_at, datetime) else pair.created_at,
    }
