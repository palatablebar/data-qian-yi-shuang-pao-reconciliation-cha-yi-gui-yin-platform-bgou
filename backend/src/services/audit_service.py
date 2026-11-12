"""审计日志服务：关键动作写 audit_log 表（横切关注点）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.models.account import AuditLog


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor_id: int | None = None,
    actor_kind: str = "user",
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    trace_id: str | None = None,
) -> AuditLog:
    row = AuditLog(
        actor_id=actor_id,
        actor_kind=actor_kind,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        payload_json=payload or {},
        ip=ip,
        trace_id=trace_id,
    )
    db.add(row)
    db.commit()
    return row


def list_logs(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "actor_kind": row.actor_kind,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "payload": row.payload_json,
            "ip": row.ip,
            "trace_id": row.trace_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
