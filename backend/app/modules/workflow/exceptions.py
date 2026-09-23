"""Etapa 7B — exceções de workflow (fornecedor fixo / importação).

Nunca um `force=true` genérico: cada exceção tem tipo conhecido, fase de
origem, destino pretendido fixo pelo negócio e uma justificativa única que é
reaproveitada em todas as transições manuais enquanto ela estiver ACTIVE
(ver `app.modules.workflow.stages.EXCEPTION_DISPENSED_REQUIREMENT_CODES`).
O avanço continua manual, fase por fase — a exceção só é concluída
automaticamente quando o equipamento chega efetivamente ao
`intended_target_stage` (ver `execute_transition`).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError
from app.core.permissions import Permission, assert_can
from app.models.common import utcnow
from app.models.user import User
from app.models.workflow_extras import WorkflowException
from app.modules.equipments.schemas import UserRefOut
from app.modules.workflow.schemas import WorkflowExceptionListOut, WorkflowExceptionOut
from app.modules.workflow.service import _get_equipment
from app.shared.audit import record_audit

# Fase-alvo pretendida fixada pelo negócio (Etapa 7, seção 4) — não é
# escolhida pelo usuário, é inerente ao tipo de exceção.
_INTENDED_TARGET_STAGE: dict[str, int] = {
    "FIXED_SUPPLIER": 5,
    "IMPORTATION": 7,
}


def _out(item: WorkflowException, actor_ref: UserRefOut | None) -> WorkflowExceptionOut:
    return WorkflowExceptionOut(
        id=item.id,
        equipment_id=item.equipment_id,
        type=item.type,
        status=item.status,
        source_stage=item.source_stage,
        intended_target_stage=item.intended_target_stage,
        justification=item.justification,
        created_by=actor_ref,
        created_at=item.created_at,
        completed_at=item.completed_at,
        cancelled_at=item.cancelled_at,
    )


async def create_exception(
    session: AsyncSession,
    equipment_id: str,
    *,
    exception_type: str,
    justification: str,
    actor: CurrentUser,
) -> WorkflowExceptionOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    if equipment.operational_status != "ACTIVE":
        raise DomainError(
            "O equipamento não está ativo — normalize o estado operacional antes de "
            "abrir uma exceção de fluxo."
        )
    existing = (
        await session.execute(
            select(WorkflowException).where(
                WorkflowException.equipment_id == equipment_id,
                WorkflowException.status == "ACTIVE",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(
            "Já existe uma exceção de fluxo ativa para este equipamento. "
            "Cancele-a antes de abrir outra."
        )
    intended_target = _INTENDED_TARGET_STAGE[exception_type]
    if equipment.current_stage >= intended_target:
        raise DomainError(
            f"O equipamento já está na fase {equipment.current_stage} ou além — "
            "esta exceção não se aplica mais."
        )

    item = WorkflowException(
        equipment_id=equipment.id,
        type=exception_type,
        status="ACTIVE",
        source_stage=equipment.current_stage,
        intended_target_stage=intended_target,
        justification=justification,
        created_by_id=actor.id,
    )
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="workflowexception.create",
        entity="WorkflowException",
        entity_id=item.id,
        new_data={
            "type": exception_type,
            "sourceStage": item.source_stage,
            "intendedTargetStage": intended_target,
            "justification": justification,
        },
        metadata={"equipmentId": equipment.id},
    )
    await session.commit()
    actor_ref = UserRefOut(id=actor.id, name=actor.name, email=actor.email)
    return _out(item, actor_ref)


async def cancel_exception(
    session: AsyncSession, equipment_id: str, exception_id: str, actor: CurrentUser
) -> WorkflowExceptionOut:
    assert_can(actor.role, Permission.WORKFLOW_TRANSITION)
    await _get_equipment(session, equipment_id, lock=False, actor=actor)
    item = (
        await session.execute(
            select(WorkflowException).where(
                WorkflowException.id == exception_id,
                WorkflowException.equipment_id == equipment_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise DomainError("Exceção de fluxo não encontrada.")
    if item.status != "ACTIVE":
        raise DomainError("Esta exceção de fluxo já não está ativa.")

    item.status = "CANCELLED"
    item.cancelled_at = utcnow()
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="workflowexception.cancel",
        entity="WorkflowException",
        entity_id=item.id,
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()

    creator = None
    if item.created_by_id:
        row = (
            await session.execute(select(User).where(User.id == item.created_by_id))
        ).scalar_one_or_none()
        if row:
            creator = UserRefOut(id=row.id, name=row.name, email=row.email)
    return _out(item, creator)


async def list_exceptions(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> WorkflowExceptionListOut:
    await _get_equipment(session, equipment_id, lock=False, actor=actor)
    rows = (
        (
            await session.execute(
                select(WorkflowException)
                .where(WorkflowException.equipment_id == equipment_id)
                .order_by(WorkflowException.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    creator_ids = {row.created_by_id for row in rows if row.created_by_id}
    creators: dict[str, UserRefOut] = {}
    if creator_ids:
        users = (
            (await session.execute(select(User).where(User.id.in_(creator_ids)))).scalars().all()
        )
        creators = {u.id: UserRefOut(id=u.id, name=u.name, email=u.email) for u in users}
    return WorkflowExceptionListOut(
        items=[
            _out(row, creators.get(row.created_by_id) if row.created_by_id else None)
            for row in rows
        ]
    )
