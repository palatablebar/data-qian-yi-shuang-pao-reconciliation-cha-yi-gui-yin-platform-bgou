"""模型注册入口：alembic 与 create_all 都从这里拿到完整 metadata。"""
from src.models.base import Base
from src.models.account import AuditLog, User
from src.models.catalog import TablePair
from src.models.recon import BucketResult, ReconBatch
from src.models.trace import DiffDetail, RepairTicket
from src.models.signoff import SignoffRecord
from src.models import demo_tables  # noqa: F401  (注册 src_* / tgt_* 演示表)

__all__ = [
    "Base",
    "User",
    "AuditLog",
    "TablePair",
    "ReconBatch",
    "BucketResult",
    "DiffDetail",
    "RepairTicket",
    "SignoffRecord",
]
