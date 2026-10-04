"""Responsáveis atribuíveis e administração do acesso por unidade."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.core.permissions import Role
from app.core.scope import assert_unit_allowed, user_unit_ids
from app.models.access import UserUnitAccess
from app.models.equipment import Unit
from app.models.user import User
from app.modules.access.schemas import (
    ResponsibleOut,
    UnitRefOut,
    UserUnitsOut,
)
from app.shared.audit import record_audit


def _role_of(user: User) -> Role:
    return Role(user.role.value if hasattr(user.role, "value") else user.role)


async def list_responsibles(
    session: AsyncSession, actor: CurrentUser, unit_id: str
) -> list[ResponsibleOut]:
    """Usuários ativos que podem ser responsáveis por equipamentos da unidade.

    Inclui quem tem vínculo com a unidade e os ADMIN, que são globais por perfil.
    """
    await assert_unit_allowed(session, actor, unit_id)
    linked = (
        select(User)
        .join(UserUnitAccess, UserUnitAccess.user_id == User.id)
        .where(UserUnitAccess.unit_id == unit_id, User.active.is_(True))
    )
    admins = select(User).where(User.active.is_(True), User.role == Role.ADMIN)
    rows = list((await session.execute(linked)).scalars().all())
    rows += list((await session.execute(admins)).scalars().all())
    unique = {user.id: user for user in rows}
    return [
        ResponsibleOut(id=user.id, name=user.name, email=user.email)
        for user in sorted(unique.values(), key=lambda item: item.name.lower())
    ]


async def _user_or_404(session: AsyncSession, user_id: str) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado")
    return user


async def get_user_units(session: AsyncSession, user_id: str) -> UserUnitsOut:
    user = await _user_or_404(session, user_id)
    role = _role_of(user)
    if role is Role.ADMIN:
        units = list((await session.execute(select(Unit).where(Unit.active.is_(True)))).scalars())
    else:
        ids = await user_unit_ids(session, user_id)
        units = (
            list((await session.execute(select(Unit).where(Unit.id.in_(ids)))).scalars())
            if ids
            else []
        )
    return UserUnitsOut(
        user_id=user_id,
        role=role.value,
        all_units=role is Role.ADMIN,
        units=[
            UnitRefOut(id=unit.id, code=unit.code, name=unit.name)
            for unit in sorted(units, key=lambda item: item.code)
        ],
    )


async def replace_user_units(
    session: AsyncSession, *, user_id: str, unit_ids: list[str], actor: CurrentUser
) -> UserUnitsOut:
    """Substitui todos os vínculos do usuário. ADMIN não usa vínculo."""
    user = await _user_or_404(session, user_id)
    if _role_of(user) is Role.ADMIN:
        raise DomainError(
            "ADMIN enxerga todas as unidades por perfil e não recebe vínculo individual."
        )
    wanted = sorted(set(unit_ids))
    if wanted:
        found = set(
            (await session.execute(select(Unit.id).where(Unit.id.in_(wanted)))).scalars()
        )
        missing = [unit_id for unit_id in wanted if unit_id not in found]
        if missing:
            raise DomainError("Há unidades inexistentes na lista informada")

    previous = await user_unit_ids(session, user_id)
    await session.execute(delete(UserUnitAccess).where(UserUnitAccess.user_id == user_id))
    for unit_id in wanted:
        session.add(UserUnitAccess(user_id=user_id, unit_id=unit_id))
    await session.flush()

    if previous != wanted:
        await record_audit(
            session,
            user_id=actor.id,
            action="user.units_changed",
            entity="User",
            entity_id=user_id,
            previous_data={"unit_ids": previous},
            new_data={"unit_ids": wanted},
        )
    await session.commit()
    return await get_user_units(session, user_id)
