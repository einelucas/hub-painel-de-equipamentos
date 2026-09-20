from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, NotFoundError
from app.core.scope import (
    allowed_unit_ids,
    assert_context_allowed,
    assert_unit_allowed,
)
from app.models.equipment import Area, Discipline, ProjectContext, Unit, WorkPackage
from app.shared.audit import record_audit


async def _list(session: AsyncSession, model: type[Any], *filters: Any) -> list[Any]:
    stmt = select(model).where(*filters).order_by(model.name.asc())
    return list((await session.execute(stmt)).scalars().all())


async def list_units(session: AsyncSession, actor: CurrentUser) -> list[Unit]:
    """Só as unidades que o usuário pode ver — a base do filtro global."""
    allowed = await allowed_unit_ids(session, actor)
    if allowed is None:
        return await _list(session, Unit, Unit.active.is_(True))
    if not allowed:
        return []
    return await _list(session, Unit, Unit.active.is_(True), Unit.id.in_(allowed))


async def list_project_contexts(
    session: AsyncSession, actor: CurrentUser, unit_id: str
) -> list[ProjectContext]:
    if await session.get(Unit, unit_id) is None:
        raise NotFoundError("Unidade não encontrada")
    await assert_unit_allowed(session, actor, unit_id)
    return await _list(
        session, ProjectContext, ProjectContext.unit_id == unit_id, ProjectContext.active.is_(True)
    )


async def list_areas(session: AsyncSession, actor: CurrentUser, unit_id: str) -> list[Area]:
    await assert_unit_allowed(session, actor, unit_id)
    return await _list(session, Area, Area.unit_id == unit_id, Area.active.is_(True))


async def list_disciplines(session: AsyncSession) -> list[Discipline]:
    """Disciplinas são globais: não pertencem a uma unidade."""
    return await _list(session, Discipline, Discipline.active.is_(True))


async def list_work_packages(
    session: AsyncSession, actor: CurrentUser, project_context_id: str
) -> list[WorkPackage]:
    await assert_context_allowed(session, actor, project_context_id)
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


async def update_catalog(
    session: AsyncSession,
    model: type[Any],
    *,
    item_id: str,
    changes: dict[str, object],
    actor: CurrentUser,
) -> Any:
    """Edição e ativação/desativação. Nunca apaga: registros são referenciados."""
    item = await session.get(model, item_id)
    if item is None:
        raise NotFoundError("Registro de catálogo não encontrado")
    changes = {
        key: value.strip() if isinstance(value, str) else value for key, value in changes.items()
    }
    if "name" in changes and not changes["name"]:
        raise ConflictError("Nome do catálogo é obrigatório")

    for field in ("code", "name"):
        if field not in changes or not hasattr(model, field):
            continue
        conditions = [getattr(model, field) == changes[field], model.id != item_id]
        if hasattr(model, "unit_id"):
            conditions.append(model.unit_id == item.unit_id)
        if hasattr(model, "project_context_id"):
            conditions.append(model.project_context_id == item.project_context_id)
        duplicated = (
            await session.execute(select(model.id).where(*conditions))
        ).scalar_one_or_none()
        if duplicated is not None:
            raise ConflictError("Já existe um registro equivalente neste catálogo")

    previous: dict[str, object] = {}
    changed: dict[str, object] = {}
    for field, value in changes.items():
        if getattr(item, field) != value:
            previous[field] = getattr(item, field)
            changed[field] = value
            setattr(item, field, value)
    if changed:
        await record_audit(
            session,
            user_id=actor.id,
            action="catalog.update",
            entity=model.__name__,
            entity_id=item.id,
            previous_data=previous,
            new_data=changed,
        )
    await session.commit()
    await session.refresh(item)
    return item
