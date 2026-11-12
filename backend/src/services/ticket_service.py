"""修复单服务：创建（从差异范围）/ 提交 / 审批 / 驳回 / 列表。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import TicketStatus
from src.models.account import User
from src.models.base import now
from src.models.recon import ReconBatch
from src.models.trace import DiffDetail, RepairTicket
from src.schemas.ticket import TicketCreateRequest
from src.utils.errors import AppError


def _next_ticket_no(db: Session) -> str:
    prefix = f"RT-{datetime.now():%Y%m%d}-"
    last = (
        db.query(RepairTicket)
        .filter(RepairTicket.ticket_no.like(f"{prefix}%"))
        .order_by(RepairTicket.id.desc())
        .first()
    )
    sequence = 1
    if last is not None:
        try:
            sequence = int(last.ticket_no.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            sequence = db.query(RepairTicket).count() + 1
    return f"{prefix}{sequence:04d}"


def create_ticket(db: Session, payload: TicketCreateRequest, user: User) -> RepairTicket:
    diffs = db.query(DiffDetail).filter(DiffDetail.id.in_(payload.diff_ids)).all()
    if not diffs:
        raise AppError(codes.TICKET_EMPTY_SCOPE, "修复单必须包含差异行", "diff_ids not found")
    if payload.batch_id is not None and db.get(ReconBatch, payload.batch_id) is None:
        raise AppError(codes.NOT_FOUND, "批次不存在", f"batch_id={payload.batch_id}")
    by_type: dict[str, int] = {}
    by_pair: dict[str, int] = {}
    by_field: dict[str, int] = {}
    for diff in diffs:
        by_type[diff.diff_type] = by_type.get(diff.diff_type, 0) + 1
        by_pair[diff.pair_code] = by_pair.get(diff.pair_code, 0) + 1
        field_key = f"{diff.pair_code}.{diff.field_name}"
        by_field[field_key] = by_field.get(field_key, 0) + 1
    ticket = RepairTicket(
        ticket_no=_next_ticket_no(db),
        title=payload.title,
        batch_id=payload.batch_id,
        pair_codes=payload.pair_codes,
        diff_scope_json={
            "diff_ids": [diff.id for diff in diffs],
            "by_type": by_type,
            "by_pair": by_pair,
            "by_field": by_field,
        },
        diff_count=len(diffs),
        status=TicketStatus.DRAFT.value,
        note=payload.note,
        created_by=user.id,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_ticket(db: Session, ticket_id: int) -> RepairTicket:
    ticket = db.get(RepairTicket, ticket_id)
    if ticket is None:
        raise AppError(codes.NOT_FOUND, "修复单不存在", f"ticket_id={ticket_id}")
    return ticket


def list_tickets(db: Session, status: str | None = None) -> list[RepairTicket]:
    query = db.query(RepairTicket)
    if status:
        query = query.filter(RepairTicket.status == status)
    return query.order_by(RepairTicket.id.desc()).all()


def submit(db: Session, ticket: RepairTicket) -> RepairTicket:
    if ticket.status != TicketStatus.DRAFT.value:
        raise AppError(codes.TICKET_INVALID_STATE, "只有草稿修复单可以提交", f"status={ticket.status}")
    ticket.status = TicketStatus.SUBMITTED.value
    ticket.submitted_at = now()
    db.commit()
    db.refresh(ticket)
    return ticket


def decide(db: Session, ticket: RepairTicket, approver: User, approve: bool, note: str) -> RepairTicket:
    if ticket.status != TicketStatus.SUBMITTED.value:
        raise AppError(
            codes.TICKET_INVALID_STATE,
            "只有已提交的修复单可以审批",
            f"status={ticket.status}",
        )
    ticket.status = TicketStatus.APPROVED.value if approve else TicketStatus.REJECTED.value
    ticket.approver_id = approver.id
    ticket.decision_note = note
    ticket.decided_at = now()
    db.commit()
    db.refresh(ticket)
    return ticket


def export_scope(ticket: RepairTicket) -> dict[str, Any]:
    return {
        "ticket_no": ticket.ticket_no,
        "diff_count": ticket.diff_count,
        "scope": ticket.diff_scope_json,
    }
