from __future__ import annotations

from typing import Any

from sqlalchemy import Select, false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.scope import allowed_unit_ids
from app.models.equipment import Equipment, ProjectContext
from app.models.sync import SyncEvent


async def record_sync_event(
    session: AsyncSession,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    unit_id: str,
    actor_user_id: str | None,
    project_context_id: str | None = None,
    equipment_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> SyncEvent:
    """Inclui o evento na transação de domínio corrente; não faz commit."""
    event = SyncEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        unit_id=unit_id,
        project_context_id=project_context_id,
        equipment_id=equipment_id,
        actor_user_id=actor_user_id,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def record_equipment_sync_event(
    session: AsyncSession,
    *,
    equipment_id: str,
    actor_user_id: str | None,
    changed_fields: list[str],
) -> SyncEvent:
    equipment = await session.get(Equipment, equipment_id)
    if equipment is None:
        raise RuntimeError("Equipamento ausente ao registrar sincronização")
    context = await session.get(ProjectContext, equipment.project_context_id)
    if context is None:
        raise RuntimeError("Obra ausente ao registrar sincronização")
    return await record_sync_event(
        session,
        event_type="updated",
        entity_type="equipment",
        entity_id=equipment.id,
        unit_id=context.unit_id,
        project_context_id=context.id,
        equipment_id=equipment.id,
        actor_user_id=actor_user_id,
        payload={"changedFields": changed_fields},
    )


async def _scoped_query(
    session: AsyncSession, actor: CurrentUser, after: int, limit: int
) -> Select[tuple[SyncEvent]]:
    stmt = select(SyncEvent).where(SyncEvent.id > after).order_by(SyncEvent.id.asc()).limit(limit)
    allowed = await allowed_unit_ids(session, actor)
    if allowed is not None:
        if not allowed:
            return stmt.where(false())
        stmt = stmt.where(SyncEvent.unit_id.in_(allowed))
    return stmt


async def list_events(
    session: AsyncSession, actor: CurrentUser, *, after: int, limit: int = 100
) -> list[SyncEvent]:
    stmt = await _scoped_query(session, actor, after, limit)
    return list((await session.execute(stmt)).scalars().all())
