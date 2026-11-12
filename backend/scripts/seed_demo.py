"""幂等演示数据入口：`docker compose exec -T backend python -m scripts.seed_demo`。

模拟客户：明川银行 · 数据中台迁移组（11 人）。12 张核心表从 Oracle 19c 迁往 MySQL 8.0，
双跑 30 天验收。demo 在同一个 MySQL 库里用 src_* / tgt_* 两套表模拟双跑。

幂等策略：
- users / table_pairs 按自然键（email / pair.code）upsert，不覆盖用户改过的展示名；
- src_* / tgt_* 演示行：先校验行数是否符合预期，符合则跳过（不覆盖人工改动），否则整表重建；
- recon_batches 按 batch_no 跳过；repair_tickets 已存在则跳过；
- 结束时打印恰好一行 `SEED_SUMMARY k=v k=v ...`（键值顺序固定，两次运行逐字一致）。
"""
from __future__ import annotations

import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, insert, select

from src.config.database import SessionLocal, engine
from src.config.settings import settings
from src.constants.enums import (
    BatchStatus,
    DiffType,
    PairStatus,
    TicketStatus,
)
from src.constants.roles import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER
from src.models.account import User
from src.models.catalog import TablePair
from src.models.demo_tables import DEMO_TABLES
from src.models.recon import BucketResult, ReconBatch
from src.models.trace import DiffDetail, RepairTicket
from src.services import audit_service, auth_service, ticket_service
from src.services.recon_engine import run_batch
from src.utils.hashing import bucket_index, is_sampled

SEED_BATCH_DATE = "20261110"
BUCKET_COUNT = 128
TARGET_BUCKETS = (27, 51, 68, 94, 113)
REFUND_NULL_INDEX = 17

DEMO_PASSWORD = settings.demo_password
DEMO_USERS = [
    ("admin@paritycheck.demo", "明川银行 · 迁移负责人", ROLE_ADMIN),
    ("analyst@paritycheck.demo", "明川银行 · 数据开发", ROLE_ANALYST),
    ("viewer@paritycheck.demo", "明川银行 · 审计", ROLE_VIEWER),
]

# pair -> (src 行数, tgt 行数)
PAIR_SIZES = {
    "orders": (2600, 2596),
    "order_item": (3000, 2992),
    "customer": (2200, 2192),
    "payment": (2100, 2096),
    "refund": (2100, 2092),
}
# pair -> 目标缺失行数（refund 另有 1 行源端主键为 NULL，不下发目标端）
MISSING_PLAN = {
    "orders": 4,
    "order_item": 8,
    "customer": 8,
    "payment": 4,
    "refund": 7,
}

PRIMARY_KEYS = {
    "orders": "order_id",
    "order_item": "item_id",
    "customer": "customer_id",
    "payment": "payment_id",
    "refund": "refund_id",
}

PAIR_META = [
    {
        "code": "orders",
        "display_name": "订单主表",
        "src_table": "src_orders",
        "tgt_table": "tgt_orders",
        "owner": "迁移组 · 陈立",
        "description": "Oracle ORDERS → MySQL orders；双写延迟 P99 < 2s，主键 order_id。",
        "fields": [
            ("order_id", "string"),
            ("customer_id", "string"),
            ("order_no", "string"),
            ("amount", "numeric"),
            ("currency", "string"),
            ("status", "string"),
            ("created_at", "datetime"),
        ],
    },
    {
        "code": "order_item",
        "display_name": "订单行项目",
        "src_table": "src_order_item",
        "tgt_table": "tgt_order_item",
        "owner": "迁移组 · 陈立",
        "description": "Oracle ORDER_ITEM → MySQL order_item；qty 源 DECIMAL(8,2)，目标库被误建为 INT。",
        "fields": [
            ("item_id", "string"),
            ("order_id", "string"),
            ("sku", "string"),
            ("qty", "numeric"),
            ("unit_price", "numeric"),
            ("created_at", "datetime"),
        ],
    },
    {
        "code": "customer",
        "display_name": "客户档案",
        "src_table": "src_customer",
        "tgt_table": "tgt_customer",
        "owner": "迁移组 · 王雪",
        "description": "Oracle CUSTOMER → MySQL customer；phone 字段全半角与零宽字符需重点核对。",
        "fields": [
            ("customer_id", "string"),
            ("name", "string"),
            ("phone", "string"),
            ("email", "string"),
            ("city", "string"),
            ("created_at", "datetime"),
        ],
    },
    {
        "code": "payment",
        "display_name": "支付流水",
        "src_table": "src_payment",
        "tgt_table": "tgt_payment",
        "owner": "迁移组 · 李哲",
        "description": "Oracle PAYMENT → MySQL payment；渠道枚举需与目标库字典对齐。",
        "fields": [
            ("payment_id", "string"),
            ("order_id", "string"),
            ("amount", "numeric"),
            ("channel", "string"),
            ("paid_at", "datetime"),
        ],
    },
    {
        "code": "refund",
        "display_name": "退款单",
        "src_table": "src_refund",
        "tgt_table": "tgt_refund",
        "owner": "迁移组 · 李哲",
        "description": "Oracle REFUND → MySQL refund；源端存在 1 行主键 NULL 脏数据，会阻塞批次。",
        "fields": [
            ("refund_id", "string"),
            ("order_id", "string"),
            ("amount", "numeric"),
            ("reason", "string"),
            ("created_at", "datetime"),
        ],
    },
]


# ---------------------------------------------------------------- 数据生成 ----
def _now_ts() -> datetime:
    return datetime.now()


def _base_ts(now_ts: datetime) -> datetime:
    return (now_ts - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


def _row_ts(base: datetime, index: int) -> datetime:
    """近 30 天内确定性分布的时间戳，保证都在批次默认时间窗内。"""
    return base - timedelta(days=index % 29, minutes=(index * 37) % 1440)


def _money(rng: random.Random) -> Decimal:
    return (Decimal(rng.randint(500, 999999)) / Decimal(100)).quantize(Decimal("0.01"))


def build_rows(now_ts: datetime) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(20261110)
    base = _base_ts(now_ts)
    cities = ["上海", "杭州", "南京", "苏州", "合肥", "成都", "武汉", "北京"]
    statuses = ["paid", "paid", "pending", "refunded", "closed"]
    currencies = ["CNY", "CNY", "CNY", "CNY", "USD", "HKD"]
    channels = ["alipay", "wechat", "unionpay", "transfer"]
    reasons = ["尺寸不符", "重复下单", "物流延迟", "七天无理由", "支付失败回退"]

    customers = []
    for index in range(1, PAIR_SIZES["customer"][0] + 1):
        customers.append(
            {
                "customer_id": f"CUS-{index:08d}",
                "name": f"明川客户{index:04d}",
                "phone": f"138{index:08d}",
                "email": f"user{index:04d}@mingchuan-bank.cn",
                "city": cities[index % len(cities)],
                "created_at": _row_ts(base, index),
            }
        )

    orders = []
    for index in range(1, PAIR_SIZES["orders"][0] + 1):
        orders.append(
            {
                "order_id": f"ORD-{index:08d}",
                "customer_id": f"CUS-{rng.randint(1, PAIR_SIZES['customer'][0]):08d}",
                "order_no": f"SO2026{index:06d}",
                "amount": _money(rng),
                "currency": currencies[index % len(currencies)],
                "status": statuses[index % len(statuses)],
                "created_at": _row_ts(base, index),
            }
        )

    order_items = []
    for index in range(1, PAIR_SIZES["order_item"][0] + 1):
        order_items.append(
            {
                "item_id": f"OI-{index:08d}",
                "order_id": f"ORD-{rng.randint(1, PAIR_SIZES['orders'][0]):08d}",
                "sku": f"SKU-{rng.randint(1, 420):04d}",
                "qty": Decimal(rng.randint(1, 5)),
                "unit_price": _money(rng),
                "created_at": _row_ts(base, index),
            }
        )

    payments = []
    for index in range(1, PAIR_SIZES["payment"][0] + 1):
        payments.append(
            {
                "payment_id": f"PAY-{index:08d}",
                "order_id": f"ORD-{rng.randint(1, PAIR_SIZES['orders'][0]):08d}",
                "amount": _money(rng),
                "channel": channels[index % len(channels)],
                "paid_at": _row_ts(base, index),
            }
        )

    refunds = []
    for index in range(1, PAIR_SIZES["refund"][0] + 1):
        refund_id = None if index == REFUND_NULL_INDEX else f"REF-{index:08d}"
        refunds.append(
            {
                "refund_id": refund_id,
                "order_id": f"ORD-{rng.randint(1, PAIR_SIZES['orders'][0]):08d}",
                "amount": _money(rng),
                "reason": reasons[index % len(reasons)],
                "created_at": _row_ts(base, index),
            }
        )

    return {
        "orders": orders,
        "order_item": order_items,
        "customer": customers,
        "payment": payments,
        "refund": refunds,
    }


def _fullwidth_digits(text: str) -> str:
    return "".join(chr(ord(ch) + 0xFEE0) if ch.isdigit() else ch for ch in text)


def find_special_pks(
    prefix: str,
    need: int,
    *,
    start: int = 5001,
    sample_rate: int = 5,
) -> list[str]:
    """搜索同时满足「落入 5 个目标桶」且「5% 抽样命中」的主键，保证下钻可复现。"""
    found: list[str] = []
    sequence = start
    while len(found) < need:
        candidate = f"{prefix}-{sequence:08d}"
        sequence += 1
        if bucket_index(candidate, BUCKET_COUNT) not in TARGET_BUCKETS:
            continue
        if not is_sampled(candidate, sample_rate):
            continue
        found.append(candidate)
    return found


def _assign_bucket_diffs(rows: dict[str, list[dict[str, Any]]], rng: random.Random) -> dict[str, Any]:
    """植入差异：12 行 order_item.qty 类型截断 + 8 行 customer.phone 编码差异。"""
    qty_pks = find_special_pks("OI", 12)
    phone_pks = find_special_pks("CUS", 8)

    for position, pk in enumerate(qty_pks):
        row = rows["order_item"][-1 - position]
        row["item_id"] = pk
        qty = (Decimal(rng.randint(1000, 99999)) / Decimal(100)).quantize(Decimal("0.01"))
        if qty == qty.to_integral_value():
            qty += Decimal("0.01")
        row["qty"] = qty

    for position, pk in enumerate(phone_pks):
        row = rows["customer"][-1 - position]
        row["customer_id"] = pk

    buckets: dict[str, dict[str, int]] = {}
    for pair, items in rows.items():
        pk_name = PRIMARY_KEYS[pair]
        buckets[pair] = {
            item[pk_name]: bucket_index(item[pk_name], BUCKET_COUNT)
            for item in items
            if item[pk_name] is not None
        }
    return {
        "qty_pks": set(qty_pks),
        "phone_pks": set(phone_pks),
        "buckets": buckets,
    }


def select_missing_rows(
    rows: dict[str, list[dict[str, Any]]],
    buckets: dict[str, dict[str, int]],
    specials: dict[str, set[str]],
    plan: dict[str, int],
    rng: random.Random,
) -> dict[str, set[str]]:
    """选出目标端缺失的行：先保证 5 个目标桶各至少 1 行（B1 三张表），再补齐额度。"""
    special_by_pair = {
        "order_item": specials["qty_pks"],
        "customer": specials["phone_pks"],
    }
    chosen: dict[str, set[str]] = {pair: set() for pair in plan}
    used: set[str] = set()

    for bucket in TARGET_BUCKETS:
        for pair in ("order_item", "customer", "orders"):
            if plan[pair] == 0 or len(chosen[pair]) >= plan[pair]:
                continue
            pk_name = PRIMARY_KEYS[pair]
            candidates = [
                item[pk_name]
                for item in rows[pair]
                if buckets[pair].get(item[pk_name]) == bucket
                and item[pk_name] not in special_by_pair.get(pair, set())
                and item[pk_name] not in used
            ]
            if candidates:
                key = candidates[rng.randrange(len(candidates))]
                chosen[pair].add(key)
                used.add(key)
                break

    for pair, need in plan.items():
        remaining = need - len(chosen[pair])
        if remaining <= 0:
            continue
        pk_name = PRIMARY_KEYS[pair]
        candidates = []
        for item in rows[pair]:
            key = item[pk_name]
            if key is None or key in special_by_pair.get(pair, set()) or key in used:
                continue
            if buckets[pair].get(key) not in TARGET_BUCKETS:
                continue
            # payment 的 running 批次（桶 64、已算前 16 桶）不能被缺失污染
            if pair == "payment" and bucket_index(key, 64) < 16:
                continue
            candidates.append(key)
        rng.shuffle(candidates)
        for key in candidates[:remaining]:
            chosen[pair].add(key)
            used.add(key)
        if len(chosen[pair]) != need:
            raise RuntimeError(f"missing rows not enough pair={pair} need={need} got={len(chosen[pair])}")
    return chosen


def build_target_rows(
    rows: dict[str, list[dict[str, Any]]],
    missing: dict[str, set[str]],
    specials: dict[str, set[str]],
) -> dict[str, list[dict[str, Any]]]:
    target: dict[str, list[dict[str, Any]]] = {}
    for pair, items in rows.items():
        pk_name = PRIMARY_KEYS[pair]
        out: list[dict[str, Any]] = []
        for item in items:
            key = item[pk_name]
            if key is None:
                continue  # 源端 NULL 主键脏数据不下发目标端
            if key in missing.get(pair, set()):
                continue
            copied = dict(item)
            if pair == "order_item" and key in specials["qty_pks"]:
                copied["qty"] = int(item["qty"])
            if pair == "customer" and key in specials["phone_pks"]:
                copied["phone"] = _fullwidth_digits(str(item["phone"])[:3]) + str(item["phone"])[3:]
            out.append(copied)
        target[pair] = out
    return target


def _assert_invariants(
    rows: dict[str, list[dict[str, Any]]],
    target: dict[str, list[dict[str, Any]]],
    missing: dict[str, set[str]],
    specials: dict[str, set[str]],
) -> None:
    for pair, (src_count, tgt_count) in PAIR_SIZES.items():
        if len(rows[pair]) != src_count:
            raise RuntimeError(f"src rows mismatch pair={pair} got={len(rows[pair])} want={src_count}")
        if len(target[pair]) != tgt_count:
            raise RuntimeError(f"tgt rows mismatch pair={pair} got={len(target[pair])} want={tgt_count}")
    for pair in ("orders", "order_item", "customer"):
        if len(missing[pair]) != MISSING_PLAN[pair]:
            raise RuntimeError(f"missing count mismatch pair={pair}")
    for bucket in TARGET_BUCKETS:
        covered = any(
            bucket_index(key, BUCKET_COUNT) == bucket
            for pair in ("orders", "order_item", "customer")
            for key in missing[pair]
        )
        if not covered:
            raise RuntimeError(f"target bucket not covered by missing rows bucket={bucket}")
    for key in specials["qty_pks"]:
        if bucket_index(key, BUCKET_COUNT) not in TARGET_BUCKETS or not is_sampled(key, 5):
            raise RuntimeError(f"qty special pk not reproducible key={key}")
    for key in specials["phone_pks"]:
        if bucket_index(key, BUCKET_COUNT) not in TARGET_BUCKETS or not is_sampled(key, 5):
            raise RuntimeError(f"phone special pk not reproducible key={key}")
    for key in missing["payment"]:
        if bucket_index(key, 64) < 16:
            raise RuntimeError(f"payment missing row pollutes running batch key={key}")


# ---------------------------------------------------------------- 写库 ----
def _demo_data_ready() -> bool:
    with engine.connect() as conn:
        for pair, (src_count, tgt_count) in PAIR_SIZES.items():
            src_table = DEMO_TABLES[PAIR_META_BY_CODE[pair]["src_table"]]
            tgt_table = DEMO_TABLES[PAIR_META_BY_CODE[pair]["tgt_table"]]
            got_src = int(conn.execute(select(func.count()).select_from(src_table)).scalar() or 0)
            got_tgt = int(conn.execute(select(func.count()).select_from(tgt_table)).scalar() or 0)
            if got_src != src_count or got_tgt != tgt_count:
                return False
    return True


PAIR_META_BY_CODE = {meta["code"]: meta for meta in PAIR_META}


def _rebuild_demo_tables(rows, target) -> None:
    with engine.begin() as conn:
        for meta in PAIR_META:
            conn.execute(delete(DEMO_TABLES[meta["src_table"]]))
            conn.execute(delete(DEMO_TABLES[meta["tgt_table"]]))
        for meta in PAIR_META:
            src_table = DEMO_TABLES[meta["src_table"]]
            tgt_table = DEMO_TABLES[meta["tgt_table"]]
            conn.execute(insert(src_table), rows[meta["code"]])
            conn.execute(insert(tgt_table), target[meta["code"]])


# ---------------------------------------------------------------- 种子逻辑 ----
def seed_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, display_name, role in DEMO_USERS:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(
                email=email,
                password_hash=auth_service.hash_password(DEMO_PASSWORD),
                display_name=display_name,
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
            print(f"SEED_CREATED entity=user key={email}", flush=True)
        users[role] = user
    db.commit()
    return users


def seed_pairs(db) -> dict[str, TablePair]:
    pairs: dict[str, TablePair] = {}
    for meta in PAIR_META:
        src_count, tgt_count = PAIR_SIZES[meta["code"]]
        pair = db.query(TablePair).filter(TablePair.code == meta["code"]).one_or_none()
        field_rules = [
            {"name": name, "type": field_type, "compare": field_type}
            for name, field_type in meta["fields"]
        ]
        if pair is None:
            pair = TablePair(
                code=meta["code"],
                display_name=meta["display_name"],
                src_table=meta["src_table"],
                tgt_table=meta["tgt_table"],
                primary_key=PRIMARY_KEYS[meta["code"]],
                field_rules=field_rules,
                status=PairStatus.ACTIVE.value,
                owner=meta["owner"],
                row_estimate_src=src_count,
                row_estimate_tgt=tgt_count,
                description=meta["description"],
            )
            db.add(pair)
            db.flush()
            print(f"SEED_CREATED entity=pair key={meta['code']}", flush=True)
        else:
            pair.row_estimate_src = src_count
            pair.row_estimate_tgt = tgt_count
            if not pair.field_rules:
                pair.field_rules = field_rules
        pairs[meta["code"]] = pair
    db.commit()
    return pairs


def seed_batches(db, users: dict[str, User]) -> dict[str, ReconBatch]:
    plan = [
        {
            "batch_no": f"PC-{SEED_BATCH_DATE}-0001",
            "pair_codes": ["orders", "order_item", "customer"],
            "strategy": "checksum",
            "bucket_count": 128,
            "sample_rate": 5,
            "window_days": 30,
            "status": BatchStatus.COMPLETED.value,
            "created_by": users[ROLE_ADMIN].id,
            "note": "上线前第三轮验收：3 张核心表，128 桶 + 5% 抽样",
            "run": "full",
        },
        {
            "batch_no": f"PC-{SEED_BATCH_DATE}-0002",
            "pair_codes": ["payment"],
            "strategy": "checksum",
            "bucket_count": 64,
            "sample_rate": 2,
            "window_days": 30,
            "status": BatchStatus.RUNNING.value,
            "created_by": users[ROLE_ANALYST].id,
            "note": "支付流水增量复核（Celery worker 正在跑，已完成前 16 桶）",
            "run": "partial",
        },
        {
            "batch_no": f"PC-{SEED_BATCH_DATE}-0003",
            "pair_codes": ["refund"],
            "strategy": "checksum",
            "bucket_count": 128,
            "sample_rate": 5,
            "window_days": 30,
            "status": BatchStatus.FAILED.value,
            "created_by": users[ROLE_ADMIN].id,
            "note": "退款单对账失败：源端存在主键 NULL 脏数据",
            "run": "failed",
        },
        {
            "batch_no": f"PC-{SEED_BATCH_DATE}-0004",
            "pair_codes": ["orders"],
            "strategy": "row_hash",
            "bucket_count": 256,
            "sample_rate": 1,
            "window_days": 7,
            "status": BatchStatus.PENDING.value,
            "created_by": users[ROLE_ANALYST].id,
            "note": "订单主表 256 桶细粒度复核（已排期，等待槽位）",
            "run": "none",
        },
    ]
    batches: dict[str, ReconBatch] = {}
    for item in plan:
        batch = db.query(ReconBatch).filter(ReconBatch.batch_no == item["batch_no"]).one_or_none()
        if batch is None:
            batch = ReconBatch(
                batch_no=item["batch_no"],
                pair_codes=item["pair_codes"],
                strategy=item["strategy"],
                bucket_count=item["bucket_count"],
                sample_rate=item["sample_rate"],
                window_days=item["window_days"],
                status=BatchStatus.PENDING.value,
                created_by=item["created_by"],
                params_json={"note": item["note"]},
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
            print(f"SEED_CREATED entity=batch key={batch.batch_no}", flush=True)
        else:
            print(f"SEED_SKIPPED entity=batch key={batch.batch_no}", flush=True)
        batches[item["batch_no"]] = batch

    # 幂等：批次已存在（首次 seed 已真实跑过）就不再重跑
    b1 = batches[f"PC-{SEED_BATCH_DATE}-0001"]
    if b1.status not in (BatchStatus.COMPLETED.value, BatchStatus.FAILED.value):
        run_batch(b1.id)
    b2 = batches[f"PC-{SEED_BATCH_DATE}-0002"]
    if b2.status not in (BatchStatus.RUNNING.value, BatchStatus.COMPLETED.value):
        run_batch(b2.id, bucket_limit=16)
    b3 = batches[f"PC-{SEED_BATCH_DATE}-0003"]
    if b3.status not in (BatchStatus.FAILED.value, BatchStatus.COMPLETED.value):
        result = run_batch(b3.id)
        print(f"SEED_NOTE entity=batch key={b3.batch_no} run={result}", flush=True)
    return batches


def seed_tickets(db, batches: dict[str, ReconBatch], users: dict[str, User]) -> None:
    if db.query(RepairTicket).count() > 0:
        print("SEED_SKIPPED entity=tickets key=existing", flush=True)
        return
    b1 = batches[f"PC-{SEED_BATCH_DATE}-0001"]

    def diff_ids(pair_code: str, field_name: str, diff_type: str, limit: int) -> list[int]:
        rows = (
            db.query(DiffDetail.id)
            .filter(
                DiffDetail.batch_id == b1.id,
                DiffDetail.pair_code == pair_code,
                DiffDetail.field_name == field_name,
                DiffDetail.diff_type == diff_type,
            )
            .order_by(DiffDetail.id.asc())
            .limit(limit)
            .all()
        )
        return [row[0] for row in rows]

    qty_ids = diff_ids("order_item", "qty", DiffType.TYPE_TRUNCATED.value, 12)
    phone_ids = diff_ids("customer", "phone", DiffType.ENCODING.value, 8)
    missing_ids = diff_ids("order_item", "__row__", DiffType.MISSING.value, 6) + diff_ids(
        "customer", "__row__", DiffType.MISSING.value, 4
    )

    analyst = users[ROLE_ANALYST]
    admin = users[ROLE_ADMIN]

    draft = ticket_service.create_ticket(
        db,
        ticket_service.TicketCreateRequest(
            batch_id=b1.id,
            pair_codes=["order_item"],
            diff_ids=qty_ids,
            title="order_item.qty 目标列 INT 截断，需扩为 DECIMAL(8,2)",
            note="12 行小数被截断，属于 DDL 映射问题，先修表结构再补数。",
        ),
        analyst,
    )
    submitted = ticket_service.create_ticket(
        db,
        ticket_service.TicketCreateRequest(
            batch_id=b1.id,
            pair_codes=["customer"],
            diff_ids=phone_ids,
            title="customer.phone 全角数字导致编码差异，统一 utf8mb4 后重导",
            note="8 行手机号首位为全角数字，连接字符集需与源库保持一致。",
        ),
        analyst,
    )
    ticket_service.submit(db, submitted)
    approved = ticket_service.create_ticket(
        db,
        ticket_service.TicketCreateRequest(
            batch_id=b1.id,
            pair_codes=["order_item", "customer"],
            diff_ids=missing_ids,
            title="缺失行补数单：目标端未写入 10 行订单行/客户档案",
            note="按主键从源库补写，补数后重跑对应桶。",
        ),
        analyst,
    )
    ticket_service.submit(db, approved)
    ticket_service.decide(db, approved, admin, True, "核对无误，同意补数。")
    print(
        f"SEED_CREATED entity=ticket keys={draft.ticket_no},{submitted.ticket_no},{approved.ticket_no}",
        flush=True,
    )


def _counts(db) -> dict[str, int]:
    pair_count = db.query(TablePair).count()
    batch_count = db.query(ReconBatch).count()
    diff_count = db.query(DiffDetail).count()
    ticket_count = db.query(RepairTicket).count()
    user_count = db.query(User).count()
    with engine.connect() as conn:
        src_rows = sum(
            int(conn.execute(select(func.count()).select_from(DEMO_TABLES[meta["src_table"]])).scalar() or 0)
            for meta in PAIR_META
        )
        tgt_rows = sum(
            int(conn.execute(select(func.count()).select_from(DEMO_TABLES[meta["tgt_table"]])).scalar() or 0)
            for meta in PAIR_META
        )
    return {
        "pairs": pair_count,
        "src_rows": src_rows,
        "tgt_rows": tgt_rows,
        "batches": batch_count,
        "diffs": diff_count,
        "tickets": ticket_count,
        "users": user_count,
    }


def seed_all() -> dict[str, int]:
    now_ts = _now_ts()
    rng = random.Random(20261110)

    if _demo_data_ready():
        print("SEED_SKIPPED entity=demo_tables key=already_ready", flush=True)
    else:
        rows = build_rows(now_ts)
        assignments = _assign_bucket_diffs(rows, rng)
        missing = select_missing_rows(rows, assignments["buckets"], assignments, MISSING_PLAN, rng)
        target = build_target_rows(rows, missing, assignments)
        _assert_invariants(rows, target, missing, assignments)
        _rebuild_demo_tables(rows, target)
        print(
            f"SEED_CREATED entity=demo_tables src={sum(len(v) for v in rows.values())} "
            f"tgt={sum(len(v) for v in target.values())}",
            flush=True,
        )

    with SessionLocal() as bootstrap:
        users = seed_users(bootstrap)
        seed_pairs(bootstrap)

    # 批次由 recon_engine 在独立 session 里真实执行；这里必须新开 session 才能读到结果
    db = SessionLocal()
    try:
        batches = seed_batches(db, users)
        db.commit()
        db.expire_all()
        seed_tickets(db, batches, users)
        audit_service.record(
            db,
            action="seed.run",
            entity_type="System",
            entity_id="seed_demo",
            actor_kind="system",
            payload={"batch_date": SEED_BATCH_DATE},
        )
        db.commit()
        db.expire_all()
        counts = _counts(db)
    finally:
        db.close()

    print(
        "SEED_SUMMARY "
        f"pairs={counts['pairs']} src_rows={counts['src_rows']} tgt_rows={counts['tgt_rows']} "
        f"batches={counts['batches']} diffs={counts['diffs']} tickets={counts['tickets']} "
        f"users={counts['users']}",
        flush=True,
    )
    return counts


def main() -> int:
    try:
        seed_all()
    except Exception as exc:  # noqa: BLE001
        print(f"SEED_FAILED reason={exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
