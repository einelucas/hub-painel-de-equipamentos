"""Perfis e permissões compartilhadas pela base do Hub."""

from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    VIEWER = "VIEWER"
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


class Permission(str, Enum):
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    EQUIPMENTS_READ = "equipments:read"
    EQUIPMENTS_WRITE = "equipments:write"
    CATALOGS_READ = "catalogs:read"
    CATALOGS_MANAGE = "catalogs:manage"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_TRANSITION = "workflow:transition"
    WORKFLOW_REOPEN = "workflow:reopen"
    PROCESS_WRITE = "process:write"


_READ = {Permission.EQUIPMENTS_READ, Permission.CATALOGS_READ, Permission.WORKFLOW_READ}
_WRITE = _READ | {
    Permission.EQUIPMENTS_WRITE,
    Permission.PROCESS_WRITE,
    Permission.WORKFLOW_TRANSITION,
}

_MATRIX: dict[Role, set[Permission]] = {
    Role.VIEWER: _READ,
    Role.ANALYST: _WRITE,
    Role.ADMIN: _WRITE
    | {
        Permission.USERS_MANAGE,
        Permission.AUDIT_READ,
        Permission.CATALOGS_MANAGE,
        Permission.WORKFLOW_REOPEN,
    },
}


def can(role: Role, permission: Permission) -> bool:
    return permission in _MATRIX[role]


def permissions_for(role: Role) -> list[Permission]:
    return sorted(_MATRIX[role], key=lambda permission: permission.value)


class ForbiddenError(Exception):
    def __init__(self, permission: Permission) -> None:
        self.permission = permission
        super().__init__(f"Permissão negada: {permission.value}")


def assert_can(role: Role, permission: Permission) -> None:
    if not can(role, permission):
        raise ForbiddenError(permission)
