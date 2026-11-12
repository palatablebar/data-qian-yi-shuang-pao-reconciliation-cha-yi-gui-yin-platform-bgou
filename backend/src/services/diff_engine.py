"""算法 B · 差异定位与归因（diff_engine）。

输入：差异桶的源行 / 目标行（按主键配对）。
步骤：
1. 按主键配对：只有源行 → missing；只有目标行 → extra；主键重复 → duplicate_key（不参与相似度）。
2. 行级字段 diff：逐个字段比较（主键之外），先做值规范化再判定。
3. 相似度：数值 → 相对误差 |a-b|/max(|a|,1)；字符串 → 1 - lev/max(len)；
   时间 → 先按 UTC/格式归一化再比较。
4. 差异分类：missing / extra / type_truncated（目标值长度 < 源值长度且为目标值前缀）/
   precision_loss（数值相对误差 < 1e-6 但不等）/ encoding（仅全半角、空格、不可见字符差异）/
   value_shift（其余值变化）。
5. 归因聚合：按 (表, 字段, 分类) 计数排序，给出最可能原因与修复建议。
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.constants.enums import DiffType, FieldType
from src.models.catalog import TablePair
from src.models.trace import DiffDetail
from src.utils.hashing import canonical

INVISIBLE_CHARS = "\u200b\u200c\u200d\u2060\ufeff\u00ad"
MAX_EDIT_LEN = 200
PRECISION_EPS = Decimal("0.000001")

ROOT_CAUSES: dict[str, tuple[str, str]] = {
    DiffType.TYPE_TRUNCATED.value: (
        "目标列长度/精度小于源值，DDL 字段映射未按源列定义（典型：DECIMAL→INT、VARCHAR 截短）",
        "按源列长度与精度 ALTER TABLE 目标表后重跑该桶",
    ),
    DiffType.PRECISION_LOSS.value: (
        "目标数值精度不足，小数位被舍入（DECIMAL 位数定义偏小）",
        "扩大目标列小数位并重导该批数据",
    ),
    DiffType.ENCODING.value: (
        "字符集/连接字符集不一致（utf8mb4 与 GBK、全角半角、零宽字符）导致值被转换",
        "统一连接字符集与列字符集为 utf8mb4_0900_ai_ci 后重导该批",
    ),
    DiffType.VALUE_SHIFT.value: (
        "迁移窗口内业务改数或时区/口径偏移，源目标值真实不同",
        "核对双写日志与业务变更单，确认后重跑该桶",
    ),
    DiffType.MISSING.value: (
        "目标端未写入该主键行（双写失败、被过滤条件丢弃或迁移中断）",
        "按主键补数后重跑该桶",
    ),
    DiffType.EXTRA.value: (
        "目标端多出该主键行（重复写入或回填重复）",
        "核对写入幂等后删除多余行",
    ),
    DiffType.DUPLICATE_KEY.value: (
        "源/目标主键重复，无法稳定配对",
        "先去重再对账，并核查迁移主键唯一约束",
    ),
}


# ------------------------------------------------------------------ 基础工具 ----
def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return str(value)


def strip_invisible(text: str) -> str:
    return "".join(ch for ch in text if ch not in INVISIBLE_CHARS)


def normalize_encoding(text: str) -> str:
    """NFKC + 去不可见字符 + 去空白，用于识别「仅编码/全半角/空格」差异。"""
    cleaned = strip_invisible(text)
    return "".join(unicodedata.normalize("NFKC", cleaned).split())


def levenshtein(left: str, right: str) -> int:
    left = left[:MAX_EDIT_LEN]
    right = right[:MAX_EDIT_LEN]
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, ch_left in enumerate(left, start=1):
        current = [i]
        for j, ch_right in enumerate(right, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            replace = previous[j - 1] + (0 if ch_left == ch_right else 1)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def text_similarity(src_text: str, tgt_text: str) -> float:
    longest = max(len(src_text), len(tgt_text))
    if longest == 0:
        return 1.0
    return max(0.0, 1.0 - levenshtein(src_text, tgt_text) / longest)


# ------------------------------------------------------------------ 相似度 ----
def numeric_similarity(src: Any, tgt: Any) -> float:
    try:
        left = Decimal(str(src))
        right = Decimal(str(tgt))
    except (InvalidOperation, ValueError):
        return text_similarity(as_text(src), as_text(tgt))
    relative_error = abs(left - right) / max(abs(left), Decimal(1))
    return max(0.0, 1.0 - float(min(relative_error, Decimal(1))))


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = strip_invisible(as_text(value)).strip()
    for candidate in (text, text.replace("/", "-"), text.replace("T", " ")):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def value_similarity(field_type: str, src: Any, tgt: Any) -> float:
    if field_type == FieldType.NUMERIC.value:
        return numeric_similarity(src, tgt)
    if field_type == FieldType.DATETIME.value:
        left, right = parse_datetime(src), parse_datetime(tgt)
        if left is not None and right is not None:
            return 1.0 if left == right else text_similarity(left.isoformat(), right.isoformat())
        return text_similarity(as_text(src), as_text(tgt))
    return text_similarity(as_text(src), as_text(tgt))


# ------------------------------------------------------------------ 分类 ----
def is_truncation(src_text: str, tgt_text: str) -> bool:
    """目标值比源值短，且是源值前缀 → 类型截断（列长度/精度不足）。"""
    if not tgt_text or not src_text or len(tgt_text) >= len(src_text):
        return False
    return src_text.startswith(tgt_text)


def classify_value(rule: dict[str, Any], src: Any, tgt: Any) -> dict[str, Any] | None:
    """返回单字段差异（含分类/相似度/归因），值等价时返回 None。"""
    if canonical(src) == canonical(tgt):
        return None
    field_type = str(rule.get("type", FieldType.STRING.value))
    src_text = as_text(src)
    tgt_text = as_text(tgt)

    if field_type == FieldType.NUMERIC.value:
        try:
            left = Decimal(str(src))
            right = Decimal(str(tgt))
        except (InvalidOperation, ValueError):
            left = right = None
        if is_truncation(src_text, tgt_text):
            diff_type = DiffType.TYPE_TRUNCATED.value
        elif left is not None and right is not None and (
            abs(left - right) / max(abs(left), Decimal(1))
        ) < PRECISION_EPS:
            diff_type = DiffType.PRECISION_LOSS.value
        else:
            diff_type = DiffType.VALUE_SHIFT.value
        similarity = numeric_similarity(src, tgt)
    elif field_type == FieldType.DATETIME.value:
        left, right = parse_datetime(src), parse_datetime(tgt)
        if left is not None and right is not None and left == right:
            diff_type = DiffType.ENCODING.value  # 仅格式/时区表述不同，归一化后一致
        else:
            diff_type = DiffType.VALUE_SHIFT.value
        similarity = value_similarity(field_type, src, tgt)
    else:
        if is_truncation(src_text, tgt_text):
            diff_type = DiffType.TYPE_TRUNCATED.value
        elif normalize_encoding(src_text) == normalize_encoding(tgt_text):
            diff_type = DiffType.ENCODING.value
        else:
            diff_type = DiffType.VALUE_SHIFT.value
        similarity = text_similarity(src_text, tgt_text)

    cause, suggestion = ROOT_CAUSES[diff_type]
    return {
        "field_name": str(rule.get("name", "")),
        "src_value": _clip(src_text),
        "tgt_value": _clip(tgt_text),
        "diff_type": diff_type,
        "similarity": round(float(similarity), 4),
        "attribution": _clip(cause),
        "suggestion": _clip(suggestion),
    }


def _clip(text: str, limit: int = 240) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


# ------------------------------------------------------------------ 行级 diff ----
def compare_rows(
    pair: TablePair,
    src_row: dict[str, Any],
    tgt_row: dict[str, Any],
    *,
    bucket_no: int,
) -> list[dict[str, Any]]:
    """逐字段比较一行（主键已配对），返回差异列表。"""
    out: list[dict[str, Any]] = []
    for rule in pair.field_rules or []:
        name = str(rule.get("name", ""))
        if not name or name == pair.primary_key:
            continue
        diff = classify_value(rule, src_row.get(name), tgt_row.get(name))
        if diff is None:
            continue
        out.append(
            {
                "bucket_no": bucket_no,
                "pair_code": pair.code,
                "primary_key_value": as_text(src_row.get(pair.primary_key)),
                **diff,
                "attribution": _clip(f"{pair.code}.{name}: {diff['attribution']}"),
            }
        )
    return out


def missing_row_diff(pair: TablePair, key: str, *, bucket_no: int, extra: bool = False) -> dict[str, Any]:
    diff_type = DiffType.EXTRA.value if extra else DiffType.MISSING.value
    cause, suggestion = ROOT_CAUSES[diff_type]
    return {
        "bucket_no": bucket_no,
        "pair_code": pair.code,
        "primary_key_value": _clip(key, 78),
        "field_name": "__row__",
        "src_value": None if extra else _clip(key, 78),
        "tgt_value": _clip(key, 78) if extra else None,
        "diff_type": diff_type,
        "similarity": 0.0,
        "attribution": _clip(f"{pair.code}.{pair.primary_key}: {cause}"),
        "suggestion": _clip(suggestion),
    }


def duplicate_key_diff(pair: TablePair, key: str, *, bucket_no: int, side: str) -> dict[str, Any]:
    cause, suggestion = ROOT_CAUSES[DiffType.DUPLICATE_KEY.value]
    return {
        "bucket_no": bucket_no,
        "pair_code": pair.code,
        "primary_key_value": _clip(key, 78),
        "field_name": pair.primary_key,
        "src_value": key if side == "src" else None,
        "tgt_value": key if side == "tgt" else None,
        "diff_type": DiffType.DUPLICATE_KEY.value,
        "similarity": 0.0,
        "attribution": _clip(f"{pair.code}.{pair.primary_key}({side}): {cause}"),
        "suggestion": _clip(suggestion),
    }


# ------------------------------------------------------------------ 归因聚合 ----
def aggregate_attribution(db: Session, batch_id: int) -> dict[str, Any]:
    """按 (表, 字段, 分类) 聚合差异，返回排序后的归因摘要。"""
    rows = (
        db.query(
            DiffDetail.pair_code,
            DiffDetail.field_name,
            DiffDetail.diff_type,
            func.count(DiffDetail.id),
        )
        .filter(DiffDetail.batch_id == batch_id)
        .group_by(DiffDetail.pair_code, DiffDetail.field_name, DiffDetail.diff_type)
        .all()
    )
    pairs = {pair.code: pair for pair in db.query(TablePair).all()}
    total = sum(int(count) for _, _, _, count in rows)
    groups: list[dict[str, Any]] = []
    by_type: dict[str, int] = defaultdict(int)
    for pair_code, field_name, diff_type, count in rows:
        count = int(count)
        cause, suggestion = ROOT_CAUSES.get(diff_type, ("未知差异", "人工核查"))
        pair = pairs.get(pair_code)
        groups.append(
            {
                "pair_code": pair_code,
                "table": pair.src_table if pair else pair_code,
                "field_name": field_name,
                "field_label": "整行" if field_name == "__row__" else field_name,
                "diff_type": diff_type,
                "count": count,
                "ratio": round(count / total, 4) if total else 0.0,
                "root_cause": cause,
                "suggestion": suggestion,
            }
        )
        by_type[diff_type] += count
    groups.sort(key=lambda item: (-item["count"], item["pair_code"], item["field_name"]))
    return {
        "batch_id": batch_id,
        "total_diffs": total,
        "groups": groups,
        "by_type": [{"diff_type": key, "count": value} for key, value in sorted(by_type.items())],
        "top_group": groups[0] if groups else None,
    }


def summarize_types(diffs: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = defaultdict(int)
    for diff in diffs:
        summary[diff["diff_type"]] += 1
    return dict(summary)
