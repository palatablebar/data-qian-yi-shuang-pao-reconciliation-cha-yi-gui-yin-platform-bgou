from __future__ import annotations

from datetime import datetime
from typing import Any


def serialize_diff(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "bucket_no": row.bucket_no,
        "pair_code": row.pair_code,
        "primary_key_value": row.primary_key_value,
        "field_name": row.field_name,
        "src_value": row.src_value,
        "tgt_value": row.tgt_value,
        "diff_type": row.diff_type,
        "similarity": float(row.similarity or 0),
        "attribution": row.attribution,
        "suggestion": row.suggestion,
        "created_at": row.created_at.isoformat() if isinstance(row.created_at, datetime) else row.created_at,
    }
