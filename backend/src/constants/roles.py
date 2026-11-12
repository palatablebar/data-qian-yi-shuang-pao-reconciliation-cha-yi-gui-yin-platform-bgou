"""RBAC 角色常量与能力矩阵。前后端必须一致。"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_ADMIN = Role.ADMIN.value
ROLE_ANALYST = Role.ANALYST.value
ROLE_VIEWER = Role.VIEWER.value

ALL_ROLES: tuple[str, ...] = (ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER)

# action -> 允许执行的角色；写操作 viewer 一律 403
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "pairs:read": ALL_ROLES,
    "pairs:write": (ROLE_ADMIN,),
    "batches:read": ALL_ROLES,
    "batches:create": (ROLE_ADMIN, ROLE_ANALYST),
    "batches:run": (ROLE_ADMIN, ROLE_ANALYST),
    "diffs:read": ALL_ROLES,
    "tickets:read": ALL_ROLES,
    "tickets:create": (ROLE_ADMIN, ROLE_ANALYST),
    "tickets:submit": (ROLE_ADMIN, ROLE_ANALYST),
    "tickets:approve": (ROLE_ADMIN,),
    "tickets:reject": (ROLE_ADMIN,),
    "signoffs:read": ALL_ROLES,
    "signoffs:create": (ROLE_ADMIN, ROLE_ANALYST),
    "signoffs:sign": (ROLE_ADMIN,),
    "exports:read": ALL_ROLES,
    "audit:read": ALL_ROLES,
    "users:admin": (ROLE_ADMIN,),
}


def role_can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, ())


ROLE_LABELS = {
    ROLE_ADMIN: "迁移负责人",
    ROLE_ANALYST: "数据开发",
    ROLE_VIEWER: "审计",
}
