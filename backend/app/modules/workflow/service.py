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
from app.models.supplier import EquipmentSupplier
from app.models.user import User
from app.models.workflow_extras import OperationalStatusEvent, RequirementWaiver
from app.modules.equipments.schemas import UserRefOut
from app.modules.notifications.service import trigger_for_transition
from app.modules.workflow.schemas import (
    AvailableTransitionsOut,
    HistoryEntryOut,
    HistoryOut,
    RequirementGroupOut,
    RequirementWaiverOut,
    TransitionOptionOut,
)
from app.modules.workflow.stages import (
    FINAL_STAGE,
    ProcessState,
    group_spec,
    groups_for,
)
from app.shared.audit import equipment_audit_conditions, record_audit

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
    # GAP-003 (Etapa 6D): só rótulo de apresentação — `action` continua
    # "migration.import" no banco, nada é reescrito.
    "migration.import": "Importado do Monday",
    # Etapa 7B, substituído pela Etapa 7.1 — mantido só para exibir
    # corretamente eventuais registros históricos (não há nenhum em DEV).
    "workflowexception.create": "Exceção de fluxo aberta",
    "workflowexception.cancel": "Exceção de fluxo cancelada",
    "reopenrequest.create": "Reabertura solicitada",
    "reopenrequest.approve": "Reabertura aprovada",
    "reopenrequest.reject": "Reabertura rejeitada",
    "requirementwaiver.create": "Requisito marcado como dispensado",
    "requirementwaiver.revoke": "Dispensa de requisito revogada",
}

_OPERATIONAL_EVENT_TITLES: dict[str, str] = {
    "STANDBY_ENTERED": "Standby ativado",
    "STANDBY_LIFTED": "Standby removido",
    "CANCELLED": "Equipamento cancelado",
    "SANITATION_ENTERED": "Em Saneamento (retorna à Nova Demanda)",
    "SANITATION_ENDED": "Saneamento concluído",
}

_AUDIT_ACTIONS_FOR_EVENT: dict[str, str] = {
    "STANDBY_ENTERED": "equipment.standby_entered",
    "STANDBY_LIFTED": "equipment.standby_lifted",
    "CANCELLED": "equipment.cancelled",
    "SANITATION_ENTERED": "equipment.sanitation_entered",
    "SANITATION_ENDED": "equipment.sanitation_ended",
}

# A transição já entra no histórico pelo próprio workflow_transition; o
# estado operacional já entra pelo próprio operational_status_event — o
# AuditLog é um registro auxiliar, não precisa aparecer duplicado aqui.
_AUDIT_SKIP = {
    "equipment.stage_changed",
    "equipment.standby_entered",
    "equipment.standby_lifted",
    "equipment.cancelled",
    "equipment.sanitation_entered",
    "equipment.sanitation_ended",
}


async def _load_state(session: AsyncSession, equipment_id: str, equipment: Equipment) -> ProcessState:
    async def fetch_one(model: Any) -> Any:
        stmt = select(model).where(model.equipment_id == equipment_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def fetch_many(model: Any) -> list[Any]:
        stmt = select(model).where(model.equipment_id == equipment_id).order_by(model.created_at)
        return list((await session.execute(stmt)).scalars().all())

    has_supplier = (
        await session.execute(
            select(EquipmentSupplier.id).where(EquipmentSupplier.equipment_id == equipment_id)
        )
    ).scalar_one_or_none() is not None

    return ProcessState(
        negotiation=await fetch_one(Negotiation),
        legal=await fetch_one(LegalProcess),
        contracts=await fetch_many(Contract),
        purchase_requests=await fetch_many(PurchaseRequest),
        purchase_orders=await fetch_many(PurchaseOrder),
        equipment=equipment,
        has_supplier=has_supplier,
    )


async def _active_waivers(
    session: AsyncSession, equipment_id: str, stage: int
) -> dict[str, RequirementWaiver]:
    stmt = select(RequirementWaiver).where(
        RequirementWaiver.equipment_id == equipment_id,
        RequirementWaiver.stage == stage,
        RequirementWaiver.status == "ACTIVE",
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {row.requirement_group_code: row for row in rows}


async def _waiver_out(session: AsyncSession, waiver: RequirementWaiver) -> RequirementWaiverOut:
    creator = None
    if waiver.created_by_id:
        row = (
            await session.execute(select(User).where(User.id == waiver.created_by_id))
        ).scalar_one_or_none()
        if row:
            creator = UserRefOut(id=row.id, name=row.name, email=row.email)
    spec = group_spec(waiver.requirement_group_code)
    return RequirementWaiverOut(
        id=waiver.id,
        equipment_id=waiver.equipment_id,
        stage=waiver.stage,
        requirement_group_code=waiver.requirement_group_code,
        requirement_group_label=spec.label if spec is not None else waiver.requirement_group_code,
        reason_code=waiver.reason_code,
        justification=waiver.justification,
        status=waiver.status,
        created_by=creator,
        created_at=waiver.created_at,
        revoked_by=None,
        revoked_at=waiver.revoked_at,
        revoke_reason=waiver.revoke_reason,
    )


async def _evaluate(
    session: AsyncSession, from_stage: int, state: ProcessState
) -> list[RequirementGroupOut]:
    """Etapa 7.1: status por GRUPO — SATISFIED (dados completos), WAIVED
    (incompleto, mas com `RequirementWaiver` ACTIVE) ou MISSING (bloqueia o
    avanço). O motor nunca aceita `force=true`: só os grupos que
    `app.modules.workflow.stages` marca como `waivable` podem ficar WAIVED,
    e só quando alguém de fato registrou a dispensa."""
    waivers = await _active_waivers(session, state.equipment.id if state.equipment else "", from_stage)
    groups: list[RequirementGroupOut] = []
    for spec in groups_for(from_stage):
        satisfied = spec.check(state)
        waiver = waivers.get(spec.code)
        if satisfied:
            status: Literal["SATISFIED", "WAIVED", "MISSING"] = "SATISFIED"
        elif waiver is not None:
            status = "WAIVED"
        else:
            status = "MISSING"
        groups.append(
            RequirementGroupOut(
                code=spec.code,
                label=spec.label,
                status=status,
                waivable=spec.waivable,
                fields=list(spec.fields),
                message=spec.message,
                waiver=(await _waiver_out(session, waiver)) if waiver is not None else None,
            )
        )
    return groups


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
    state = await _load_state(session, equipment_id, equipment)
    current = equipment.current_stage
    options: list[TransitionOptionOut] = []

    if current < FINAL_STAGE:
        groups = await _evaluate(session, current, state)
        missing = [item for item in groups if item.status == "MISSING"]
        allowed = (
            actor_can(actor, Permission.WORKFLOW_TRANSITION)
            and equipment.operational_status == "ACTIVE"
        )
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
                    else (
                        "O equipamento não está ativo (Standby/Cancelado/Em Saneamento) — "
                        "normalize o estado operacional antes de avançar."
                        if equipment.operational_status != "ACTIVE"
                        else "Seu perfil não tem permissão para avançar etapas."
                    )
                ),
                requirement_groups=groups,
            )
        )

    # Etapa 7C: reabertura deixou de ser uma opção imediata aqui — agora
    # passa por `ReopenRequest` (solicitação + aprovação por permissão
    # superior). Ver `app.modules.workflow.reopen`.
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


def _classify(current: int, target: int) -> Literal["advance"]:
    if target == current + 1 and target <= FINAL_STAGE:
        return "advance"
    if target == current:
        raise ConflictError(
            f"O equipamento já está na etapa {current} · {STAGES[current]}. "
            "Recarregue a página antes de tentar novamente."
        )
    if target < current:
        raise DomainError(
            "Reabertura não é feita por aqui — solicite reabertura com aprovação "
            "(endpoint de solicitação de reabertura)."
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

    if equipment.operational_status != "ACTIVE":
        raise DomainError(
            "O equipamento não está ativo (Standby/Cancelado/Em Saneamento) — "
            "normalize o estado operacional antes de avançar."
        )
    state = await _load_state(session, equipment_id, equipment)
    missing = [item for item in await _evaluate(session, from_stage, state) if item.status == "MISSING"]
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

    transition = WorkflowTransition(
        equipment_id=equipment.id,
        from_stage=from_stage,
        to_stage=target_stage,
        reason=clean_reason,
        actor_id=actor.id,
    )
    session.add(transition)
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

    # Etapa 7F: Kickoff (conclusão da fase 5) / FUP (conclusão da fase 7).
    # Roda DEPOIS do commit da fase — falha de notificação nunca desfaz nem
    # bloqueia a transição real.
    if kind == "advance":
        await trigger_for_transition(session, equipment=equipment, transition=transition)

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
    conditions = await equipment_audit_conditions(session, equipment_id)
    audits = (
        (await session.execute(select(AuditLog).where(or_(*conditions))))
        .scalars()
        .all()
    )
    operational_events = (
        (
            await session.execute(
                select(OperationalStatusEvent).where(
                    OperationalStatusEvent.equipment_id == equipment_id
                )
            )
        )
        .scalars()
        .all()
    )

    actor_ids = {item.actor_id for item in transitions if item.actor_id}
    actor_ids |= {item.userId for item in audits if item.userId}
    actor_ids |= {item.actor_id for item in operational_events if item.actor_id}
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
            title=(
                f"{_AUDIT_TITLES.get(item.action, item.action)} "
                f"({(item.newData or {}).get('requirementGroupCode')})"
                if item.action in ("requirementwaiver.create", "requirementwaiver.revoke")
                and (item.newData or {}).get("requirementGroupCode")
                else _AUDIT_TITLES.get(item.action, item.action)
            ),
            actor=actors.get(item.userId) if item.userId else None,
            occurred_at=item.createdAt,
            # Etapa 7.1: mesma vitrine usada por Standby/Saneamento/Cancelado
            # — justificativa legível direto no histórico, sem abrir o JSON.
            justification=(
                (item.newData or {}).get("justification")
                if item.action == "requirementwaiver.create"
                else (item.newData or {}).get("revokeReason")
                if item.action == "requirementwaiver.revoke"
                else None
            ),
            previous_data=item.previousData,
            new_data=item.newData,
        )
        for item in audits
        if item.action not in _AUDIT_SKIP
    )
    entries.extend(
        HistoryEntryOut(
            id=item.id,
            kind="operational_status",
            action=_AUDIT_ACTIONS_FOR_EVENT.get(item.kind, item.kind),
            title=_OPERATIONAL_EVENT_TITLES.get(item.kind, item.kind),
            from_stage=item.stage_at_event,
            from_stage_label=STAGES.get(item.stage_at_event),
            justification=item.justification or None,
            actor=actors.get(item.actor_id) if item.actor_id else None,
            occurred_at=item.occurred_at,
        )
        for item in operational_events
    )
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return HistoryOut(items=entries)
