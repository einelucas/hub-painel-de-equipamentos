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
    # Etapa 7C: reabertura passou a exigir solicitação + aprovação por
    # permissão superior — substitui o antigo `WORKFLOW_REOPEN` (reabertura
    # imediata via /transitions), que não fica mais acessível por nenhuma
    # rota. Mantido só como marcador histórico até uma limpeza futura.
    WORKFLOW_REOPEN = "workflow:reopen"
    WORKFLOW_REOPEN_REQUEST = "workflow:reopen_request"
    WORKFLOW_REOPEN_APPROVE = "workflow:reopen_approve"
    PROCESS_WRITE = "process:write"
    SUPPLIERS_READ = "suppliers:read"
    SUPPLIERS_WRITE = "suppliers:write"


_READ = {
    Permission.EQUIPMENTS_READ,
    Permission.CATALOGS_READ,
    Permission.WORKFLOW_READ,
    Permission.SUPPLIERS_READ,
}
_WRITE = _READ | {
    Permission.EQUIPMENTS_WRITE,
    Permission.PROCESS_WRITE,
    Permission.WORKFLOW_TRANSITION,
    Permission.SUPPLIERS_WRITE,
    # Etapa 7C: solicitar reabertura é uma alteração operacional normal —
    # mesmo perfil (Engenharia/Planejamento) que já avança fases.
    Permission.WORKFLOW_REOPEN_REQUEST,
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
        # Etapa 7C: aprovação exige permissão "superior" — hierarquia
        # corporativa real (Microsoft/Automação) ainda não definida; no
        # DEV atual, o perfil mais alto da matriz existente (ADMIN) é quem
        # aprova, do jeito menos invasivo possível.
        Permission.WORKFLOW_REOPEN_APPROVE,
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
