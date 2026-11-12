"""共享枚举（后端唯一来源；前端 constants/enums.ts 与之一一对应）。

出现位置：models/* 列注释与校验、schemas/* 序列化、services/* 状态机、
constants/roles.py 权限矩阵、seed_demo.py 演示数据、README「共享枚举」节。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class BatchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BucketStatus(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    EMPTY = "empty"


class DiffType(StrEnum):
    MISSING = "missing"
    EXTRA = "extra"
    TYPE_TRUNCATED = "type_truncated"
    PRECISION_LOSS = "precision_loss"
    ENCODING = "encoding"
    VALUE_SHIFT = "value_shift"
    DUPLICATE_KEY = "duplicate_key"


class TicketStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class SignoffStatus(StrEnum):
    DRAFT = "draft"
    SIGNED = "signed"


class PairStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class FieldType(StrEnum):
    STRING = "string"
    NUMERIC = "numeric"
    DATETIME = "datetime"


class CompareStrategy(StrEnum):
    CHECKSUM = "checksum"
    ROW_HASH = "row_hash"


class FailureReason(StrEnum):
    NULL_PRIMARY_KEY = "null_primary_key"
    DUPLICATE_KEY = "duplicate_key"


class ActorKind(StrEnum):
    USER = "user"
    SYSTEM = "system"


DIFF_TYPE_LABELS = {
    DiffType.MISSING: "缺失行",
    DiffType.EXTRA: "多出行",
    DiffType.TYPE_TRUNCATED: "类型截断",
    DiffType.PRECISION_LOSS: "精度丢失",
    DiffType.ENCODING: "编码差异",
    DiffType.VALUE_SHIFT: "值漂移",
    DiffType.DUPLICATE_KEY: "主键重复",
}


# 底稿新鲜度（读时实时计算，不落库）：fresh=材料未变；stale=冻结后有材料变更，需重签
SIGNOFF_FRESH = "fresh"
SIGNOFF_STALE = "stale"

# 过期原因（stale_reasons 元素的 reason 取值；前端 labels.ts 有对应中文文案）
STALE_BATCH_RERUN = "batch_rerun"          # 批次在冻结后重跑，桶/差异结果已改写
STALE_BATCH_STATUS = "batch_status"        # 批次状态与冻结时不一致（如失败/重跑中）
STALE_TICKET_CHANGED = "ticket_changed"    # 已引用的修复单状态/范围变更
STALE_TICKET_NEW = "ticket_new"            # 冻结后出现覆盖本批次差异的新修复单
STALE_DIFF_UNEXEMPTED = "diff_unexempted"  # 冻结后出现未豁免差异（重跑产生新 diff）
STALE_PAIR_CORE_CHANGED = "pair_core_changed"  # 核心表标记变化，覆盖结论可能失效

SIGNOFF_STATUS_LABELS = {
    SignoffStatus.DRAFT: "草稿",
    SignoffStatus.SIGNED: "已签核",
}

STALE_REASON_LABELS = {
    STALE_BATCH_RERUN: "批次冻结后重跑，对账结果已改写",
    STALE_BATCH_STATUS: "批次状态与冻结时不一致",
    STALE_TICKET_CHANGED: "引用的已审批修复单发生变更",
    STALE_TICKET_NEW: "冻结后出现覆盖本批次差异的新修复单",
    STALE_DIFF_UNEXEMPTED: "存在冻结后新增的未豁免差异",
    STALE_PAIR_CORE_CHANGED: "核心表标记发生变化",
}
