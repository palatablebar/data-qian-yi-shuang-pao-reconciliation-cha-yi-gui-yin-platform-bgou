"""稳定哈希工具：桶号、行级 checksum、确定性抽样、值规范化。

口径（与 README / 页面公式说明一致）：
- 桶号 = int(md5(pk)[:8], 16) mod N
- 行级 h = md5(用 '|' 连接各列规范化字符串)
- 桶级 checksum = sum(int(h[:8], 16)) mod 2^32（与行序无关）
- 抽样命中 = int(md5(pk + '#sample')[:8], 16) % 100 < sample_rate_pct
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Any

NULL_TOKEN = "\u2205"
MOD32 = 1 << 32


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def bucket_index(pk_value: Any, bucket_count: int) -> int:
    return int(md5_hex(f"pk:{canonical(pk_value)}")[:8], 16) % bucket_count


def is_sampled(pk_value: Any, sample_rate_pct: int) -> bool:
    if sample_rate_pct <= 0:
        return False
    if sample_rate_pct >= 100:
        return True
    return int(md5_hex(f"sample:{canonical(pk_value)}")[:8], 16) % 100 < sample_rate_pct


def canonical(value: Any) -> str:
    """列值规范化：None → ∅；Decimal 去尾零；datetime 固定到秒；其余 str。"""
    if value is None:
        return NULL_TOKEN
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return format(normalized, "f")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(Decimal(str(value)).normalize(), "f")
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def row_checksum(values: list[Any]) -> str:
    return md5_hex("|".join(canonical(value) for value in values))


def checksum_int(row_hash: str) -> int:
    return int(row_hash[:8], 16)


def bucket_checksum(row_hashes: list[str]) -> int:
    return sum(checksum_int(h) for h in row_hashes) % MOD32
