"""双跑演示表：src_*（Oracle 19c 迁移前视图）/ tgt_*（MySQL 8.0 新库）两套同构表。

演示用同一个 MySQL 库里的两套表模拟双跑，seed 负责灌数与制造差异：
- tgt_order_item.qty 故意定义为 INT（源 DECIMAL(8,2)）→ 12 行类型截断；
- tgt_customer.phone 写入全角数字/零宽空格 → 8 行编码差异；
- 两个方向各少写若干行 → missing 差异；
- src_refund 含 1 行 refund_id IS NULL → failed 批次 null_primary_key。
"""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, Numeric, String, Table

from src.models.base import Base

src_orders = Table(
    "src_orders",
    Base.metadata,
    Column("order_id", String(20), primary_key=True),
    Column("customer_id", String(20), nullable=False),
    Column("order_no", String(32), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

tgt_orders = Table(
    "tgt_orders",
    Base.metadata,
    Column("order_id", String(20), primary_key=True),
    Column("customer_id", String(20), nullable=False),
    Column("order_no", String(32), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("currency", String(3), nullable=False),
    Column("status", String(16), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

src_order_item = Table(
    "src_order_item",
    Base.metadata,
    Column("item_id", String(20), primary_key=True),
    Column("order_id", String(20), nullable=False),
    Column("sku", String(24), nullable=False),
    Column("qty", Numeric(8, 2), nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

tgt_order_item = Table(
    "tgt_order_item",
    Base.metadata,
    Column("item_id", String(20), primary_key=True),
    Column("order_id", String(20), nullable=False),
    Column("sku", String(24), nullable=False),
    Column("qty", Integer, nullable=False),  # 迁移时误建为 INT → 类型截断
    Column("unit_price", Numeric(10, 2), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

src_customer = Table(
    "src_customer",
    Base.metadata,
    Column("customer_id", String(20), primary_key=True),
    Column("name", String(60), nullable=False),
    Column("phone", String(24), nullable=False),
    Column("email", String(80), nullable=False),
    Column("city", String(32), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

tgt_customer = Table(
    "tgt_customer",
    Base.metadata,
    Column("customer_id", String(20), primary_key=True),
    Column("name", String(60), nullable=False),
    Column("phone", String(24), nullable=False),  # 含全角数字 / 零宽空格
    Column("email", String(80), nullable=False),
    Column("city", String(32), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

src_payment = Table(
    "src_payment",
    Base.metadata,
    Column("payment_id", String(20), primary_key=True),
    Column("order_id", String(20), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("channel", String(16), nullable=False),
    Column("paid_at", DateTime, nullable=False),
)

tgt_payment = Table(
    "tgt_payment",
    Base.metadata,
    Column("payment_id", String(20), primary_key=True),
    Column("order_id", String(20), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("channel", String(16), nullable=False),
    Column("paid_at", DateTime, nullable=False),
)

# src_refund 的 refund_id 允许 NULL：用于验证 failed 批次 null_primary_key
src_refund = Table(
    "src_refund",
    Base.metadata,
    Column("refund_id", String(20), nullable=True),
    Column("order_id", String(20), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("reason", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

tgt_refund = Table(
    "tgt_refund",
    Base.metadata,
    Column("refund_id", String(20), primary_key=True),
    Column("order_id", String(20), nullable=False),
    Column("amount", Numeric(12, 2), nullable=False),
    Column("reason", String(64), nullable=False),
    Column("created_at", DateTime, nullable=False),
)

DEMO_TABLES = {
    "src_orders": src_orders,
    "tgt_orders": tgt_orders,
    "src_order_item": src_order_item,
    "tgt_order_item": tgt_order_item,
    "src_customer": src_customer,
    "tgt_customer": tgt_customer,
    "src_payment": src_payment,
    "tgt_payment": tgt_payment,
    "src_refund": src_refund,
    "tgt_refund": tgt_refund,
}
