"""签核底稿 controller：生成草稿 / 刷新 / 签核 / 重签 / 台账 / 详情 / CSV 导出。"""
from __future__ import annotations

import csv
import io

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers.auth_controller import write_audit
from src.constants.enums import STALE_REASON_LABELS
from src.middlewares.rbac import require_permission
from src.models.account import User
from src.schemas.signoff import SignoffCreateRequest, SignoffSignRequest, serialize_signoff
from src.services import signoff_service


def _serialize(db: Session, record) -> dict:
    freshness = signoff_service.evaluate_freshness(db, record)
    for reason in freshness["stale_reasons"]:
        reason["label"] = STALE_REASON_LABELS.get(reason["reason"], reason["reason"])
    return serialize_signoff(record, freshness)


def list_signoffs(
    status: str | None = None,
    user: User = Depends(require_permission("signoffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    records = signoff_service.list_records(db, status)
    items = [_serialize(db, record) for record in records]
    return {"items": items, "total": len(items)}


def get_signoff(
    signoff_id: int,
    user: User = Depends(require_permission("signoffs:read")),
    db: Session = Depends(get_db),
) -> dict:
    return _serialize(db, signoff_service.get_record(db, signoff_id))


def create_signoff(
    payload: SignoffCreateRequest,
    request: Request,
    user: User = Depends(require_permission("signoffs:create")),
    db: Session = Depends(get_db),
) -> dict:
    record = signoff_service.create_draft(db, payload.batch_ids, payload.title, payload.note, user)
    write_audit(
        db,
        request,
        action="signoff.create",
        entity_type="SignoffRecord",
        entity_id=str(record.id),
        user=user,
        payload={"signoff_no": record.signoff_no, "batch_ids": record.batch_ids},
    )
    return _serialize(db, record)


def refresh_signoff(
    signoff_id: int,
    request: Request,
    user: User = Depends(require_permission("signoffs:create")),
    db: Session = Depends(get_db),
) -> dict:
    record = signoff_service.refresh_draft(db, signoff_service.get_record(db, signoff_id))
    write_audit(
        db,
        request,
        action="signoff.refresh",
        entity_type="SignoffRecord",
        entity_id=str(record.id),
        user=user,
        payload={"signoff_no": record.signoff_no},
    )
    return _serialize(db, record)


def sign_signoff(
    signoff_id: int,
    payload: SignoffSignRequest,
    request: Request,
    user: User = Depends(require_permission("signoffs:sign")),
    db: Session = Depends(get_db),
) -> dict:
    record = signoff_service.sign(db, signoff_service.get_record(db, signoff_id), payload.note, user)
    write_audit(
        db,
        request,
        action="signoff.sign",
        entity_type="SignoffRecord",
        entity_id=str(record.id),
        user=user,
        payload={"signoff_no": record.signoff_no, "note": payload.note},
    )
    return _serialize(db, record)


def resign_signoff(
    signoff_id: int,
    request: Request,
    user: User = Depends(require_permission("signoffs:create")),
    db: Session = Depends(get_db),
) -> dict:
    source = signoff_service.get_record(db, signoff_id)
    record = signoff_service.resign(db, source, user)
    write_audit(
        db,
        request,
        action="signoff.resign",
        entity_type="SignoffRecord",
        entity_id=str(record.id),
        user=user,
        payload={"new_signoff_no": record.signoff_no, "source_signoff_id": source.id},
    )
    return _serialize(db, record)


def export_signoff_csv(
    signoff_id: int,
    user: User = Depends(require_permission("exports:read")),
    db: Session = Depends(get_db),
) -> Response:
    record = signoff_service.get_record(db, signoff_id)
    payload = _serialize(db, record)
    snapshot = payload["snapshot_json"]
    freshness = payload["freshness"] or {}
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, lineterminator="\n")

    writer.writerow(["签核底稿编号", record.signoff_no])
    writer.writerow(["标题", record.title])
    writer.writerow(["状态", record.status])
    writer.writerow(["材料新鲜度", freshness.get("freshness", "")])
    for reason in freshness.get("stale_reasons", []):
        writer.writerow(["过期材料", reason.get("label", reason.get("reason")), reason.get("detail")])
    writer.writerow(["签核时间", record.signed_at.isoformat() if record.signed_at else ""])
    writer.writerow([])

    writer.writerow(["批次号", "状态", "表对", "桶数", "抽样率%", "不一致桶", "差异行数", "完成时间"])
    for batch in snapshot.get("batches", []):
        writer.writerow(
            [
                batch["batch_no"],
                batch["status"],
                " / ".join(batch["pair_codes"]),
                batch["bucket_count"],
                batch["sample_rate"],
                batch["buckets_mismatched"],
                batch["diff_count"],
                batch.get("finished_at") or "",
            ]
        )
    writer.writerow([])

    writer.writerow(["可验收/阻塞", "表对", "核心表", "差异总数", "已豁免", "阻塞差异"])
    for verdict in snapshot.get("pair_verdicts", []):
        writer.writerow(
            [
                "可验收" if verdict["verdict"] == "acceptable" else "阻塞",
                verdict["pair_code"],
                "是" if verdict["is_core"] else "否",
                verdict["diff_total"],
                verdict["exempted_count"],
                verdict["blocking_count"],
            ]
        )
    writer.writerow([])

    writer.writerow(["修复单号", "标题", "豁免差异数", "表对分布", "类型分布", "审批时间"])
    for exemption in snapshot.get("exemptions", []):
        writer.writerow(
            [
                exemption["ticket_no"],
                exemption["title"],
                exemption["exempted_diff_count"],
                " / ".join(f"{k}:{v}" for k, v in exemption["by_pair"].items()),
                " / ".join(f"{k}:{v}" for k, v in exemption["by_type"].items()),
                exemption.get("decided_at") or "",
            ]
        )
    writer.writerow([])

    writer.writerow(["阻塞差异ID", "批次ID", "表对", "字段", "主键", "差异类型", "桶号"])
    for diff in snapshot.get("blocking_diffs", []):
        writer.writerow(
            [
                diff["diff_id"],
                diff["batch_id"],
                diff["pair_code"],
                diff["field_name"],
                diff["primary_key_value"],
                diff["diff_type"],
                diff["bucket_no"],
            ]
        )

    return Response(
        content=buffer.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="paritycheck-signoff-{signoff_id}.csv"'},
    )
