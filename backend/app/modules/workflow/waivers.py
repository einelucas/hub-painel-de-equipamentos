"""Etapa 7.1 — dispensa de requisitos por grupo (`RequirementWaiver`).

Substitui `WorkflowException`/`EXCEPTION_DISPENSED_REQUIREMENT_CODES`
(Etapa 7B): o motivo (`reason_code`) é só classificação para auditoria —
quais grupos existem, em qual fase, e se são dispensáveis é decidido
exclusivamente pelo backend (`app.modules.workflow.stages`), nunca por uma
string arbitrária vinda do cliente. O avanço de fase continua manual,
fase por fase — dispensar um grupo nunca pula etapa nenhuma.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.permissions import Permission, assert_can
from app.core.scope import assert_equipment_allowed
from app.models.common import utcnow
from app.models.user import User
from app.models.workflow_extras import RequirementWaiver
from app.modules.equipments.schemas import UserRefOut
from app.modules.workflow.schemas import RequirementWaiverListOut, RequirementWaiverOut
from app.modules.workflow.service import _get_equipment
from app.modules.workflow.stages import REASON_CODES, group_spec, is_waivable_group
from app.shared.audit import record_audit


def _out(
    item: RequirementWaiver, created_by: UserRefOut | None, revoked_by: UserRefOut | None
) -> RequirementWaiverOut:
    spec = group_spec(item.requirement_group_code)
    return RequirementWaiverOut(
        id=item.id,
        equipment_id=item.equipment_id,
        stage=item.stage,
        requirement_group_code=item.requirement_group_code,
        requirement_group_label=spec.label if spec is not None else item.requirement_group_code,
        reason_code=item.reason_code,
        justification=item.justification,
        status=item.status,
        created_by=created_by,
        created_at=item.created_at,
        revoked_by=revoked_by,
        revoked_at=item.revoked_at,
        revoke_reason=item.revoke_reason,
    )


async def _user_ref(session: AsyncSession, user_id: str | None) -> UserRefOut | None:
    if not user_id:
        return None
    row = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if row is None:
        return None
    return UserRefOut(id=row.id, name=row.name, email=row.email)


async def create_waiver(
    session: AsyncSession,
    equipment_id: str,
    *,
    stage: int,
    requirement_group_code: str,
    reason_code: str,
    justification: str,
    actor: CurrentUser,
) -> RequirementWaiverOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)

    spec = group_spec(requirement_group_code)
    if spec is None:
        raise DomainError("Grupo de requisito desconhecido.")
    if not is_waivable_group(stage, requirement_group_code):
        raise DomainError(
            "Este grupo de requisito não pode ser dispensado nesta fase — "
            f"'{requirement_group_code}' pertence à fase {spec.stage}, não à {stage}, "
            "ou não é um grupo dispensável."
            if spec.stage != stage
            else f"O grupo '{requirement_group_code}' não pode ser dispensado."
        )
    if reason_code not in REASON_CODES:
        raise DomainError("Motivo de dispensa inválido.")
    if not justification.strip():
        raise DomainError("Justificativa obrigatória.")

    existing = (
        await session.execute(
            select(RequirementWaiver).where(
                RequirementWaiver.equipment_id == equipment_id,
                RequirementWaiver.stage == stage,
                RequirementWaiver.requirement_group_code == requirement_group_code,
                RequirementWaiver.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            f"Já existe uma dispensa ativa para '{requirement_group_code}' nesta fase. "
            "Revogue-a antes de criar outra."
        )

    item = RequirementWaiver(
        equipment_id=equipment.id,
        stage=stage,
        requirement_group_code=requirement_group_code,
        reason_code=reason_code,
        justification=justification.strip(),
        status="ACTIVE",
        created_by_id=actor.id,
    )
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="requirementwaiver.create",
        entity="RequirementWaiver",
        entity_id=item.id,
        new_data={
            "stage": stage,
            "requirementGroupCode": requirement_group_code,
            "reasonCode": reason_code,
            "justification": item.justification,
        },
        metadata={"equipmentId": equipment.id},
    )
    await session.commit()
    creator = UserRefOut(id=actor.id, name=actor.name, email=actor.email)
    return _out(item, creator, None)


async def revoke_waiver(
    session: AsyncSession,
    equipment_id: str,
    waiver_id: str,
    *,
    revoke_reason: str | None,
    actor: CurrentUser,
) -> RequirementWaiverOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    await _get_equipment(session, equipment_id, lock=False, actor=actor)

    item = (
        await session.execute(
            select(RequirementWaiver).where(
                RequirementWaiver.id == waiver_id,
                RequirementWaiver.equipment_id == equipment_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Dispensa de requisito não encontrada.")
    if item.status != "ACTIVE":
        raise DomainError("Esta dispensa já não está ativa.")

    item.status = "REVOKED"
    item.revoked_by_id = actor.id
    item.revoked_at = utcnow()
    item.revoke_reason = revoke_reason.strip() if revoke_reason else None
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="requirementwaiver.revoke",
        entity="RequirementWaiver",
        entity_id=item.id,
        new_data={"revokeReason": item.revoke_reason},
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()

    creator = await _user_ref(session, item.created_by_id)
    revoker = UserRefOut(id=actor.id, name=actor.name, email=actor.email)
    return _out(item, creator, revoker)


async def list_waivers(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> RequirementWaiverListOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    rows = (
        (
            await session.execute(
                select(RequirementWaiver)
                .where(RequirementWaiver.equipment_id == equipment_id)
                .order_by(RequirementWaiver.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    user_ids = {row.created_by_id for row in rows if row.created_by_id}
    user_ids |= {row.revoked_by_id for row in rows if row.revoked_by_id}
    users: dict[str, UserRefOut] = {}
    if user_ids:
        db_rows = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: UserRefOut(id=u.id, name=u.name, email=u.email) for u in db_rows}

    return RequirementWaiverListOut(
        items=[
            _out(
                row,
                users.get(row.created_by_id) if row.created_by_id else None,
                users.get(row.revoked_by_id) if row.revoked_by_id else None,
            )
            for row in rows
        ]
    )


async def active_waivers_by_group(
    session: AsyncSession, equipment_id: str, stage: int
) -> dict[str, RequirementWaiver]:
    """Usado pelo motor de avaliação (`workflow/service.py`) — dispensas
    ACTIVE da fase informada, indexadas por `requirement_group_code`."""
    rows = (
        (
            await session.execute(
                select(RequirementWaiver).where(
                    RequirementWaiver.equipment_id == equipment_id,
                    RequirementWaiver.stage == stage,
                    RequirementWaiver.status == "ACTIVE",
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.requirement_group_code: row for row in rows}
