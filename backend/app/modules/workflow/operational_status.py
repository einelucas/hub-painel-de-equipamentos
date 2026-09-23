"""Etapa 7B — estado operacional (Standby / Cancelado / Em Saneamento).

Separado da fase do processo (`Equipment.current_stage`, controlada só por
`app.modules.workflow.service.execute_transition`). Aqui só
`Equipment.operational_status` muda, e sempre acompanhado de um
`OperationalStatusEvent` com usuário, data/hora, fase e justificativa — nunca
um campo mutável isolado sem rastro.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import DomainError
from app.core.permissions import Permission, assert_can
from app.models.equipment import Equipment
from app.models.workflow_extras import OperationalStatusEvent
from app.modules.equipments.schemas import UserRefOut
from app.modules.workflow.schemas import EquipmentOperationalStatusOut, OperationalStatusEventOut
from app.modules.workflow.service import _get_equipment
from app.shared.audit import record_audit

_AUDIT_ACTIONS = {
    "STANDBY_ENTERED": "equipment.standby_entered",
    "STANDBY_LIFTED": "equipment.standby_lifted",
    "CANCELLED": "equipment.cancelled",
    "SANITATION_ENTERED": "equipment.sanitation_entered",
    "SANITATION_ENDED": "equipment.sanitation_ended",
}


async def _apply(
    session: AsyncSession,
    *,
    equipment: Equipment,
    kind: str,
    resulting_status: str,
    stage_at_event: int,
    justification: str | None,
    actor: CurrentUser,
) -> None:
    session.add(
        OperationalStatusEvent(
            equipment_id=equipment.id,
            kind=kind,
            resulting_status=resulting_status,
            stage_at_event=stage_at_event,
            justification=justification or "",
            actor_id=actor.id,
        )
    )
    previous_status = equipment.operational_status
    equipment.operational_status = resulting_status
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=_AUDIT_ACTIONS[kind],
        entity="Equipment",
        entity_id=equipment.id,
        previous_data={"operationalStatus": previous_status},
        new_data={"operationalStatus": resulting_status, "justification": justification},
        metadata={"equipmentId": equipment.id, "stageAtEvent": stage_at_event},
    )
    await session.commit()


async def enter_standby(
    session: AsyncSession, equipment_id: str, justification: str, actor: CurrentUser
) -> EquipmentOperationalStatusOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    if equipment.operational_status != "ACTIVE":
        raise DomainError(
            "Só é possível colocar em Standby um equipamento no estado ativo."
        )
    await _apply(
        session,
        equipment=equipment,
        kind="STANDBY_ENTERED",
        resulting_status="STANDBY",
        stage_at_event=equipment.current_stage,
        justification=justification,
        actor=actor,
    )
    return await get_operational_status(session, equipment_id, actor)


async def lift_standby(
    session: AsyncSession, equipment_id: str, justification: str | None, actor: CurrentUser
) -> EquipmentOperationalStatusOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    if equipment.operational_status != "STANDBY":
        raise DomainError("Este equipamento não está em Standby.")
    await _apply(
        session,
        equipment=equipment,
        kind="STANDBY_LIFTED",
        resulting_status="ACTIVE",
        stage_at_event=equipment.current_stage,
        justification=justification,
        actor=actor,
    )
    return await get_operational_status(session, equipment_id, actor)


async def cancel_equipment(
    session: AsyncSession, equipment_id: str, justification: str, actor: CurrentUser
) -> EquipmentOperationalStatusOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    if equipment.operational_status == "CANCELLED":
        raise DomainError("Este equipamento já está cancelado.")
    await _apply(
        session,
        equipment=equipment,
        kind="CANCELLED",
        resulting_status="CANCELLED",
        stage_at_event=equipment.current_stage,
        justification=justification,
        actor=actor,
    )
    return await get_operational_status(session, equipment_id, actor)


async def enter_sanitation(
    session: AsyncSession, equipment_id: str, justification: str, actor: CurrentUser
) -> EquipmentOperationalStatusOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    if equipment.operational_status != "ACTIVE":
        raise DomainError(
            "Só é possível colocar em Saneamento um equipamento no estado ativo."
        )
    origin_stage = equipment.current_stage
    session.add(
        OperationalStatusEvent(
            equipment_id=equipment.id,
            kind="SANITATION_ENTERED",
            resulting_status="IN_SANITATION",
            stage_at_event=origin_stage,
            justification=justification,
            actor_id=actor.id,
        )
    )
    equipment.operational_status = "IN_SANITATION"
    equipment.current_stage = 0
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=_AUDIT_ACTIONS["SANITATION_ENTERED"],
        entity="Equipment",
        entity_id=equipment.id,
        previous_data={"operationalStatus": "ACTIVE", "currentStage": origin_stage},
        new_data={
            "operationalStatus": "IN_SANITATION",
            "currentStage": 0,
            "justification": justification,
        },
        metadata={"equipmentId": equipment.id, "originStage": origin_stage},
    )
    await session.commit()
    return await get_operational_status(session, equipment_id, actor)


async def end_sanitation(
    session: AsyncSession, equipment_id: str, justification: str | None, actor: CurrentUser
) -> EquipmentOperationalStatusOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    if equipment.operational_status != "IN_SANITATION":
        raise DomainError("Este equipamento não está em Saneamento.")
    await _apply(
        session,
        equipment=equipment,
        kind="SANITATION_ENDED",
        resulting_status="ACTIVE",
        stage_at_event=equipment.current_stage,
        justification=justification,
        actor=actor,
    )
    return await get_operational_status(session, equipment_id, actor)


async def get_operational_status(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> EquipmentOperationalStatusOut:
    equipment = await _get_equipment(session, equipment_id, lock=False, actor=actor)
    rows = (
        (
            await session.execute(
                select(OperationalStatusEvent)
                .where(OperationalStatusEvent.equipment_id == equipment_id)
                .order_by(OperationalStatusEvent.occurred_at.desc())
            )
        )
        .scalars()
        .all()
    )
    actor_ids = {row.actor_id for row in rows if row.actor_id}
    actors: dict[str, UserRefOut] = {}
    if actor_ids:
        from app.models.user import User

        users = (
            (await session.execute(select(User).where(User.id.in_(actor_ids)))).scalars().all()
        )
        actors = {u.id: UserRefOut(id=u.id, name=u.name, email=u.email) for u in users}

    return EquipmentOperationalStatusOut(
        operational_status=equipment.operational_status,
        events=[
            OperationalStatusEventOut(
                id=row.id,
                kind=row.kind,
                resulting_status=row.resulting_status,
                stage_at_event=row.stage_at_event,
                justification=row.justification,
                actor=actors.get(row.actor_id) if row.actor_id else None,
                occurred_at=row.occurred_at,
            )
            for row in rows
        ],
    )
