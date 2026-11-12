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
