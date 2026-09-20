"""Apply transacional: escreve no domínio exatamente o que o plano validado
decidiu, nunca mais e nunca menos.

Não simula o workflow 0-8: `current_stage` é inicializado diretamente pelo
serviço de migração, sem `WorkflowTransition` fictício. Toda escrita gera
`AuditLog` com `action="migration.import"`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.models.common import utcnow
from app.models.equipment import Equipment, EquipmentComponent, EquipmentWorkPackage
from app.models.monday_import import MondayImportBatch, MondayImportRecord, MondayMigrationRun
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.modules.monday_import.plan import (
    ComponentIdentityStrategy,
    EquipmentIdentityStrategy,
    MigrationPlan,
    PlanItem,
    _json_safe,
)
from app.modules.monday_import.service import register_external_mapping
from app.shared.audit import record_audit

_MIGRATION_ACTION = "migration.import"

_SUB_ENTITY_MODELS: dict[str, type[Any]] = {
    "negotiation": Negotiation,
    "legal_process": LegalProcess,
    "contract": Contract,
    "purchase_request": PurchaseRequest,
    "purchase_order": PurchaseOrder,
}
# (nome do atributo na lista do plano) -> (chave do modelo em _SUB_ENTITY_MODELS)
_SUB_ENTITY_LIST_KINDS: dict[str, str] = {
    "negotiations": "negotiation",
    "legal_processes": "legal_process",
    "contracts": "contract",
    "purchase_requests": "purchase_request",
    "purchase_orders": "purchase_order",
}


class PlanStaleError(RuntimeError):
    """O staging ou o mapping mudaram entre `plan` e `apply`."""


class PlanBlockedError(RuntimeError):
    """O plano tem itens BLOCKED; apply é tudo-ou-nada por contexto."""

    def __init__(self, blocked: list[PlanItem]) -> None:
        self.blocked = blocked
        super().__init__(f"{len(blocked)} item(ns) bloqueado(s) no plano")


@dataclass(slots=True)
class ApplyResult:
    migration_run_id: str
    status: str
    counts: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "migrationRunId": self.migration_run_id,
            "status": self.status,
            "counts": self.counts,
        }


def _plan_metadata(
    plan: MigrationPlan, run_id: str, source_key: str, identity_strategy: str
) -> dict[str, Any]:
    return {
        "sourceSystem": "monday",
        "migrationRunId": run_id,
        "batchIds": sorted(plan.batch_ids),
        "sourceKey": source_key,
        "identityStrategy": identity_strategy,
    }


async def _apply_equipment(
    session: AsyncSession, *, plan: MigrationPlan, item: PlanItem, run_id: str, actor: CurrentUser
) -> str:
    if item.action == "NOOP":
        assert item.target_entity_id is not None
        return item.target_entity_id

    work_package_ids: list[str] = list(item.payload.get("work_package_ids", []))
    columns = {key: value for key, value in item.payload.items() if key != "work_package_ids"}

    if item.action == "CREATE":
        equipment = Equipment(project_context_id=plan.project_context_id, **columns)
        if len(work_package_ids) == 1:
            equipment.work_package_id = work_package_ids[0]
        session.add(equipment)
        await session.flush()
        for work_package_id in work_package_ids:
            session.add(EquipmentWorkPackage(equipment_id=equipment.id, work_package_id=work_package_id))
        await register_external_mapping(
            session,
            project_context_id=plan.project_context_id,
            source_entity_type="equipment",
            external_id=item.source_key,
            identity_strategy=EquipmentIdentityStrategy,
            target_entity_type="Equipment",
            target_entity_id=equipment.id,
        )
        await record_audit(
            session,
            user_id=actor.id,
            action=_MIGRATION_ACTION,
            entity="Equipment",
            entity_id=equipment.id,
            new_data=_json_safe({**columns, "workPackageIds": work_package_ids}),
            metadata=_plan_metadata(plan, run_id, item.source_key, EquipmentIdentityStrategy),
        )
        return equipment.id

    assert item.target_entity_id is not None
    existing_equipment = await session.get(Equipment, item.target_entity_id)
    assert existing_equipment is not None
    previous: dict[str, Any] = {}
    for key, value in columns.items():
        previous[key] = getattr(existing_equipment, key)
        setattr(existing_equipment, key, value)
    if "work_package_ids" in item.payload:
        existing_links = (
            (
                await session.execute(
                    select(EquipmentWorkPackage).where(
                        EquipmentWorkPackage.equipment_id == existing_equipment.id
                    )
                )
            )
            .scalars()
            .all()
        )
        previous["work_package_ids"] = sorted(link.work_package_id for link in existing_links)
        wanted = set(work_package_ids)
        for link in existing_links:
            if link.work_package_id not in wanted:
                await session.delete(link)
        current_ids = {link.work_package_id for link in existing_links if link.work_package_id in wanted}
        for work_package_id in wanted - current_ids:
            session.add(
                EquipmentWorkPackage(equipment_id=existing_equipment.id, work_package_id=work_package_id)
            )
        existing_equipment.work_package_id = work_package_ids[0] if len(work_package_ids) == 1 else None
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=_MIGRATION_ACTION,
        entity="Equipment",
        entity_id=existing_equipment.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=_plan_metadata(plan, run_id, item.source_key, EquipmentIdentityStrategy),
    )
    return existing_equipment.id


async def _apply_sub_entity(
    session: AsyncSession,
    *,
    plan: MigrationPlan,
    item: PlanItem,
    model: type[Any],
    equipment_id: str,
    run_id: str,
    actor: CurrentUser,
) -> None:
    if item.action == "NOOP":
        return
    if item.action == "CREATE":
        instance = model(equipment_id=equipment_id, **item.payload)
        session.add(instance)
        await session.flush()
        await record_audit(
            session,
            user_id=actor.id,
            action=_MIGRATION_ACTION,
            entity=model.__name__,
            entity_id=instance.id,
            new_data=_json_safe(item.payload),
            metadata=_plan_metadata(plan, run_id, item.source_key, "equipment-child-v1"),
        )
        return
    assert item.target_entity_id is not None
    instance = await session.get(model, item.target_entity_id)
    assert instance is not None
    previous = {key: getattr(instance, key) for key in item.payload}
    for key, value in item.payload.items():
        setattr(instance, key, value)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=_MIGRATION_ACTION,
        entity=model.__name__,
        entity_id=instance.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=_plan_metadata(plan, run_id, item.source_key, "equipment-child-v1"),
    )


async def _apply_component(
    session: AsyncSession,
    *,
    plan: MigrationPlan,
    item: PlanItem,
    equipment_id: str,
    run_id: str,
    actor: CurrentUser,
) -> None:
    if item.action == "NOOP":
        return
    if item.action == "CREATE":
        component = EquipmentComponent(equipment_id=equipment_id, **item.payload)
        session.add(component)
        await session.flush()
        await register_external_mapping(
            session,
            project_context_id=plan.project_context_id,
            source_entity_type="component",
            external_id=item.source_key,
            identity_strategy=ComponentIdentityStrategy,
            target_entity_type="EquipmentComponent",
            target_entity_id=component.id,
        )
        await record_audit(
            session,
            user_id=actor.id,
            action=_MIGRATION_ACTION,
            entity="EquipmentComponent",
            entity_id=component.id,
            new_data=_json_safe(item.payload),
            metadata=_plan_metadata(plan, run_id, item.source_key, ComponentIdentityStrategy),
        )
        return
    assert item.target_entity_id is not None
    existing_component = await session.get(EquipmentComponent, item.target_entity_id)
    assert existing_component is not None
    previous = {key: getattr(existing_component, key) for key in item.payload}
    for key, value in item.payload.items():
        setattr(existing_component, key, value)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=_MIGRATION_ACTION,
        entity="EquipmentComponent",
        entity_id=existing_component.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=_plan_metadata(plan, run_id, item.source_key, ComponentIdentityStrategy),
    )


async def _stamp_final_entities(
    session: AsyncSession, *, plan: MigrationPlan, resolutions: dict[str, tuple[str, str]]
) -> None:
    """`resolutions`: source_key -> (final_entity_type, final_entity_id)."""
    records = (
        (
            await session.execute(
                select(MondayImportRecord).where(MondayImportRecord.batch_id.in_(plan.batch_ids))
            )
        )
        .scalars()
        .all()
    )
    for record in records:
        resolution = resolutions.get(record.source_key)
        if resolution is None:
            continue
        record.final_entity_type, record.final_entity_id = resolution


async def apply_plan(
    session: AsyncSession,
    *,
    plan: MigrationPlan,
    expected_plan_sha256: str,
    actor: CurrentUser,
) -> ApplyResult:
    if plan.plan_sha256 != expected_plan_sha256:
        raise PlanStaleError(
            "O plano recalculado diverge do hash informado — staging ou mapping mudaram. "
            "Rode `plan` novamente e revise antes de aplicar."
        )
    blocked = [item for items in plan.all_groups.values() for item in items if item.action == "BLOCKED"]
    if blocked:
        raise PlanBlockedError(blocked)

    run = MondayMigrationRun(
        project_context_id=plan.project_context_id,
        status="PLANNED",
        batch_ids=sorted(plan.batch_ids),
        mapping_sha256=plan.mapping_sha256,
        plan_sha256=plan.plan_sha256,
        actor_id=actor.id,
    )
    session.add(run)
    await session.flush()

    try:
        async with session.begin_nested():
            run.status = "APPLYING"
            resolutions: dict[str, tuple[str, str]] = {}
            equipment_ids: dict[str, str] = {}

            for item in plan.equipments:
                equipment_id = await _apply_equipment(
                    session, plan=plan, item=item, run_id=run.id, actor=actor
                )
                equipment_ids[item.source_key] = equipment_id
                resolutions[item.source_key] = ("Equipment", equipment_id)

            for list_name, kind in _SUB_ENTITY_LIST_KINDS.items():
                model = _SUB_ENTITY_MODELS[kind]
                for item in getattr(plan, list_name):
                    parent_key = item.parent_source_key or item.source_key
                    parent_equipment_id = equipment_ids.get(parent_key)
                    if parent_equipment_id is None:
                        raise RuntimeError(f"equipamento pai não resolvido para {item.source_key}")
                    await _apply_sub_entity(
                        session,
                        plan=plan,
                        item=item,
                        model=model,
                        equipment_id=parent_equipment_id,
                        run_id=run.id,
                        actor=actor,
                    )

            for item in plan.components:
                assert item.parent_source_key is not None
                component_parent_id = equipment_ids.get(item.parent_source_key)
                if component_parent_id is None:
                    raise RuntimeError(f"equipamento pai não resolvido para componente {item.source_key}")
                await _apply_component(
                    session,
                    plan=plan,
                    item=item,
                    equipment_id=component_parent_id,
                    run_id=run.id,
                    actor=actor,
                )
                if item.action != "NOOP":
                    resolutions[item.source_key] = (
                        "EquipmentComponent",
                        item.target_entity_id or "",
                    )

            await _stamp_final_entities(session, plan=plan, resolutions=resolutions)

            batches = (
                (
                    await session.execute(
                        select(MondayImportBatch).where(MondayImportBatch.id.in_(plan.batch_ids))
                    )
                )
                .scalars()
                .all()
            )
            for batch in batches:
                batch.status = "APPLIED"
                batch.completed_at = utcnow()

            counts = {name: _summarize(items) for name, items in plan.all_groups.items()}
            run.status = "APPLIED"
            run.summary = counts
            run.completed_at = utcnow()
        await session.commit()
    except Exception as exc:
        run.status = "FAILED"
        run.error = str(exc)[:2000]
        run.completed_at = utcnow()
        await session.commit()
        raise

    return ApplyResult(migration_run_id=run.id, status=run.status, counts=run.summary or {})


def _summarize(items: list[PlanItem]) -> dict[str, int]:
    counts = {"create": 0, "update": 0, "noop": 0}
    for item in items:
        if item.action == "CREATE":
            counts["create"] += 1
        elif item.action == "UPDATE":
            counts["update"] += 1
        elif item.action == "NOOP":
            counts["noop"] += 1
    return counts
