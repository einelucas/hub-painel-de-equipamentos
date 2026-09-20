"""Serviço único de transição de etapa do equipamento.

Nenhum outro caminho pode alterar `equipment.current_stage`. A operação roda
dentro de uma transação com o equipamento bloqueado, revalida a etapa antes do
commit e registra `workflow_transition` + auditoria de forma atômica.
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.permissions import Permission, assert_can
from app.core.scope import assert_equipment_allowed
from app.models.audit import AuditLog
from app.models.equipment import STAGES, Equipment, WorkflowTransition
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)
from app.models.user import User
from app.modules.equipments.schemas import UserRefOut
from app.modules.workflow.schemas import (
    AvailableTransitionsOut,
    HistoryEntryOut,
    HistoryOut,
    RequirementOut,
    TransitionOptionOut,
)
from app.modules.workflow.stages import (
    FINAL_STAGE,
    MIN_REOPEN_SOURCE_STAGE,
    REOPEN_STAGE,
    ProcessState,
    requirements_for,
)
from app.shared.audit import record_audit

_AUDIT_TITLES: dict[str, str] = {
    "equipment.create": "Equipamento cadastrado",
    "equipment.update": "Dados mestres atualizados",
    "component.create": "Componente adicionado",
    "component.update": "Componente atualizado",
    "negotiation.update": "Negociação atualizada",
    "legalprocess.update": "Processo jurídico atualizado",
    "contract.update": "Contrato atualizado",
    "purchaserequest.update": "SC/OCI atualizada",
    "purchaseorder.update": "Ordem de compra atualizada",
}

# A transição já entra no histórico pelo próprio workflow_transition.
_AUDIT_SKIP = {"equipment.stage_changed"}


async def _load_state(session: AsyncSession, equipment_id: str) -> ProcessState:
    async def fetch(model: Any) -> Any:
        stmt = select(model).where(model.equipment_id == equipment_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    return ProcessState(
        negotiation=await fetch(Negotiation),
        legal=await fetch(LegalProcess),
        contract=await fetch(Contract),
        purchase_request=await fetch(PurchaseRequest),
        purchase_order=await fetch(PurchaseOrder),
    )


def _evaluate(from_stage: int, state: ProcessState) -> list[RequirementOut]:
    return [
        RequirementOut(
            code=spec.code,
            field=spec.field,
            message=spec.message,
            satisfied=spec.check(state),
        )
        for spec in requirements_for(from_stage)
    ]


async def _get_equipment(
    session: AsyncSession, equipment_id: str, *, lock: bool, actor: CurrentUser
) -> Equipment:
    # Escopo antes de qualquer leitura: UUID conhecido não dá acesso a outra unidade.
    await assert_equipment_allowed(session, actor, equipment_id)
    stmt = select(Equipment).where(Equipment.id == equipment_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    equipment = (await session.execute(stmt)).scalar_one_or_none()
    if equipment is None:
        raise NotFoundError("Equipamento não encontrado")
    return equipment


async def available_transitions(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> AvailableTransitionsOut:
    equipment = await _get_equipment(session, equipment_id, lock=False, actor=actor)
    state = await _load_state(session, equipment_id)
    current = equipment.current_stage
    options: list[TransitionOptionOut] = []

    if current < FINAL_STAGE:
        requirements = _evaluate(current, state)
        missing = [item for item in requirements if not item.satisfied]
        allowed = actor_can(actor, Permission.WORKFLOW_TRANSITION)
        options.append(
            TransitionOptionOut(
                target_stage=current + 1,
                target_stage_label=STAGES[current + 1],
                kind="advance",
                can_execute=not missing and allowed,
                requires_reason=False,
                blocked_reason=(
                    None
                    if allowed
                    else "Seu perfil não tem permissão para avançar etapas."
                ),
                requirements=requirements,
                satisfied_requirements=[item for item in requirements if item.satisfied],
                missing_requirements=missing,
            )
        )

    if current >= MIN_REOPEN_SOURCE_STAGE:
        allowed = actor_can(actor, Permission.WORKFLOW_REOPEN)
        options.append(
            TransitionOptionOut(
                target_stage=REOPEN_STAGE,
                target_stage_label=STAGES[REOPEN_STAGE],
                kind="reopen",
                can_execute=allowed,
                requires_reason=True,
                blocked_reason=(
                    None if allowed else "A reabertura é restrita ao perfil administrativo."
                ),
                requirements=[],
                satisfied_requirements=[],
                missing_requirements=[],
            )
        )

    return AvailableTransitionsOut(
        current_stage=current,
        current_stage_label=STAGES[current],
        transitions=options,
    )


def actor_can(actor: CurrentUser, permission: Permission) -> bool:
    try:
        assert_can(actor.role, permission)
    except Exception:
        return False
    return True


def _classify(current: int, target: int) -> Literal["advance", "reopen"]:
    if target == REOPEN_STAGE and current >= MIN_REOPEN_SOURCE_STAGE:
        return "reopen"
    if target == current + 1 and target <= FINAL_STAGE:
        return "advance"
    if target <= current:
        raise ConflictError(
            f"O equipamento já está na etapa {current} · {STAGES[current]}. "
            "Recarregue a página antes de tentar novamente."
        )
    raise DomainError(
        "Não é possível pular etapas. Avance uma etapa por vez a partir da etapa atual."
    )


async def execute_transition(
    session: AsyncSession,
    *,
    equipment_id: str,
    target_stage: int,
    reason: str | None,
    actor: CurrentUser,
) -> AvailableTransitionsOut:
    equipment = await _get_equipment(session, equipment_id, lock=True, actor=actor)
    from_stage = equipment.current_stage
    kind = _classify(from_stage, target_stage)
    clean_reason = reason.strip() if reason else None

    if kind == "reopen":
        assert_can(actor.role, Permission.WORKFLOW_REOPEN)
        if not clean_reason:
            raise DomainError("Informe o motivo da reabertura.")
    else:
        state = await _load_state(session, equipment_id)
        missing = [item for item in _evaluate(from_stage, state) if not item.satisfied]
        if missing:
            pending = " ".join(item.message for item in missing)
            raise DomainError(f"Requisitos pendentes para avançar: {pending}")

    stored_stage = (
        await session.execute(select(Equipment.current_stage).where(Equipment.id == equipment_id))
    ).scalar_one()
    if stored_stage != from_stage:
        raise ConflictError(
            "A etapa do equipamento foi alterada por outro usuário. Recarregue a página."
        )

    session.add(
        WorkflowTransition(
            equipment_id=equipment.id,
            from_stage=from_stage,
            to_stage=target_stage,
            reason=clean_reason,
            actor_id=actor.id,
        )
    )
    equipment.current_stage = target_stage
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="equipment.stage_changed",
        entity="Equipment",
        entity_id=equipment.id,
        previous_data={"current_stage": from_stage},
        new_data={"current_stage": target_stage, "reason": clean_reason},
        metadata={"equipmentId": equipment.id, "kind": kind},
    )
    await session.commit()
    return await available_transitions(session, equipment_id, actor)


async def history(session: AsyncSession, equipment_id: str, actor: CurrentUser) -> HistoryOut:
    await _get_equipment(session, equipment_id, lock=False, actor=actor)
    transitions = (
        (
            await session.execute(
                select(WorkflowTransition).where(WorkflowTransition.equipment_id == equipment_id)
            )
        )
        .scalars()
        .all()
    )
    audits = (
        (
            await session.execute(
                select(AuditLog).where(
                    or_(
                        AuditLog.entityId == equipment_id,
                        AuditLog.metadata_["equipmentId"].astext == equipment_id,
                    )
                )
            )
        )
        .scalars()
        .all()
    )

    actor_ids = {item.actor_id for item in transitions if item.actor_id}
    actor_ids |= {item.userId for item in audits if item.userId}
    actors: dict[str, UserRefOut] = {}
    if actor_ids:
        rows = (
            (await session.execute(select(User).where(User.id.in_(actor_ids)))).scalars().all()
        )
        actors = {
            row.id: UserRefOut(id=row.id, name=row.name, email=row.email) for row in rows
        }

    entries: list[HistoryEntryOut] = [
        HistoryEntryOut(
            id=item.id,
            kind="transition",
            action="equipment.stage_changed",
            title=f"{STAGES[item.from_stage]} → {STAGES[item.to_stage]}",
            from_stage=item.from_stage,
            from_stage_label=STAGES[item.from_stage],
            to_stage=item.to_stage,
            to_stage_label=STAGES[item.to_stage],
            reason=item.reason,
            actor=actors.get(item.actor_id) if item.actor_id else None,
            occurred_at=item.occurred_at,
        )
        for item in transitions
    ]
    entries.extend(
        HistoryEntryOut(
            id=item.id,
            kind="change",
            action=item.action,
            title=_AUDIT_TITLES.get(item.action, item.action),
            actor=actors.get(item.userId) if item.userId else None,
            occurred_at=item.createdAt,
            previous_data=item.previousData,
            new_data=item.newData,
        )
        for item in audits
        if item.action not in _AUDIT_SKIP
    )
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return HistoryOut(items=entries)
