from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import ticket_controller
from src.middlewares.rate_limit import rate_limit_guard
from src.middlewares.rbac import require_permission
from src.schemas.ticket import TicketCreateRequest, TicketDecisionRequest

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(rate_limit_guard)])


@router.get("")
def list_tickets(
    status: str | None = None,
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_controller.list_tickets(status, user, db)


@router.post("")
def create_ticket(
    payload: TicketCreateRequest,
    request: Request,
    user=Depends(require_permission("tickets:create")),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_controller.create_ticket(payload, request, user, db)


@router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_controller.get_ticket(ticket_id, user, db)


@router.post("/{ticket_id}/submit")
def submit_ticket(
    ticket_id: int,
    request: Request,
    user=Depends(require_permission("tickets:submit")),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_controller.submit_ticket(ticket_id, request, user, db)


@router.post("/{ticket_id}/approve")
def approve_ticket(
    ticket_id: int,
    payload: TicketDecisionRequest,
    request: Request,
    user=Depends(require_permission("tickets:approve")),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_controller.approve_ticket(ticket_id, payload, request, user, db)


@router.post("/{ticket_id}/reject")
def reject_ticket(
    ticket_id: int,
    payload: TicketDecisionRequest,
    request: Request,
    user=Depends(require_permission("tickets:reject")),
    db: Session = Depends(get_db),
) -> dict:
    return ticket_controller.reject_ticket(ticket_id, payload, request, user, db)
