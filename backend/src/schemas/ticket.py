from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TicketCreateRequest(BaseModel):
    batch_id: int | None = None
    pair_codes: list[str] = Field(min_length=1, max_length=10)
    diff_ids: list[int] = Field(min_length=1, max_length=5000)
    title: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=2000)


class TicketDecisionRequest(BaseModel):
    note: str = Field(default="", max_length=2000)


def serialize_ticket(ticket: Any) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "title": ticket.title,
        "batch_id": ticket.batch_id,
        "pair_codes": ticket.pair_codes,
        "diff_scope_json": ticket.diff_scope_json,
        "diff_count": ticket.diff_count,
        "status": ticket.status,
        "note": ticket.note,
        "decision_note": ticket.decision_note,
        "created_by": ticket.created_by,
        "approver_id": ticket.approver_id,
        "submitted_at": ticket.submitted_at.isoformat() if isinstance(ticket.submitted_at, datetime) else ticket.submitted_at,
        "decided_at": ticket.decided_at.isoformat() if isinstance(ticket.decided_at, datetime) else ticket.decided_at,
        "created_at": ticket.created_at.isoformat() if isinstance(ticket.created_at, datetime) else ticket.created_at,
    }
