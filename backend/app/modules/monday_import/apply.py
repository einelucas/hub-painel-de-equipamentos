"""Apply transacional: escreve no domínio exatamente o que o plano validado
decidiu, nunca mais e nunca menos.

Não simula o workflow 0-8: `current_stage` é inicializado diretamente pelo
serviço de migração, sem `WorkflowTransition` fictício. Toda escrita gera
`AuditLog` com `action="migration.import"`.

Catálogos planejados como CREATE (EAP PROCESS → AREA, Discipline, WorkPackage e
ProjectEap) são criados na MESMA transação, antes dos equipamentos; os
IDs novos substituem as `catalog_refs` do payload. Qualquer falha desfaz tudo.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.models.common import utcnow
from app.models.equipment import (
    Discipline,
    EapNode,
    Equipment,
    EquipmentComponent,
    EquipmentWorkPackage,
    ProjectEap,
    WorkPackage,
)
from app.models.monday_import import MondayImportBatch, MondayImportRecord, MondayMigrationRun
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.models.supplier import EquipmentSupplier
from app.modules.monday_import.catalog_taxonomy import CatalogAction
from app.modules.monday_import.plan import (
    OPERATIONAL_TRANSITIONS,
    CatalogPlanItem,
    MigrationPlan,
    PlanItem,
    _json_safe,
    component_identity_strategy,
    equipment_identity_strategy,
)
from app.modules.monday_import.service import register_external_mapping
from app.modules.workflow.operational_status import record_operational_status_change
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
class _CreatedCatalogs:
    """IDs dos catálogos existentes/criados, pela chave usada no plan."""

    eap: dict[str, str] = field(default_factory=dict)
    discipline: dict[str, str] = field(default_factory=dict)
    work_package: dict[str, str] = field(default_factory=dict)


_EAP_LEVEL_ORDER = {"PROCESS": 0, "AREA": 1}


async def _audit_catalog(
    session: AsyncSession, *, plan: MigrationPlan, run_id: str, actor: CurrentUser,
    entity: str, entity_id: str, item: CatalogPlanItem, data: dict[str, Any],
) -> None:
    await record_audit(
        session,
        user_id=actor.id,
        action=_MIGRATION_ACTION,
        entity=entity,
        entity_id=entity_id,
        new_data=_json_safe(data),
        metadata={
            **_plan_metadata(plan, run_id, item.key, "catalog"),
            "catalogKind": item.kind,
            "evidenceSource": item.evidence_source,
        },
    )


async def _apply_catalogs(
    session: AsyncSession, *, plan: MigrationPlan, run_id: str, actor: CurrentUser
) -> _CreatedCatalogs:
    """Cria, na transação corrente, os catálogos que o plan revisado marcou como CREATE.

    Se algum já existir neste momento (criado por fora entre plan e apply), o
    plano está velho: PlanStaleError desfaz tudo e pede novo plan.
    """
    created = _CreatedCatalogs()
    creates = [item for item in plan.catalog_items if item.action is CatalogAction.CREATE]

    eap_items = sorted(
        (item for item in creates if item.kind == "eap_node"),
        key=lambda item: (_EAP_LEVEL_ORDER.get(str(item.payload.get("level")), 9), item.key),
    )
    for item in eap_items:
        code = str(item.payload["code"])
        if await session.scalar(select(EapNode.id).where(EapNode.code == code)) is not None:
            raise PlanStaleError(f"EAP {code} passou a existir após o plano. Gere o plano novamente.")
        parent_code = item.payload.get("parentCode")
        parent_id: str | None = None
        if parent_code:
            parent_id = created.eap.get(str(parent_code)) or await session.scalar(
                select(EapNode.id).where(EapNode.code == parent_code, EapNode.active.is_(True))
            )
            if parent_id is None:
                raise PlanStaleError(f"Processo pai {parent_code} da EAP {code} não existe mais.")
        node = EapNode(
            code=code, name=str(item.payload["name"]), level=str(item.payload["level"]), parent_id=parent_id
        )
        session.add(node)
        await session.flush()
        created.eap[code] = node.id
        await _audit_catalog(
            session, plan=plan, run_id=run_id, actor=actor, entity="EapNode", entity_id=node.id, item=item,
            data=dict(item.payload),
        )

    discipline_by_code: dict[str, str] = {}
    for item in (item for item in creates if item.kind == "discipline"):
        code = str(item.payload["code"])
        if code in discipline_by_code:
            # Outro valor da origem (alias explícito) aponta para a mesma disciplina.
            created.discipline[item.key] = discipline_by_code[code]
            continue
        if await session.scalar(select(Discipline.id).where(Discipline.code == code)) is not None:
            raise PlanStaleError(f"Disciplina {code} passou a existir após o plano. Gere o plano novamente.")
        discipline = Discipline(code=code, name=str(item.payload.get("name") or item.key))
        session.add(discipline)
        await session.flush()
        created.discipline[item.key] = discipline.id
        discipline_by_code[code] = discipline.id
        await _audit_catalog(
            session, plan=plan, run_id=run_id, actor=actor, entity="Discipline", entity_id=discipline.id,
            item=item, data={"code": discipline.code, "name": discipline.name},
        )

    for item in (item for item in creates if item.kind == "work_package"):
        code = str(item.payload["code"])
        exists = await session.scalar(
            select(WorkPackage.id).where(WorkPackage.code == code)
        )
        if exists is not None:
            raise PlanStaleError(
                f"Work Package {code} passou a existir após o plano. Gere o plano novamente."
            )
        work_package = WorkPackage(code=code, name=str(item.payload["name"]))
        session.add(work_package)
        await session.flush()
        created.work_package[item.key] = work_package.id
        await _audit_catalog(
            session, plan=plan, run_id=run_id, actor=actor, entity="WorkPackage", entity_id=work_package.id,
            item=item, data={"code": code, "name": work_package.name},
        )

    for item in (item for item in creates if item.kind == "project_eap"):
        node_id = item.target_id or created.eap.get(item.key)
        if node_id is None:
            raise RuntimeError(f"ProjectEap sem EAP resolvida para {item.key}")
        linked = await session.scalar(
            select(ProjectEap.id).where(
                ProjectEap.project_context_id == plan.project_context_id, ProjectEap.eap_node_id == node_id
            )
        )
        if linked is not None:
            continue  # idempotente: vínculo já existe
        link = ProjectEap(project_context_id=plan.project_context_id, eap_node_id=node_id)
        session.add(link)
        await session.flush()
        await _audit_catalog(
            session, plan=plan, run_id=run_id, actor=actor, entity="ProjectEap", entity_id=link.id, item=item,
            data={"projectContextId": plan.project_context_id, "eapNodeId": node_id},
        )
    return created


def _materialize(item: PlanItem, created: _CreatedCatalogs) -> PlanItem:
    """Troca as referências a catálogos criados pelos IDs reais."""
    refs = item.payload.get("catalog_refs")
    if not refs:
        return item
    payload = {key: value for key, value in item.payload.items() if key != "catalog_refs"}
    if "eapCode" in refs:
        payload["eap_node_id"] = created.eap[refs["eapCode"]]
    if "discipline" in refs:
        payload["discipline_id"] = created.discipline[refs["discipline"]]
    if "workPackageCodes" in refs and "work_package_ids" in payload:
        new_ids = {created.work_package[code] for code in refs["workPackageCodes"]}
        payload["work_package_ids"] = sorted(set(payload["work_package_ids"]) | new_ids)
    return replace(item, payload=payload)


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


async def _apply_operational_status(
    session: AsyncSession,
    *,
    plan: MigrationPlan,
    equipment: Equipment,
    target: str,
    run_id: str,
    source_key: str,
    actor: CurrentUser,
) -> None:
    """Estado operacional da origem via evento do domínio (nunca coluna isolada)."""
    kind = OPERATIONAL_TRANSITIONS[(equipment.operational_status, target)]
    await record_operational_status_change(
        session,
        equipment=equipment,
        kind=kind,
        resulting_status=target,
        stage_at_event=equipment.current_stage,
        justification="Importação Monday: estado operacional informado no status da origem.",
        actor_id=actor.id,
        audit_action=_MIGRATION_ACTION,
        audit_metadata=_plan_metadata(plan, run_id, source_key, equipment_identity_strategy(source_key)),
    )


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
    columns = {
        key: value
        for key, value in item.payload.items()
        if key not in {"work_package_ids", "operational_status", "supplier_id", "catalog_refs"}
    }
    operational_target = item.payload.get("operational_status")
    supplier_id = item.payload.get("supplier_id")

    if item.action == "CREATE":
        equipment = Equipment(project_context_id=plan.project_context_id, **columns)
        if len(work_package_ids) == 1:
            equipment.work_package_id = work_package_ids[0]
        session.add(equipment)
        await session.flush()
        for work_package_id in work_package_ids:
            session.add(EquipmentWorkPackage(equipment_id=equipment.id, work_package_id=work_package_id))
        if supplier_id is not None:
            session.add(
                EquipmentSupplier(
                    equipment_id=equipment.id,
                    supplier_id=supplier_id,
                    is_primary=True,
                    start_stage=equipment.current_stage,
                    source="MONDAY_CONFIRMED",
                    changed_by_user_id=actor.id,
                )
            )
        await register_external_mapping(
            session,
            project_context_id=plan.project_context_id,
            source_entity_type="equipment",
            external_id=item.source_key,
            identity_strategy=equipment_identity_strategy(item.source_key),
            target_entity_type="Equipment",
            target_entity_id=equipment.id,
        )
        await record_audit(
            session,
            user_id=actor.id,
            action=_MIGRATION_ACTION,
            entity="Equipment",
            entity_id=equipment.id,
            new_data=_json_safe({**columns, "workPackageIds": work_package_ids, "supplierId": supplier_id}),
            metadata=_plan_metadata(
                plan, run_id, item.source_key, equipment_identity_strategy(item.source_key)
            ),
        )
        if operational_target is not None:
            await _apply_operational_status(
                session,
                plan=plan,
                equipment=equipment,
                target=operational_target,
                run_id=run_id,
                source_key=item.source_key,
                actor=actor,
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
    if supplier_id is not None:
        # A seleção veio explicitamente de `supplierSelections`. A troca
        # preserva a linha anterior e abre um único vínculo ativo.
        current_supplier = await session.scalar(
            select(EquipmentSupplier).where(
                EquipmentSupplier.equipment_id == existing_equipment.id,
                EquipmentSupplier.ended_at.is_(None),
            )
        )
        previous["supplier_id"] = current_supplier.supplier_id if current_supplier else None
        if current_supplier is not None and current_supplier.supplier_id != supplier_id:
            current_supplier.ended_at = utcnow()
            current_supplier.end_stage = existing_equipment.current_stage
            current_supplier.is_primary = False
            current_supplier.change_reason = "Substituído durante revisão da importação Monday"
            current_supplier.changed_by_user_id = actor.id
            await session.flush()
        if current_supplier is None or current_supplier.supplier_id != supplier_id:
            session.add(
                EquipmentSupplier(
                    equipment_id=existing_equipment.id,
                    supplier_id=supplier_id,
                    is_primary=True,
                    start_stage=existing_equipment.current_stage,
                    source="MONDAY_CONFIRMED",
                    changed_by_user_id=actor.id,
                )
            )
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=_MIGRATION_ACTION,
        entity="Equipment",
        entity_id=existing_equipment.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=_plan_metadata(plan, run_id, item.source_key, equipment_identity_strategy(item.source_key)),
    )
    if operational_target is not None:
        await _apply_operational_status(
            session,
            plan=plan,
            equipment=existing_equipment,
            target=operational_target,
            run_id=run_id,
            source_key=item.source_key,
            actor=actor,
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
            identity_strategy=component_identity_strategy(item.source_key),
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
            metadata=_plan_metadata(
                plan, run_id, item.source_key, component_identity_strategy(item.source_key)
            ),
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
        metadata=_plan_metadata(plan, run_id, item.source_key, component_identity_strategy(item.source_key)),
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
            created = await _apply_catalogs(session, plan=plan, run_id=run.id, actor=actor)

            for planned in plan.equipments:
                item = _materialize(planned, created)
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
            counts["catalogs"] = {
                kind: len(ids)
                for kind, ids in (
                    ("eapNodes", created.eap),
                    ("disciplines", created.discipline),
                    ("workPackages", created.work_package),
                    ("suppliers", {}),
                )
            }
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
