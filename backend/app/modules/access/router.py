from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.access import service
from app.modules.access.schemas import (
    ResponsibleListOut,
    UserUnitsOut,
    UserUnitsUpdateIn,
)

router = APIRouter(tags=["acessos"])


@router.get("/responsibles", response_model=ResponsibleListOut)
async def get_responsibles(
    unit_id: str = Query(alias="unit_id"),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> ResponsibleListOut:
    """Leitura própria para o formulário: não expõe a administração de usuários."""
    return ResponsibleListOut(items=await service.list_responsibles(session, actor, unit_id))


@router.get("/usuarios/{user_id}/units", response_model=UserUnitsOut)
async def get_user_units(
    user_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserUnitsOut:
    return await service.get_user_units(session, user_id)


@router.put("/usuarios/{user_id}/units", response_model=UserUnitsOut)
async def put_user_units(
    user_id: str,
    body: UserUnitsUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.USERS_MANAGE)),
) -> UserUnitsOut:
    return await service.replace_user_units(
        session, user_id=user_id, unit_ids=body.unit_ids, actor=actor
    )
