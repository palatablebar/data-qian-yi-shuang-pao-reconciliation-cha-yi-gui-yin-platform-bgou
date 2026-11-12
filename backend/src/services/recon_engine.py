"""算法 A · 分桶对账（recon_engine）。

输入：批次（表对集合、时间窗、桶数 N∈{64,128,256}、抽样率）。
步骤：
1. 主键 → 稳定哈希：bucket = int(md5(pk)[:8], 16) mod N，跨表对共用同一桶空间；
2. 每桶计算 count 与多列 checksum：行级 h = md5('|'.join(列值规范化))，
   桶级 checksum = sum(int(h[:8], 16)) mod 2^32（可复现、与行序无关）；
3. 桶内 count 与 checksum 都相等 → match（跳过，不抽样）；
4. 不一致桶：缺失/多出行按主键行集比对必然暴露（全量），字段级值差异按抽样率
   由 int(md5(pk + '#sample')[:8], 16) % 100 < 抽样率 命中后下钻到 diff_engine；
5. 输出桶矩阵、跳过率 = match 桶数 / 总桶数，并估算全量扫描成本 = 桶数 × 单桶平均耗时。

失败态：源表主键含 NULL → 批次 failed，reason=null_primary_key；
空桶（0/0）记 empty，不计不一致；主键重复在 diff_engine 中标 duplicate_key（不参与相似度）。
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.database import session_scope
from src.constants.enums import BatchStatus, BucketStatus, FailureReason
from src.models.base import now
from src.models.catalog import TablePair
from src.models.demo_tables import DEMO_TABLES
from src.models.recon import BucketResult, ReconBatch
from src.models.trace import DiffDetail
from src.services import audit_service, diff_engine
from src.utils.hashing import bucket_index, checksum_int, is_sampled, row_checksum
from src.utils.logger import get_logger

MOD32 = 1 << 32
logger = get_logger("paritycheck.recon_engine")


@dataclass
class BucketStat:
    src_count: int = 0
    tgt_count: int = 0
    src_sum: int = 0
    tgt_sum: int = 0
    pair_stats: dict[str, dict[str, int]] = field(default_factory=dict)

    def pair(self, code: str) -> dict[str, int]:
        if code not in self.pair_stats:
            self.pair_stats[code] = {"src_count": 0, "tgt_count": 0, "src_sum": 0, "tgt_sum": 0}
        return self.pair_stats[code]


def _timestamp_column(columns: list[str]) -> str | None:
    for name in ("created_at", "paid_at"):
        if name in columns:
            return name
    return None


def load_pair_rows(db: Session, pair: TablePair, window_days: int) -> dict[str, Any]:
    """读取一个表对在时间窗内的源行/目标行（只要 field_rules 里的列）。"""
    src_table = DEMO_TABLES[pair.src_table]
    tgt_table = DEMO_TABLES[pair.tgt_table]
    columns = [str(rule["name"]) for rule in pair.field_rules or []]
    ts_column = _timestamp_column(columns)
    cutoff = datetime.now() - timedelta(days=window_days)

    src_stmt = select(*[src_table.c[name] for name in columns])
    tgt_stmt = select(*[tgt_table.c[name] for name in columns])
    if ts_column:
        src_stmt = src_stmt.where(src_table.c[ts_column] >= cutoff)
        tgt_stmt = tgt_stmt.where(tgt_table.c[ts_column] >= cutoff)

    src_rows = [dict(row._mapping) for row in db.execute(src_stmt).all()]
    tgt_rows = [dict(row._mapping) for row in db.execute(tgt_stmt).all()]
    return {
        "pair": pair,
        "columns": columns,
        "src_rows": src_rows,
        "tgt_rows": tgt_rows,
    }


def _mark_failed(db: Session, batch: ReconBatch, reason: str, detail: dict[str, Any] | None = None) -> None:
    batch.status = BatchStatus.FAILED.value
    batch.failure_reason = reason
    batch.finished_at = now()
    if detail:
        batch.params_json = {**(batch.params_json or {}), "failure_detail": detail}
    db.commit()
    audit_service.record(
        db,
        action="batch.failed",
        entity_type="ReconBatch",
        entity_id=str(batch.id),
        actor_id=batch.created_by,
        actor_kind="system",
        payload={"reason": reason, "detail": detail or {}},
    )
    logger.warning("batch failed batch_id=%s reason=%s", batch.id, reason)


def _pair_bucket_status(pair_stat: dict[str, int] | None) -> str:
    if not pair_stat or (pair_stat["src_count"] == 0 and pair_stat["tgt_count"] == 0):
        return BucketStatus.EMPTY.value
    if pair_stat["src_count"] == pair_stat["tgt_count"] and pair_stat["src_sum"] == pair_stat["tgt_sum"]:
        return BucketStatus.MATCH.value
    return BucketStatus.MISMATCH.value


def _drill_bucket(
    pair: TablePair,
    columns: list[str],
    src_rows: list[dict[str, Any]],
    tgt_rows: list[dict[str, Any]],
    *,
    bucket_no: int,
    sample_rate: int,
) -> list[dict[str, Any]]:
    """不一致桶下钻：缺失/多出行全量暴露；值差异按确定性抽样率抽行做字段级 diff。"""
    pk_name = pair.primary_key
    src_map: dict[str, dict[str, Any]] = {}
    tgt_map: dict[str, dict[str, Any]] = {}
    duplicates: list[tuple[str, str]] = []

    for row in src_rows:
        key = str(row.get(pk_name))
        if key in src_map:
            duplicates.append((key, "src"))
        else:
            src_map[key] = row
    for row in tgt_rows:
        key = str(row.get(pk_name))
        if key in tgt_map:
            duplicates.append((key, "tgt"))
        else:
            tgt_map[key] = row

    diffs: list[dict[str, Any]] = []
    for key, row in src_map.items():
        if key not in tgt_map:
            diffs.append(diff_engine.missing_row_diff(pair, key, bucket_no=bucket_no))
            continue
        if not is_sampled(key, sample_rate):
            continue
        diffs.extend(diff_engine.compare_rows(pair, row, tgt_map[key], bucket_no=bucket_no))
    for key in tgt_map:
        if key not in src_map:
            diffs.append(diff_engine.missing_row_diff(pair, key, bucket_no=bucket_no, extra=True))
    seen: set[tuple[str, str]] = set()
    for key, side in duplicates:
        if (key, side) in seen:
            continue
        seen.add((key, side))
        diffs.append(diff_engine.duplicate_key_diff(pair, key, bucket_no=bucket_no, side=side))
    return diffs


def run_batch(batch_id: int, bucket_limit: int | None = None) -> dict[str, Any]:
    """执行一个批次（Celery worker / seed 同步调用共用）。bucket_limit 用于演示 running 状态。"""
    started_at = time.perf_counter()
    with session_scope() as db:
        batch = db.get(ReconBatch, batch_id)
        if batch is None:
            return {"ok": False, "reason": "batch_not_found", "batch_id": batch_id}
        if batch.status == BatchStatus.COMPLETED.value:
            return {"ok": True, "batch_id": batch.id, "status": batch.status, "idempotent": True}

        pairs = db.query(TablePair).filter(TablePair.code.in_(batch.pair_codes or [])).all()
        if not pairs:
            _mark_failed(db, batch, "no_pairs")
            return {"ok": False, "reason": "no_pairs", "batch_id": batch.id}

        batch.status = BatchStatus.RUNNING.value
        batch.started_at = batch.started_at or now()
        batch.failure_reason = None
        db.commit()

        loaded: list[dict[str, Any]] = []
        for pair in pairs:
            if pair.status != "active":
                _mark_failed(db, batch, "pair_inactive", {"pair_code": pair.code})
                return {"ok": False, "reason": "pair_inactive", "batch_id": batch.id}
            data = load_pair_rows(db, pair, batch.window_days)
            null_rows = [row for row in data["src_rows"] if row.get(pair.primary_key) is None]
            if null_rows:
                logger.warning("null primary key detected pair=%s rows=%s", pair.code, len(null_rows))
                _mark_failed(
                    db,
                    batch,
                    FailureReason.NULL_PRIMARY_KEY.value,
                    {"pair_code": pair.code, "null_rows": len(null_rows)},
                )
                return {
                    "ok": False,
                    "reason": FailureReason.NULL_PRIMARY_KEY.value,
                    "pair_code": pair.code,
                    "null_rows": len(null_rows),
                    "batch_id": batch.id,
                }
            loaded.append(data)

        total_buckets = batch.bucket_count if bucket_limit is None else min(bucket_limit, batch.bucket_count)
        stats: dict[int, BucketStat] = defaultdict(BucketStat)
        pair_rows: dict[str, dict[str, dict[int, list[dict[str, Any]]]]] = {}

        for data in loaded:
            pair: TablePair = data["pair"]
            columns: list[str] = data["columns"]
            src_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
            tgt_buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in data["src_rows"]:
                bucket = bucket_index(row[pair.primary_key], batch.bucket_count)
                if bucket >= total_buckets:
                    continue
                row_hash = checksum_int(row_checksum([row[name] for name in columns]))
                stat = stats[bucket]
                stat.src_count += 1
                stat.src_sum = (stat.src_sum + row_hash) % MOD32
                pair_stat = stat.pair(pair.code)
                pair_stat["src_count"] += 1
                pair_stat["src_sum"] = (pair_stat["src_sum"] + row_hash) % MOD32
                src_buckets[bucket].append(row)
            for row in data["tgt_rows"]:
                bucket = bucket_index(row[pair.primary_key], batch.bucket_count)
                if bucket >= total_buckets:
                    continue
                row_hash = checksum_int(row_checksum([row[name] for name in columns]))
                stat = stats[bucket]
                stat.tgt_count += 1
                stat.tgt_sum = (stat.tgt_sum + row_hash) % MOD32
                pair_stat = stat.pair(pair.code)
                pair_stat["tgt_count"] += 1
                pair_stat["tgt_sum"] = (pair_stat["tgt_sum"] + row_hash) % MOD32
                tgt_buckets[bucket].append(row)
            pair_rows[pair.code] = {"src": src_buckets, "tgt": tgt_buckets}

        bucket_results: list[BucketResult] = []
        diff_payloads: list[dict[str, Any]] = []
        matched = mismatched = empty = 0
        src_total = tgt_total = 0
        bucket_elapsed: list[float] = []

        for bucket_no in range(total_buckets):
            tick = time.perf_counter()
            stat = stats.get(bucket_no) or BucketStat()
            bucket_status = BucketStatus.EMPTY.value
            breakdown: list[dict[str, Any]] = []
            for data in loaded:
                pair: TablePair = data["pair"]
                pair_stat = stat.pair_stats.get(pair.code)
                p_status = _pair_bucket_status(pair_stat)
                if p_status == BucketStatus.MISMATCH.value:
                    bucket_status = BucketStatus.MISMATCH.value
                    diff_payloads.extend(
                        _drill_bucket(
                            pair,
                            data["columns"],
                            pair_rows[pair.code]["src"].get(bucket_no, []),
                            pair_rows[pair.code]["tgt"].get(bucket_no, []),
                            bucket_no=bucket_no,
                            sample_rate=batch.sample_rate,
                        )
                    )
                elif p_status == BucketStatus.MATCH.value and bucket_status == BucketStatus.EMPTY.value:
                    bucket_status = BucketStatus.MATCH.value
                if pair_stat:
                    breakdown.append(
                        {
                            "pair_code": pair.code,
                            "src_count": pair_stat["src_count"],
                            "tgt_count": pair_stat["tgt_count"],
                            "src_checksum": pair_stat["src_sum"],
                            "tgt_checksum": pair_stat["tgt_sum"],
                            "status": p_status,
                        }
                    )

            if bucket_status == BucketStatus.MATCH.value:
                matched += 1
            elif bucket_status == BucketStatus.MISMATCH.value:
                mismatched += 1
            else:
                empty += 1
            src_total += stat.src_count
            tgt_total += stat.tgt_count
            bucket_elapsed.append((time.perf_counter() - tick) * 1000)
            bucket_results.append(
                BucketResult(
                    batch_id=batch.id,
                    bucket_no=bucket_no,
                    src_count=stat.src_count,
                    tgt_count=stat.tgt_count,
                    src_checksum=stat.src_sum % MOD32,
                    tgt_checksum=stat.tgt_sum % MOD32,
                    status=bucket_status,
                    pair_breakdown=breakdown,
                    compared_rows=0,
                    elapsed_ms=int(bucket_elapsed[-1]),
                )
            )

        # 幂等：重跑时先清掉旧结果
        db.query(BucketResult).filter(BucketResult.batch_id == batch.id).delete()
        db.query(DiffDetail).filter(DiffDetail.batch_id == batch.id).delete()
        db.flush()
        for item in bucket_results:
            db.add(item)
        for payload in diff_payloads:
            db.add(
                DiffDetail(
                    batch_id=batch.id,
                    bucket_no=payload["bucket_no"],
                    pair_code=payload["pair_code"],
                    primary_key_value=payload["primary_key_value"],
                    field_name=payload["field_name"],
                    src_value=payload["src_value"],
                    tgt_value=payload["tgt_value"],
                    diff_type=payload["diff_type"],
                    similarity=Decimal(str(payload["similarity"])),
                    attribution=payload["attribution"],
                    suggestion=payload["suggestion"],
                )
            )

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        avg_bucket_ms = elapsed_ms / total_buckets if total_buckets else 0.0
        skip_rate = round(matched / total_buckets * 100, 2) if total_buckets else 0.0
        finished = bucket_limit is None
        batch.buckets_total = batch.bucket_count
        batch.buckets_matched = matched
        batch.buckets_mismatched = mismatched
        batch.buckets_empty = empty
        batch.src_rows = src_total
        batch.tgt_rows = tgt_total
        batch.skip_rate = Decimal(str(skip_rate))
        batch.diff_count = len(diff_payloads)
        batch.status = BatchStatus.COMPLETED.value if finished else BatchStatus.RUNNING.value
        batch.finished_at = now() if finished else None
        batch.scan_cost_json = {
            "computed_buckets": total_buckets,
            "time_window_days": batch.window_days,
            "elapsed_ms": round(elapsed_ms, 1),
            "avg_bucket_ms": round(avg_bucket_ms, 3),
            "estimated_full_scan_ms": round(avg_bucket_ms * batch.bucket_count, 1),
            "skipped_buckets": matched,
            "skip_rate_pct": skip_rate,
            "diff_types": diff_engine.summarize_types(diff_payloads),
        }
        batch.params_json = {
            **(batch.params_json or {}),
            "engine": "bucket_md5_checksum_v1",
            "bucket_formula": "int(md5(pk)[:8],16) mod N",
            "checksum_formula": "sum(int(md5(row)[:8],16)) mod 2^32",
            "sample_formula": "int(md5(pk+'#sample')[:8],16) % 100 < sample_rate",
        }
        db.commit()
        if finished:
            audit_service.record(
                db,
                action="batch.completed",
                entity_type="ReconBatch",
                entity_id=str(batch.id),
                actor_id=batch.created_by,
                actor_kind="system",
                payload={
                    "buckets": total_buckets,
                    "mismatched": mismatched,
                    "skip_rate": skip_rate,
                    "diffs": len(diff_payloads),
                },
            )
        logger.info(
            "batch run batch_id=%s buckets=%s mismatched=%s skip_rate=%s diffs=%s elapsed_ms=%.1f",
            batch.id,
            total_buckets,
            mismatched,
            skip_rate,
            len(diff_payloads),
            elapsed_ms,
        )
        return {
            "ok": True,
            "batch_id": batch.id,
            "status": batch.status,
            "buckets": total_buckets,
            "matched": matched,
            "mismatched": mismatched,
            "empty": empty,
            "skip_rate": skip_rate,
            "diffs": len(diff_payloads),
            "elapsed_ms": round(elapsed_ms, 1),
        }


def estimate_scan_cost(db: Session, pair_codes: list[str], bucket_count: int, sample_rate: int) -> dict[str, Any]:
    """批次创建页的预估：行数、桶数、预计抽样行数、按历史批次均速估算扫描耗时。"""
    pairs = db.query(TablePair).filter(TablePair.code.in_(pair_codes)).all()
    src_rows = sum(pair.row_estimate_src for pair in pairs)
    tgt_rows = sum(pair.row_estimate_tgt for pair in pairs)
    estimated_scan_ms = 0.0
    last_batch = (
        db.query(ReconBatch)
        .filter(ReconBatch.status == BatchStatus.COMPLETED.value)
        .order_by(ReconBatch.id.desc())
        .first()
    )
    if last_batch and last_batch.scan_cost_json:
        avg_bucket_ms = float(last_batch.scan_cost_json.get("avg_bucket_ms", 0) or 0)
        estimated_scan_ms = round(avg_bucket_ms * bucket_count, 1)
    return {
        "pair_count": len(pairs),
        "bucket_count": bucket_count,
        "sample_rate": sample_rate,
        "src_rows": src_rows,
        "tgt_rows": tgt_rows,
        "rows_per_bucket": round((src_rows + tgt_rows) / bucket_count, 1) if bucket_count else 0,
        "estimated_sampled_rows": int(round(src_rows * sample_rate / 100)),
        "estimated_scan_ms": estimated_scan_ms,
        "source_batch": last_batch.batch_no if last_batch else None,
    }
