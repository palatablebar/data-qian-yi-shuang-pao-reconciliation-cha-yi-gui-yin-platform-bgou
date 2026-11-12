"""签核底稿：table_pairs 增 is_core，新增 signoff_records。

Revision ID: 0002_signoff
幂等：全新库经 0001 create_all 已含新表/新列时跳过；老库则补列补表。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from src.models import Base

revision = "0002_signoff"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "table_pairs" in tables:
        columns = {column["name"] for column in inspector.get_columns("table_pairs")}
        if "is_core" not in columns:
            op.add_column(
                "table_pairs",
                sa.Column("is_core", sa.Boolean(), nullable=False, server_default=sa.true()),
            )

    if "signoff_records" not in tables:
        Base.metadata.tables["signoff_records"].create(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "signoff_records" in tables:
        op.drop_table("signoff_records")
    if "table_pairs" in tables:
        columns = {column["name"] for column in inspector.get_columns("table_pairs")}
        if "is_core" in columns:
            op.drop_column("table_pairs", "is_core")
