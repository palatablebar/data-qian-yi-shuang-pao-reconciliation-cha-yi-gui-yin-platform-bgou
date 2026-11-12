"""差异明细服务：筛选 / 分页 / 归因摘要 / CSV 导出。"""
from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import DIFF_TYPE_LABELS, DiffType
from src.models.catalog import TablePair
from src.models.recon import ReconBatch
from src.models.trace import DiffDetail
from src.schemas.diff import serialize_diff
from src.services import diff_engine
from src.utils.errors import AppError


def list_diffs(
    db: Session,
    *,
    batch_id: int | None = None,
    pair_code: str | None = None,
    field_name: str | None = None,
    diff_type: str | None = None,
    bucket_no: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    query = db.query(DiffDetail)
    if batch_id is not None:
        query = query.filter(DiffDetail.batch_id == batch_id)
    if pair_code:
        query = query.filter(DiffDetail.pair_code == pair_code)
    if field_name:
        query = query.filter(DiffDetail.field_name == field_name)
    if diff_type:
        query = query.filter(DiffDetail.diff_type == diff_type)
    if bucket_no is not None:
        query = query.filter(DiffDetail.bucket_no == bucket_no)
    total = query.count()
    rows = (
        query.order_by(DiffDetail.bucket_no.asc(), DiffDetail.id.asc())
        .limit(min(limit, 500))
        .offset(max(offset, 0))
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [serialize_diff(row) for row in rows],
    }


def summary(db: Session, batch_id: int) -> dict[str, Any]:
    batch = db.get(ReconBatch, batch_id)
    if batch is None:
        raise AppError(codes.NOT_FOUND, "批次不存在", f"batch_id={batch_id}")
    attribution = diff_engine.aggregate_attribution(db, batch_id)
    type_rows = (
        db.query(DiffDetail.diff_type, func.count(DiffDetail.id))
        .filter(DiffDetail.batch_id == batch_id)
        .group_by(DiffDetail.diff_type)
        .all()
    )
    by_type = [
        {
            "diff_type": diff_type,
            "label": DIFF_TYPE_LABELS.get(DiffType(diff_type), diff_type),
            "count": int(count),
        }
        for diff_type, count in type_rows
    ]
    by_type.sort(key=lambda item: -item["count"])
    return {
        "batch_id": batch_id,
        "batch_no": batch.batch_no,
        "total_diffs": attribution["total_diffs"],
        "by_type": by_type,
        "groups": attribution["groups"],
        "top_group": attribution["top_group"],
    }


def build_csv(rows: list[DiffDetail], pairs: dict[str, TablePair]) -> str:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "差异ID",
            "批次ID",
            "桶号",
            "表对",
            "源表",
            "主键",
            "字段",
            "源值",
            "目标值",
            "差异类型",
            "相似度",
            "归因",
            "建议",
        ]
    )
    for row in rows:
        pair = pairs.get(row.pair_code)
        writer.writerow(
            [
                row.id,
                row.batch_id,
                row.bucket_no,
                row.pair_code,
                pair.src_table if pair else row.pair_code,
                row.primary_key_value,
                "整行" if row.field_name == "__row__" else row.field_name,
                "" if row.src_value is None else row.src_value,
                "" if row.tgt_value is None else row.tgt_value,
                row.diff_type,
                f"{float(row.similarity or 0):.4f}",
                row.attribution,
                row.suggestion,
            ]
        )
    return buffer.getvalue()


def export_diffs_csv(db: Session, batch_id: int | None, pair_code: str | None) -> str:
    query = db.query(DiffDetail)
    if batch_id is not None:
        query = query.filter(DiffDetail.batch_id == batch_id)
    if pair_code:
        query = query.filter(DiffDetail.pair_code == pair_code)
    rows = query.order_by(DiffDetail.id.asc()).all()
    pairs = {pair.code: pair for pair in db.query(TablePair).all()}
    return build_csv(rows, pairs)


def export_attribution_csv(db: Session, batch_id: int) -> str:
    payload = summary(db, batch_id)
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["批次号", "表对", "源表", "字段", "差异类型", "数量", "占比", "最可能原因", "建议"])
    for group in payload["groups"]:
        writer.writerow(
            [
                payload["batch_no"],
                group["pair_code"],
                group["table"],
                group["field_label"],
                group["diff_type"],
                group["count"],
                f"{group['ratio']:.4f}",
                group["root_cause"],
                group["suggestion"],
            ]
        )
    return buffer.getvalue()
