"""签核底稿（验收结论冻结记录）。

业务规则（与 signoff_service 对应）：
- 选择覆盖核心表的已完成批次生成冻结记录，快照列明可验收表、阻塞差异、已准确豁免差异；
- 已签（signed）记录的快照永不被后续变化改写，新鲜度读时实时计算并提示过期材料；
- 相同批次组合重复运行不新增签核记录（batch_set_hash 上的草稿唯一/已签唯一约束在服务层保证）；
- 核心表未覆盖或仍有未豁免差异时不能签核通过。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, now


class SignoffRecord(Base):
    __tablename__ = "signoff_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signoff_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    batch_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    # 排序后批次 id 集合的稳定哈希，用于「相同批次组合重复运行不新增记录」
    batch_set_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    # 冻结快照：签核时刻的批次/表对结论/阻塞差异/豁免差异/修复单指纹，后续任何变化不改写
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # 签核校验结果（可通过性 + 阻塞项），签核成功时落库；草稿阶段也回填最近一次构建结果
    validation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sign_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False, index=True)
