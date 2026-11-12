"""修复单 controller：创建 / 提交 / 审批 / 驳回。"""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers.auth_controller import write_audit
from src.middlewares.rbac import require_permission
from src.models.account import User
from src.schemas.ticket import TicketCreateRequest, TicketDecisionRequest, serialize_ticket
from src.services import ticket_service


def list_tickets(
    status: str | None = None,
    user: User = Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
) -> dict:
    tickets = [serialize_ticket(ticket) for ticket in ticket_service.list_tickets(db, status)]
    return {"items": tickets, "total": len(tickets)}


def get_ticket(ticket_id: int, user: User = Depends(require_permission("tickets:read")), db: Session = Depends(get_db)) -> dict:
    return serialize_ticket(ticket_service.get_ticket(db, ticket_id))


def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    user: User = Depends(require_permission("tickets:create")),
    db: Session = Depends(get_db),
) -> dict:
    ticket = ticket_service.create_ticket(db, payload, user)
    write_audit(
        db,
        request,
        action="ticket.create",
        entity_type="RepairTicket",
        entity_id=str(ticket.id),
        user=user,
        payload={"ticket_no": ticket.ticket_no, "diff_count": ticket.diff_count},
    )
    return serialize_ticket(ticket)


def submit_ticket(
    ticket_id: int,
    request: Request,
    user: User = Depends(require_permission("tickets:submit")),
    db: Session = Depends(get_db),
) -> dict:
    ticket = ticket_service.submit(db, ticket_service.get_ticket(db, ticket_id))
    write_audit(
        db,
        request,
        action="ticket.submit",
        entity_type="RepairTicket",
        entity_id=str(ticket.id),
        user=user,
        payload={"ticket_no": ticket.ticket_no},
    )
    return serialize_ticket(ticket)


def approve_ticket(
    ticket_id: int,
    payload: TicketDecisionRequest,
    request: Request,
    user: User = Depends(require_permission("tickets:approve")),
    db: Session = Depends(get_db),
) -> dict:
    ticket = ticket_service.decide(db, ticket_service.get_ticket(db, ticket_id), user, True, payload.note)
    write_audit(
        db,
        request,
        action="ticket.approve",
        entity_type="RepairTicket",
        entity_id=str(ticket.id),
        user=user,
        payload={"ticket_no": ticket.ticket_no, "note": payload.note},
    )
    return serialize_ticket(ticket)


def reject_ticket(
    ticket_id: int,
    payload: TicketDecisionRequest,
    request: Request,
    user: User = Depends(require_permission("tickets:reject")),
    db: Session = Depends(get_db),
) -> dict:
    ticket = ticket_service.decide(db, ticket_service.get_ticket(db, ticket_id), user, False, payload.note)
    write_audit(
        db,
        request,
        action="ticket.reject",
        entity_type="RepairTicket",
        entity_id=str(ticket.id),
        user=user,
        payload={"ticket_no": ticket.ticket_no, "note": payload.note},
    )
    return serialize_ticket(ticket)
