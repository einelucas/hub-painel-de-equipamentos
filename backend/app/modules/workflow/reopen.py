"""Etapa 7C — reabertura com aprovação.

O equipamento só muda de fase quando um `ReopenRequest` é APROVADO por quem
tem `WORKFLOW_REOPEN_APPROVE` — nunca no momento da solicitação. Hierarquia
corporativa real (quem é "superior" de quem) ainda não foi definida pelo
time de Automação/Microsoft: por ora, aprovar é uma permissão de perfil
(ADMIN), não uma relação de gestor/subordinado real. Dados de fases
posteriores nunca são apagados/zerados por uma reabertura.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.permissions import Permission, assert_can
from app.models.common import utcnow
from app.models.equipment import STAGES, WorkflowTransition
from app.models.user import User
from app.models.workflow_extras import ReopenRequest
from app.modules.equipments.schemas import UserRefOut
from app.modules.workflow.schemas import ReopenRequestListOut, ReopenRequestOut
from app.modules.workflow.service import _get_equipment
from app.shared.audit import record_audit


def _ref(user: User | None) -> UserRefOut | None:
    if user is None:
        return None
    return UserRefOut(id=user.id, name=user.name, email=user.email)


async def _out(session: AsyncSession, item: ReopenRequest) -> ReopenRequestOut:
    ids = {i for i in (item.requested_by_id, item.decided_by_id) if i}
    users: dict[str, User] = {}
    if ids:
        rows = (await session.execute(select(User).where(User.id.in_(ids)))).scalars().all()
        users = {u.id: u for u in rows}
    return ReopenRequestOut(
        id=item.id,
        equipment_id=item.equipment_id,
        source_stage=item.source_stage,
        source_stage_label=STAGES[item.source_stage],
        target_stage=item.target_stage,
        target_stage_label=STAGES[item.target_stage],
        justification=item.justification,
        status=item.status,
        requested_by=_ref(users.get(item.requested_by_id)) if item.requested_by_id else None,
        requested_at=item.requested_at,
        decided_by=_ref(users.get(item.decided_by_id)) if item.decided_by_id else None,
        decided_at=item.decided_at,
        decision_note=item.decision_note,
    )


async def request_reopen(
    session: AsyncSession,
    equipment_id: str,
    *,
    target_stage: int,
    justification: str,
    actor: CurrentUser,
) -> ReopenRequestOut:
    assert_can(actor.role, Permission.WORKFLOW_REOPEN_REQUEST)
    equipment = await _get_equipment(session, equipment_id, lock=False, actor=actor)
    if equipment.operational_status != "ACTIVE":
        raise DomainError(
            "O equipamento não está ativo — normalize o estado operacional antes de "
            "solicitar reabertura."
        )
    if target_stage >= equipment.current_stage:
        raise DomainError(
            "A reabertura só pode apontar para uma fase anterior à fase atual."
        )
    existing = (
        await session.execute(
            select(ReopenRequest).where(
                ReopenRequest.equipment_id == equipment_id,
                ReopenRequest.status == "PENDING",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            "Já existe uma solicitação de reabertura pendente para este equipamento."
        )

    item = ReopenRequest(
        equipment_id=equipment.id,
        source_stage=equipment.current_stage,
        target_stage=target_stage,
        justification=justification,
        status="PENDING",
        requested_by_id=actor.id,
    )
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="reopenrequest.create",
        entity="ReopenRequest",
        entity_id=item.id,
        new_data={
            "sourceStage": item.source_stage,
            "targetStage": item.target_stage,
            "justification": justification,
        },
        metadata={"equipmentId": equipment.id},
    )
    await session.commit()
    return await _out(session, item)


async def _get_request(session: AsyncSession, equipment_id: str, request_id: str) -> ReopenRequest:
    item = (
        await session.execute(
            select(ReopenRequest).where(
                ReopenRequest.id == request_id, ReopenRequest.equipment_id == equipment_id
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Solicitação de reabertura não encontrada")
    return item


async def approve_reopen(
    session: AsyncSession,
    equipment_id: str,
    request_id: str,
    *,
    note: str | None,
    actor: CurrentUser,
) -> ReopenRequestOut:
    assert_can(actor.role, Permission.WORKFLOW_REOPEN_APPROVE)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    item = await _get_request(session, equipment_id, request_id)
    if item.status != "PENDING":
        raise DomainError("Esta solicitação de reabertura já foi decidida.")
    if item.requested_by_id == actor.id:
        raise DomainError("Quem solicita a reabertura não pode aprovar a própria solicitação.")

    from_stage = equipment.current_stage
    session.add(
        WorkflowTransition(
            equipment_id=equipment.id,
            from_stage=from_stage,
            to_stage=item.target_stage,
            reason=item.justification,
            actor_id=actor.id,
        )
    )
    equipment.current_stage = item.target_stage
    item.status = "APPROVED"
    item.decided_by_id = actor.id
    item.decided_at = utcnow()
    item.decision_note = note
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="reopenrequest.approve",
        entity="ReopenRequest",
        entity_id=item.id,
        previous_data={"current_stage": from_stage},
        new_data={"current_stage": item.target_stage, "decisionNote": note},
        metadata={"equipmentId": equipment.id},
    )
    await session.commit()
    return await _out(session, item)


async def reject_reopen(
    session: AsyncSession,
    equipment_id: str,
    request_id: str,
    *,
    note: str | None,
    actor: CurrentUser,
) -> ReopenRequestOut:
    assert_can(actor.role, Permission.WORKFLOW_REOPEN_APPROVE)
    await _get_equipment(session, equipment_id, lock=False, actor=actor)
    item = await _get_request(session, equipment_id, request_id)
    if item.status != "PENDING":
        raise DomainError("Esta solicitação de reabertura já foi decidida.")
    if item.requested_by_id == actor.id:
        raise DomainError("Quem solicita a reabertura não pode decidir a própria solicitação.")

    item.status = "REJECTED"
    item.decided_by_id = actor.id
    item.decided_at = utcnow()
    item.decision_note = note
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="reopenrequest.reject",
        entity="ReopenRequest",
        entity_id=item.id,
        new_data={"decisionNote": note},
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()
    return await _out(session, item)


async def list_reopen_requests(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> ReopenRequestListOut:
    await _get_equipment(session, equipment_id, lock=False, actor=actor)
    rows = (
        (
            await session.execute(
                select(ReopenRequest)
                .where(ReopenRequest.equipment_id == equipment_id)
                .order_by(ReopenRequest.requested_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return ReopenRequestListOut(items=[await _out(session, row) for row in rows])
