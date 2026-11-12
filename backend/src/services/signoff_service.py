"""签核底稿服务：冻结快照生成 / 签核通过校验 / 新鲜度（过期材料）实时计算。

核心规则（需求对应）：
1. 选择覆盖核心表的「已完成」批次生成冻结记录，快照列明可验收表、阻塞差异、已准确豁免差异；
2. 已签记录不被后续变化改写（snapshot_json 只在生成/签核/刷新草稿时写入）；
   新鲜度读时用「冻结指纹 vs 当前指纹」实时计算，提示哪项材料过期、需重签；
3. 相同批次组合重复运行不新增签核记录（同组合有草稿直接返回；已签则 409 引导重签）；
4. 核心表未覆盖或仍有未豁免差异不能通过签核。
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.constants import error_codes as codes
from src.constants.enums import (
    SIGNOFF_FRESH,
    SIGNOFF_STALE,
    STALE_BATCH_RERUN,
    STALE_BATCH_STATUS,
    STALE_DIFF_UNEXEMPTED,
    STALE_PAIR_CORE_CHANGED,
    STALE_TICKET_CHANGED,
    STALE_TICKET_NEW,
    SignoffStatus,
    TicketStatus,
)
from src.models.account import User
from src.models.base import now
from src.models.catalog import TablePair
from src.models.recon import ReconBatch
from src.models.signoff import SignoffRecord
from src.models.trace import DiffDetail, RepairTicket
from src.utils.errors import AppError
from src.utils.logger import get_logger

logger = get_logger("paritycheck.signoff_service")


# ---------------------------------------------------------------- 工具函数 ----
def batch_set_hash(batch_ids: list[int]) -> str:
    canonical = ",".join(str(i) for i in sorted(set(batch_ids)))
    return hashlib.sha256(f"batch-set:{canonical}".encode("utf-8")).hexdigest()


def _next_signoff_no(db: Session) -> str:
    prefix = f"SO-{datetime.now():%Y%m%d}-"
    last = (
        db.query(SignoffRecord)
        .filter(SignoffRecord.signoff_no.like(f"{prefix}%"))
        .order_by(SignoffRecord.id.desc())
        .first()
    )
    sequence = 1
    if last is not None:
        try:
            sequence = int(last.signoff_no.rsplit("-", 1)[1]) + 1
        except (IndexError, ValueError):
            sequence = db.query(SignoffRecord).count() + 1
    return f"{prefix}{sequence:04d}"


def _batch_fingerprint(batch: ReconBatch, diffs: list[DiffDetail]) -> str:
    """批次材料指纹：批次状态/桶统计/差异集合。重跑会改写 diff 行（先删后插），指纹必变。"""
    diff_keys = sorted(f"{d.pair_code}|{d.field_name}|{d.diff_type}|{d.primary_key_value}" for d in diffs)
    payload = "|".join(
        [
            f"status={batch.status}",
            f"buckets={batch.buckets_total}/{batch.buckets_matched}/{batch.buckets_mismatched}/{batch.buckets_empty}",
            f"rows={batch.src_rows}/{batch.tgt_rows}",
            f"diff_count={batch.diff_count}",
            f"skip_rate={float(batch.skip_rate or 0)}",
            f"finished={batch.finished_at.isoformat() if batch.finished_at else ''}",
            "diffs=" + ";".join(diff_keys),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ticket_fingerprint(ticket: RepairTicket) -> str:
    scope = ticket.diff_scope_json or {}
    diff_ids = sorted(int(i) for i in scope.get("diff_ids", []))
    payload = "|".join(
        [
            f"no={ticket.ticket_no}",
            f"status={ticket.status}",
            f"diff_count={ticket.diff_count}",
            f"ids={','.join(str(i) for i in diff_ids)}",
            f"decided_at={ticket.decided_at.isoformat() if ticket.decided_at else ''}",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _approved_tickets_for(db: Session, batch_ids: list[int]) -> list[RepairTicket]:
    """覆盖所选批次差异的已审批修复单（含 batch_id 直接关联与 diff 行落在批次内两种情况）。"""
    if not batch_ids:
        return []
    linked = (
        db.query(RepairTicket)
        .filter(
            RepairTicket.status == TicketStatus.APPROVED.value,
            RepairTicket.batch_id.in_(batch_ids),
        )
        .all()
    )
    # 显式查「修复单 scope 中的 diff_id 落在所选批次」的修复单，覆盖未填 batch_id 的历史单
    batch_diff_ids = {
        row[0] for row in db.query(DiffDetail.id).filter(DiffDetail.batch_id.in_(batch_ids)).all()
    }
    scope_only: list[RepairTicket] = []
    if batch_diff_ids:
        candidates = (
            db.query(RepairTicket)
            .filter(RepairTicket.status == TicketStatus.APPROVED.value)
            .all()
        )
        linked_ids = {ticket.id for ticket in linked}
        scope_only = [
            ticket
            for ticket in candidates
            if ticket.id not in linked_ids
            and set((ticket.diff_scope_json or {}).get("diff_ids", [])) & batch_diff_ids
        ]
    tickets = {t.id: t for t in linked + scope_only}
    return sorted(tickets.values(), key=lambda t: t.id)


# ---------------------------------------------------------------- 快照构建 ----
def build_snapshot(db: Session, batch_ids: list[int]) -> dict[str, Any]:
    """读当前库实时构建冻结快照 + 签核校验结论。纯读操作，不落库。"""
    ordered_ids = sorted(set(batch_ids))
    batches = [db.get(ReconBatch, bid) for bid in ordered_ids]
    batches = [b for b in batches if b is not None]
    if len(batches) != len(ordered_ids):
        found = {b.id for b in batches}
        missing = [bid for bid in ordered_ids if bid not in found]
        raise AppError(codes.NOT_FOUND, "批次不存在", f"missing_batch_ids={missing}")

    not_completed = [b.batch_no for b in batches if b.status != "completed"]
    if not_completed:
        raise AppError(
            codes.SIGNOFF_BATCH_NOT_COMPLETED,
            "只有已完成批次可以进入签核底稿",
            f"not_completed={not_completed}",
        )

    diffs = (
        db.query(DiffDetail)
        .filter(DiffDetail.batch_id.in_(ordered_ids))
        .order_by(DiffDetail.id.asc())
        .all()
    )
    tickets = _approved_tickets_for(db, ordered_ids)

    # diff_id -> 豁免它的已审批修复单（一个 diff 可能被多张单覆盖，全部记录）
    exempt_map: dict[int, list[RepairTicket]] = defaultdict(list)
    ticket_diff_ids: dict[int, set[int]] = {}
    for ticket in tickets:
        ids = set(int(i) for i in (ticket.diff_scope_json or {}).get("diff_ids", []))
        ticket_diff_ids[ticket.id] = ids
        for diff_id in ids:
            exempt_map[diff_id].append(ticket)

    blocking: list[DiffDetail] = []
    for diff in diffs:
        if not exempt_map.get(diff.id):
            blocking.append(diff)

    core_pairs = db.query(TablePair).filter(TablePair.is_core.is_(True)).all()
    all_pairs = {pair.code: pair for pair in db.query(TablePair).all()}
    covered_codes = {code for batch in batches for code in (batch.pair_codes or [])}
    core_codes = {pair.code for pair in core_pairs}
    uncovered_core = sorted(core_codes - covered_codes)

    # 表对级结论：覆盖到的表对按「是否还有未豁免差异」判可验收/阻塞
    pair_verdicts: list[dict[str, Any]] = []
    blocking_by_pair: dict[str, list[DiffDetail]] = defaultdict(list)
    for diff in blocking:
        blocking_by_pair[diff.pair_code].append(diff)
    for code in sorted(covered_codes):
        pair = all_pairs.get(code)
        pair_blocking = blocking_by_pair.get(code, [])
        pair_diffs = [d for d in diffs if d.pair_code == code]
        pair_exempt = [d for d in pair_diffs if exempt_map.get(d.id)]
        pair_verdicts.append(
            {
                "pair_code": code,
                "display_name": pair.display_name if pair else code,
                "is_core": bool(pair.is_core) if pair else False,
                "verdict": "blocked" if pair_blocking else "acceptable",
                "diff_total": len(pair_diffs),
                "exempted_count": len(pair_exempt),
                "blocking_count": len(pair_blocking),
            }
        )

    # 已准确豁免差异：按修复单分组，只统计实际落在所选批次内的 diff
    exemptions: list[dict[str, Any]] = []
    for ticket in tickets:
        in_scope_ids = ticket_diff_ids[ticket.id] & {d.id for d in diffs}
        in_scope_diffs = [d for d in diffs if d.id in in_scope_ids]
        by_pair: dict[str, int] = defaultdict(int)
        by_type: dict[str, int] = defaultdict(int)
        for diff in in_scope_diffs:
            by_pair[diff.pair_code] += 1
            by_type[diff.diff_type] += 1
        exemptions.append(
            {
                "ticket_id": ticket.id,
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "status": ticket.status,
                "approver_id": ticket.approver_id,
                "decided_at": ticket.decided_at.isoformat() if ticket.decided_at else None,
                "exempted_diff_count": len(in_scope_diffs),
                "by_pair": dict(sorted(by_pair.items())),
                "by_type": dict(sorted(by_type.items())),
                "diff_ids": sorted(in_scope_ids),
            }
        )

    blocking_items = [
        {
            "diff_id": diff.id,
            "batch_id": diff.batch_id,
            "pair_code": diff.pair_code,
            "field_name": diff.field_name,
            "primary_key_value": diff.primary_key_value,
            "diff_type": diff.diff_type,
            "bucket_no": diff.bucket_no,
        }
        for diff in blocking
    ]

    frozen_batches = []
    for batch in batches:
        batch_diffs = [d for d in diffs if d.batch_id == batch.id]
        frozen_batches.append(
            {
                "batch_id": batch.id,
                "batch_no": batch.batch_no,
                "status": batch.status,
                "pair_codes": list(batch.pair_codes or []),
                "bucket_count": batch.bucket_count,
                "sample_rate": batch.sample_rate,
                "window_days": batch.window_days,
                "buckets_matched": batch.buckets_matched,
                "buckets_mismatched": batch.buckets_mismatched,
                "diff_count": batch.diff_count,
                "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
                "fingerprint": _batch_fingerprint(batch, batch_diffs),
            }
        )

    frozen_tickets = [
        {
            "ticket_id": ticket.id,
            "ticket_no": ticket.ticket_no,
            "status": ticket.status,
            "fingerprint": _ticket_fingerprint(ticket),
        }
        for ticket in tickets
    ]
    frozen_core_codes = sorted(core_codes)

    validation = {
        "passable": not uncovered_core and not blocking,
        "blocking_reasons": [
            *(["core_not_covered"] if uncovered_core else []),
            *(["has_unexempted_diff"] if blocking else []),
        ],
        "uncovered_core_pairs": uncovered_core,
        "blocking_diff_count": len(blocking),
        "exempted_diff_count": sum(item["exempted_diff_count"] for item in exemptions),
        "checked_at": now().isoformat(),
    }

    return {
        "frozen_at": now().isoformat(),
        "batch_ids": ordered_ids,
        "batches": frozen_batches,
        "core_pair_codes": frozen_core_codes,
        "covered_pair_codes": sorted(covered_codes),
        "pair_verdicts": pair_verdicts,
        "acceptable_pair_codes": [v["pair_code"] for v in pair_verdicts if v["verdict"] == "acceptable"],
        "blocking_diffs": blocking_items,
        "exemptions": exemptions,
        "ticket_fingerprints": frozen_tickets,
        "validation": validation,
    }


# ---------------------------------------------------------------- 新鲜度 ----
def evaluate_freshness(db: Session, record: SignoffRecord) -> dict[str, Any]:
    """读时实时比对：冻结指纹 vs 当前材料。已签记录快照本身永不改写。

    返回 {freshness, stale_reasons:[{reason, detail}]}；草稿同样计算（提示材料已变可刷新）。
    """
    snapshot = record.snapshot_json or {}
    stale_reasons: list[dict[str, Any]] = []
    frozen_batch_ids = list(snapshot.get("batch_ids", []) or record.batch_ids)

    # 1. 批次指纹 / 状态
    current_batches = {b.id: b for b in db.query(ReconBatch).filter(ReconBatch.id.in_(frozen_batch_ids)).all()}
    frozen_batches = {item["batch_id"]: item for item in snapshot.get("batches", [])}
    current_diff_cache: dict[int, list[DiffDetail]] = {}
    for bid in frozen_batch_ids:
        batch = current_batches.get(bid)
        frozen = frozen_batches.get(bid)
        if batch is None:
            stale_reasons.append({"reason": STALE_BATCH_STATUS, "detail": {"batch_id": bid, "issue": "missing"}})
            continue
        batch_diffs = (
            db.query(DiffDetail).filter(DiffDetail.batch_id == bid).order_by(DiffDetail.id.asc()).all()
        )
        current_diff_cache[bid] = batch_diffs
        if frozen is None:
            continue
        if batch.status != frozen.get("status"):
            stale_reasons.append(
                {
                    "reason": STALE_BATCH_STATUS,
                    "detail": {
                        "batch_id": bid,
                        "batch_no": batch.batch_no,
                        "frozen_status": frozen.get("status"),
                        "current_status": batch.status,
                    },
                }
            )
        current_fp = _batch_fingerprint(batch, batch_diffs)
        if current_fp != frozen.get("fingerprint"):
            # 重跑（finished_at/差异集合变化）优先标记为 batch_rerun
            reason = STALE_BATCH_RERUN if batch.status == "completed" else STALE_BATCH_STATUS
            stale_reasons.append(
                {
                    "reason": reason,
                    "detail": {
                        "batch_id": bid,
                        "batch_no": batch.batch_no,
                        "frozen_diff_count": frozen.get("diff_count"),
                        "current_diff_count": batch.diff_count,
                    },
                }
            )

    # 2. 核心表标记变化
    current_core = {
        pair.code for pair in db.query(TablePair).filter(TablePair.is_core.is_(True)).all()
    }
    frozen_core = set(snapshot.get("core_pair_codes", []))
    if current_core != frozen_core:
        stale_reasons.append(
            {
                "reason": STALE_PAIR_CORE_CHANGED,
                "detail": {
                    "added": sorted(current_core - frozen_core),
                    "removed": sorted(frozen_core - current_core),
                },
            }
        )

    # 3. 已引用修复单变更
    frozen_tickets = {item["ticket_id"]: item for item in snapshot.get("ticket_fingerprints", [])}
    for ticket_id, frozen in frozen_tickets.items():
        ticket = db.get(RepairTicket, ticket_id)
        if ticket is None:
            stale_reasons.append(
                {"reason": STALE_TICKET_CHANGED, "detail": {"ticket_id": ticket_id, "issue": "missing"}}
            )
            continue
        if _ticket_fingerprint(ticket) != frozen.get("fingerprint"):
            stale_reasons.append(
                {
                    "reason": STALE_TICKET_CHANGED,
                    "detail": {
                        "ticket_id": ticket_id,
                        "ticket_no": ticket.ticket_no,
                        "frozen_status": frozen.get("status"),
                        "current_status": ticket.status,
                    },
                }
            )

    # 4. 冻结后出现覆盖本批次的新已审批修复单
    current_tickets = _approved_tickets_for(db, frozen_batch_ids)
    new_tickets = [t for t in current_tickets if t.id not in frozen_tickets]
    if new_tickets:
        stale_reasons.append(
            {
                "reason": STALE_TICKET_NEW,
                "detail": {"ticket_nos": [t.ticket_no for t in new_tickets]},
            }
        )

    # 5. 未豁免差异：用当前库重算，与冻结阻塞清单比对新增项
    current_diffs = [d for bid in frozen_batch_ids for d in current_diff_cache.get(bid, [])]
    if frozen_batch_ids:
        tickets_now = _approved_tickets_for(db, frozen_batch_ids)
        exempt_ids: set[int] = set()
        for ticket in tickets_now:
            exempt_ids.update(int(i) for i in (ticket.diff_scope_json or {}).get("diff_ids", []))
        current_blocking = [d for d in current_diffs if d.id not in exempt_ids]
        frozen_blocking_ids = {item["diff_id"] for item in snapshot.get("blocking_diffs", [])}
        added_blocking = [d for d in current_blocking if d.id not in frozen_blocking_ids]
        if added_blocking:
            stale_reasons.append(
                {
                    "reason": STALE_DIFF_UNEXEMPTED,
                    "detail": {
                        "diff_ids": sorted(d.id for d in added_blocking),
                        "count": len(added_blocking),
                    },
                }
            )

    # 同一 reason 去重（保留首条 detail）
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in stale_reasons:
        if item["reason"] in seen:
            continue
        seen.add(item["reason"])
        deduped.append(item)

    return {
        "freshness": SIGNOFF_FRESH if not deduped else SIGNOFF_STALE,
        "stale_reasons": deduped,
        "evaluated_at": now().isoformat(),
    }


# ---------------------------------------------------------------- 写操作 ----
def _find_by_batch_set(db: Session, set_hash: str) -> list[SignoffRecord]:
    return (
        db.query(SignoffRecord)
        .filter(SignoffRecord.batch_set_hash == set_hash)
        .order_by(SignoffRecord.id.asc())
        .all()
    )


def create_draft(db: Session, batch_ids: list[int], title: str, note: str, user: User) -> SignoffRecord:
    """生成冻结底稿草稿。相同批次组合：有草稿直接返回（不新增）；已签则 409。"""
    if not batch_ids:
        raise AppError(codes.SIGNOFF_NO_BATCHES, "签核底稿必须至少选择一个批次", "batch_ids empty")
    set_hash = batch_set_hash(batch_ids)
    existing = _find_by_batch_set(db, set_hash)
    if existing:
        signed = next((r for r in existing if r.status == SignoffStatus.SIGNED.value), None)
        if signed is not None:
            raise AppError(
                codes.SIGNOFF_DUPLICATE_SIGNED,
                f"批次组合已签核（{signed.signoff_no}），材料变更请对该记录发起重签",
                extra={"existing_signoff_id": signed.id, "signoff_no": signed.signoff_no},
            )
        draft = next((r for r in existing if r.status == SignoffStatus.DRAFT.value), None)
        if draft is not None:
            logger.info("signoff draft idempotent hit signoff_id=%s", draft.id)
            return draft

    snapshot = build_snapshot(db, batch_ids)
    record = SignoffRecord(
        signoff_no=_next_signoff_no(db),
        title=title or f"验收签核底稿 · 批次 {len(snapshot['batch_ids'])} 个",
        batch_ids=snapshot["batch_ids"],
        batch_set_hash=set_hash,
        status=SignoffStatus.DRAFT.value,
        snapshot_json=snapshot,
        validation_json=snapshot["validation"],
        note=note,
        created_by=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info(
        "signoff draft created signoff_id=%s batches=%s passable=%s",
        record.id,
        record.batch_ids,
        snapshot["validation"]["passable"],
    )
    return record


def refresh_draft(db: Session, record: SignoffRecord) -> SignoffRecord:
    """草稿允许按当前库重新冻结（已签记录拒绝，保证签后快照不可变）。"""
    if record.status != SignoffStatus.DRAFT.value:
        raise AppError(
            codes.SIGNOFF_INVALID_STATE,
            "只有草稿底稿可以刷新快照；已签记录请使用重签生成新底稿",
            f"status={record.status}",
        )
    snapshot = build_snapshot(db, record.batch_ids)
    record.snapshot_json = snapshot
    record.validation_json = snapshot["validation"]
    db.commit()
    db.refresh(record)
    return record


def sign(db: Session, record: SignoffRecord, sign_note: str, user: User) -> SignoffRecord:
    """签核通过：实时重算校验，核心表未覆盖或存在未豁免差异一律拒绝。"""
    if record.status != SignoffStatus.DRAFT.value:
        raise AppError(
            codes.SIGNOFF_INVALID_STATE,
            "只有草稿底稿可以签核",
            f"status={record.status} signoff_id={record.id}",
        )
    snapshot = build_snapshot(db, record.batch_ids)
    validation = snapshot["validation"]
    if validation["uncovered_core_pairs"]:
        raise AppError(
            codes.SIGNOFF_CORE_NOT_COVERED,
            f"核心表未全部覆盖：{', '.join(validation['uncovered_core_pairs'])}",
            f"uncovered={validation['uncovered_core_pairs']}",
            extra={"uncovered": validation["uncovered_core_pairs"]},
        )
    if validation["blocking_diff_count"] > 0:
        sample = snapshot["blocking_diffs"][:10]
        raise AppError(
            codes.SIGNOFF_HAS_UNEXEMPTED_DIFF,
            f"仍有 {validation['blocking_diff_count']} 条未豁免差异，不能通过签核",
            f"blocking_diff_count={validation['blocking_diff_count']}",
            extra={"sample": sample},
        )
    # 通过校验：以签核时刻材料重新冻结一次并落库，之后不再改写
    record.snapshot_json = snapshot
    record.validation_json = validation
    record.status = SignoffStatus.SIGNED.value
    record.signed_by = user.id
    record.signed_at = now()
    record.sign_note = sign_note
    db.commit()
    db.refresh(record)
    logger.info("signoff signed signoff_id=%s by=%s", record.id, user.id)
    return record


def resign(db: Session, record: SignoffRecord, user: User) -> SignoffRecord:
    """对已签记录发起重签：原记录保留不动（审计留痕），按同批次组合生成新草稿。"""
    if record.status != SignoffStatus.SIGNED.value:
        raise AppError(
            codes.SIGNOFF_INVALID_STATE,
            "只有已签核记录可以发起重签",
            f"status={record.status} signoff_id={record.id}",
        )
    snapshot = build_snapshot(db, record.batch_ids)
    new_record = SignoffRecord(
        signoff_no=_next_signoff_no(db),
        title=f"{record.title}（重签）",
        batch_ids=snapshot["batch_ids"],
        batch_set_hash=record.batch_set_hash,
        status=SignoffStatus.DRAFT.value,
        snapshot_json=snapshot,
        validation_json=snapshot["validation"],
        note=record.note,
        created_by=user.id,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    logger.info(
        "signoff resign new_id=%s from_signed_id=%s stale=%s",
        new_record.id,
        record.id,
        evaluate_freshness(db, record)["freshness"],
    )
    return new_record


def get_record(db: Session, signoff_id: int) -> SignoffRecord:
    record = db.get(SignoffRecord, signoff_id)
    if record is None:
        raise AppError(codes.NOT_FOUND, "签核底稿不存在", f"signoff_id={signoff_id}")
    return record


def list_records(db: Session, status: str | None = None) -> list[SignoffRecord]:
    query = db.query(SignoffRecord)
    if status:
        query = query.filter(SignoffRecord.status == status)
    return query.order_by(SignoffRecord.id.desc()).all()
