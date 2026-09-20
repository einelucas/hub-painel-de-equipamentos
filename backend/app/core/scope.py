"""Escopo de unidades por usuário.

O perfil diz **o que** o usuário pode fazer; o vínculo em `user_unit_access` diz
**onde**. Toda leitura ou escrita que toque dados de uma unidade precisa passar
por aqui — conhecer o UUID de um equipamento não pode dar acesso a ele.

ADMIN é global por perfil e não depende da tabela de vínculos.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import NotFoundError
from app.core.permissions import Role
from app.models.access import UserUnitAccess
from app.models.equipment import Equipment, ProjectContext
from app.models.user import User

# Mensagem única: não revela se o recurso existe em outra unidade.
_DENIED = "Recurso não encontrado ou fora das unidades autorizadas"


async def allowed_unit_ids(session: AsyncSession, actor: CurrentUser) -> set[str] | None:
    """Unidades visíveis ao usuário. `None` significa "todas" (ADMIN)."""
    if actor.role is Role.ADMIN:
        return None
    rows = (
        await session.execute(
            select(UserUnitAccess.unit_id).where(UserUnitAccess.user_id == actor.id)
        )
    ).scalars()
    return set(rows)


async def assert_unit_allowed(session: AsyncSession, actor: CurrentUser, unit_id: str) -> None:
    allowed = await allowed_unit_ids(session, actor)
    if allowed is not None and unit_id not in allowed:
        raise NotFoundError(_DENIED)


async def assert_context_allowed(
    session: AsyncSession, actor: CurrentUser, project_context_id: str
) -> ProjectContext:
    context = await session.get(ProjectContext, project_context_id)
    if context is None:
        raise NotFoundError("Contexto de projeto não encontrado")
    await assert_unit_allowed(session, actor, context.unit_id)
    return context


async def assert_equipment_allowed(
    session: AsyncSession, actor: CurrentUser, equipment_id: str
) -> Equipment:
    """Carrega o equipamento só se ele estiver em unidade autorizada."""
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise NotFoundError("Equipamento não encontrado")
    context = await session.get(ProjectContext, equipment.project_context_id)
    if context is None:
        raise NotFoundError("Equipamento não encontrado")
    await assert_unit_allowed(session, actor, context.unit_id)
    return equipment


def restrict_to_units(stmt: Select[Any], allowed: set[str] | None) -> Select[Any]:
    """Limita uma consulta que já passa por `project_context` às unidades permitidas.

    Com o conjunto vazio a consulta não retorna nada, que é o comportamento
    correto para quem ainda não tem unidade atribuída.
    """
    if allowed is None:
        return stmt
    return stmt.where(ProjectContext.unit_id.in_(allowed))


async def user_can_access_unit(session: AsyncSession, user_id: str, unit_id: str) -> bool:
    """Acesso de um usuário qualquer (ex.: candidato a responsável) à unidade."""
    user = await session.get(User, user_id)
    if user is None or not user.active:
        return False
    if Role(user.role.value if hasattr(user.role, "value") else user.role) is Role.ADMIN:
        return True
    found = (
        await session.execute(
            select(UserUnitAccess.id).where(
                UserUnitAccess.user_id == user_id, UserUnitAccess.unit_id == unit_id
            )
        )
    ).scalar_one_or_none()
    return found is not None


async def user_unit_ids(session: AsyncSession, user_id: str) -> list[str]:
    rows = (
        await session.execute(
            select(UserUnitAccess.unit_id).where(UserUnitAccess.user_id == user_id)
        )
    ).scalars()
    return sorted(rows)
