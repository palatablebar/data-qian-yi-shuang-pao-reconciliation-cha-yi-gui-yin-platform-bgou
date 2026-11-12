"""表对服务：列表 / 详情 / 维护。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.models.catalog import TablePair
from src.utils.errors import AppError


def list_pairs(db: Session) -> list[TablePair]:
    return db.query(TablePair).order_by(TablePair.id.asc()).all()


def get_pair(db: Session, pair_id: int) -> TablePair:
    pair = db.get(TablePair, pair_id)
    if pair is None:
        raise AppError(codes.NOT_FOUND, "表对不存在", f"pair_id={pair_id}")
    return pair


def get_pair_by_code(db: Session, code: str) -> TablePair:
    pair = db.query(TablePair).filter(TablePair.code == code).one_or_none()
    if pair is None:
        raise AppError(codes.NOT_FOUND, "表对不存在", f"pair_code={code}")
    return pair


def update_pair(db: Session, pair_id: int, payload) -> TablePair:
    pair = get_pair(db, pair_id)
    if payload.status is not None:
        pair.status = payload.status
    if payload.is_core is not None:
        pair.is_core = payload.is_core
    if payload.owner is not None:
        pair.owner = payload.owner
    if payload.description is not None:
        pair.description = payload.description
    db.commit()
    db.refresh(pair)
    return pair
