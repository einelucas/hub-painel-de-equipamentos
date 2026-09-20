from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, NotFoundError
from app.models.equipment import Area, Discipline, ProjectContext, Unit, WorkPackage
from app.shared.audit import record_audit


async def _list(session: AsyncSession, model: type[Any], *filters: Any) -> list[Any]:
    stmt = select(model).where(*filters).order_by(model.name.asc())
    return list((await session.execute(stmt)).scalars().all())


async def list_units(session: AsyncSession) -> list[Unit]:
    return await _list(session, Unit, Unit.active.is_(True))


async def list_project_contexts(session: AsyncSession, unit_id: str) -> list[ProjectContext]:
    if await session.get(Unit, unit_id) is None:
        raise NotFoundError("Unidade não encontrada")
    return await _list(
        session, ProjectContext, ProjectContext.unit_id == unit_id, ProjectContext.active.is_(True)
    )


async def list_areas(session: AsyncSession, unit_id: str) -> list[Area]:
    return await _list(session, Area, Area.unit_id == unit_id, Area.active.is_(True))


async def list_disciplines(session: AsyncSession) -> list[Discipline]:
    return await _list(session, Discipline, Discipline.active.is_(True))


async def list_work_packages(session: AsyncSession, project_context_id: str) -> list[WorkPackage]:
    return await _list(
        session,
        WorkPackage,
        WorkPackage.project_context_id == project_context_id,
        WorkPackage.active.is_(True),
    )


async def create_catalog(
    session: AsyncSession,
    model: type[Any],
    *,
    values: dict[str, object],
    actor: CurrentUser,
) -> Any:
    values = {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}
    if not values.get("name"):
        raise ConflictError("Nome do catálogo é obrigatório")

    if model in (ProjectContext, Area):
        parent_id = str(values["unit_id"])
        if await session.get(Unit, parent_id) is None:
            raise NotFoundError("Unidade não encontrada")
    elif model is WorkPackage:
        parent_id = str(values["project_context_id"])
        if await session.get(ProjectContext, parent_id) is None:
            raise NotFoundError("Contexto de projeto não encontrado")

    conditions = []
    if "code" in values:
        conditions.append(model.code == values["code"])
    else:
        conditions.append(model.name == values["name"])
    if "unit_id" in values:
        conditions.append(model.unit_id == values["unit_id"])
    if "project_context_id" in values:
        conditions.append(model.project_context_id == values["project_context_id"])
    if (await session.execute(select(model.id).where(*conditions))).scalar_one_or_none() is not None:
        raise ConflictError("Já existe um registro equivalente neste catálogo")

    item = model(**values)
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="catalog.create",
        entity=model.__name__,
        entity_id=item.id,
        new_data=values,
    )
    await session.commit()
    await session.refresh(item)
    return item
