"""初始化全部表：平台 7 张 + 双跑演示 src_*/tgt_* 10 张。

Revision ID: 0001_initial
"""
from __future__ import annotations

from alembic import op

from src.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
