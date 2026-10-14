"""Apply transacional: escreve no domínio exatamente o que o plano validado
decidiu, nunca mais e nunca menos.

Não simula o workflow 0-8: `current_stage` é inicializado diretamente pelo
serviço de migração, sem `WorkflowTransition` fictício. Toda escrita gera
`AuditLog` com `action="migration.import"`.

Catálogos planejados como CREATE (EAP PROCESS → AREA, Discipline, WorkPackage e
ProjectEap) são criados na MESMA transação, antes dos equipamentos; os
IDs novos substituem as `catalog_refs` do payload. Qualquer falha desfaz tudo.

O banco é remoto (Neon): o apply roda em duas fases para não pagar round-trips
por linha. (1) Em memória: percorre o plano e monta as linhas de cada tabela
(IDs gerados na aplicação), reaproveitando o `_PlanPrefetch` do `build_plan`.
(2) Escrita: uma tabela por vez, na ordem das FKs, com INSERT multi-VALUES e
UPDATE via executemany — mesmo resultado final do apply linha a linha.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import Table, any_, bindparam, delete, select, update
from sqlalchemy import cast as cast_
from sqlalchemy import column as sa_column
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import values as sa_values
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.util import identity_key
from sqlalchemy.types import String

from app.core.auth import CurrentUser
from app.models.audit import AuditLog
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
from app.models.monday_import import (
    ExternalMapping,
    MondayImportBatch,
    MondayImportRecord,
    MondayMigrationRun,
)
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.models.supplier import EquipmentSupplier
from app.models.workflow_extras import OperationalStatusEvent
from app.modules.monday_import.catalog_taxonomy import CatalogAction
from app.modules.monday_import.mappings import SOURCE_SYSTEM
from app.modules.monday_import.plan import (
    OPERATIONAL_TRANSITIONS,
    CatalogPlanItem,
    MigrationPlan,
    PlanItem,
    _chunks,
    _json_safe,
    component_identity_strategy,
    equipment_identity_strategy,
)
from app.modules.workflow.operational_status import build_operational_status_change_rows
from app.shared.audit import build_audit_row, bulk_insert_audit, chunk_size_for

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

# Ordem de escrita (FKs): catálogos → equipamento → filhos. Mapeamentos, eventos
# de estado operacional e auditoria vêm depois, em `_write`.
_WRITE_ORDER: tuple[type[Any], ...] = (
    EapNode,
    Discipline,
    WorkPackage,
    ProjectEap,
    Equipment,
    EquipmentWorkPackage,
    EquipmentSupplier,
    Negotiation,
    LegalProcess,
    Contract,
    PurchaseRequest,
    PurchaseOrder,
    EquipmentComponent,
)
# Linhas por statement: tabelas sem JSONB usam o limite de binds (até 1000);
# as com JSONB potencialmente grande (auditoria, mapeamento) usam lotes menores.
_DEFAULT_ROWS_PER_STATEMENT = 1000
_JSONB_ROWS_PER_STATEMENT = 500
_UPDATE_ROWS_PER_STATEMENT = 1000
_EXTERNAL_MAPPING_CONFLICT = ["project_context_id", "source_system", "source_entity_type", "external_id"]


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


# --- linhas em memória -----------------------------------------------------------------


def _new_row(model: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    """Linha (nomes de coluna) de um INSERT, com os defaults Python que o ORM
    aplicaria no flush (id, timestamps, flags). Colunas sem valor nem default
    ficam fora, exatamente como no INSERT do ORM."""
    columns = sa_inspect(model).columns
    row = {columns[attr].key: value for attr, value in values.items()}
    for column in model.__table__.columns:
        default = column.default
        if column.key in row or default is None:
            continue
        if default.is_scalar:
            row[column.key] = default.arg
        elif default.is_callable:
            row[column.key] = default.arg(None)
    return row


def _changes(model: type[Any], instance: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Só os atributos que de fato mudam — mesma comparação do flush do ORM
    (`type.compare_values`); se nada muda, o ORM não emite UPDATE."""
    columns = sa_inspect(model).columns
    return {
        attr: value
        for attr, value in values.items()
        if columns[attr].type.compare_values(getattr(instance, attr), value) is not True
    }


@dataclass(slots=True)
class _WriteSet:
    """Tudo o que a fase de escrita grava, por tabela."""

    inserts: dict[type[Any], list[dict[str, Any]]] = field(default_factory=dict)
    # model -> [(id, {atributo: valor})]
    updates: dict[type[Any], list[tuple[str, dict[str, Any]]]] = field(default_factory=dict)
    deletes: dict[type[Any], list[str]] = field(default_factory=dict)
    mappings: list[dict[str, Any]] = field(default_factory=list)
    status_events: list[dict[str, Any]] = field(default_factory=list)
    audits: list[dict[str, Any]] = field(default_factory=list)
    # Objetos ORM já na sessão: depois da escrita recebem os valores gravados
    # (sem marcar como sujos), para a sessão não ficar com estado velho.
    synced: list[tuple[Any, dict[str, Any]]] = field(default_factory=list)
    expunge: list[Any] = field(default_factory=list)
    expire_links: list[Any] = field(default_factory=list)

    def insert(self, model: type[Any], values: dict[str, Any]) -> dict[str, Any]:
        row = _new_row(model, values)
        self.inserts.setdefault(model, []).append(row)
        return row

    def update(self, model: type[Any], instance: Any, values: dict[str, Any]) -> None:
        if not values:
            return
        values = dict(values)
        for column in model.__table__.columns:
            # `onupdate` (updated_at) como o ORM aplicaria no UPDATE.
            if column.onupdate is not None and column.key not in values and column.onupdate.is_callable:
                values[column.key] = column.onupdate.arg(None)
        self.updates.setdefault(model, []).append((instance.id, values))
        self.synced.append((instance, values))

    def audit(self, **kwargs: Any) -> None:
        self.audits.append(build_audit_row(action=_MIGRATION_ACTION, **kwargs))

    def mapping(
        self,
        *,
        project_context_id: str,
        source_entity_type: str,
        external_id: str,
        identity_strategy: str,
        target_entity_type: str,
        target_entity_id: str,
    ) -> None:
        self.mappings.append(
            _new_row(
                ExternalMapping,
                {
                    "project_context_id": project_context_id,
                    "source_system": SOURCE_SYSTEM,
                    "source_entity_type": source_entity_type,
                    "external_id": external_id,
                    "identity_strategy": identity_strategy,
                    "target_entity_type": target_entity_type,
                    "target_entity_id": target_entity_id,
                    "raw_identity": None,
                },
            )
        )


@dataclass(slots=True)
class _ApplyContext:
    plan: MigrationPlan
    run_id: str
    actor: CurrentUser
    writes: _WriteSet = field(default_factory=_WriteSet)
    created: _CreatedCatalogs = field(default_factory=_CreatedCatalogs)
    # Estado atual do que o plano atualiza (prefetch do plano ou consulta em lote).
    equipments: dict[str, Equipment] = field(default_factory=dict)
    work_package_links: dict[str, list[EquipmentWorkPackage]] = field(default_factory=dict)
    # equipment_id -> (id da linha EquipmentSupplier ativa, supplier_id) | None
    active_supplier: dict[str, tuple[str, str] | None] = field(default_factory=dict)
    sub_entities: dict[type[Any], dict[str, Any]] = field(default_factory=dict)
    components: dict[str, EquipmentComponent] = field(default_factory=dict)
    identity_map: Any = None


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


# --- catálogos -------------------------------------------------------------------------


def _audit_catalog(
    ctx: _ApplyContext, *, entity: str, entity_id: str, item: CatalogPlanItem, data: dict[str, Any]
) -> None:
    ctx.writes.audit(
        user_id=ctx.actor.id,
        entity=entity,
        entity_id=entity_id,
        new_data=_json_safe(data),
        metadata={
            **_plan_metadata(ctx.plan, ctx.run_id, item.key, "catalog"),
            "catalogKind": item.kind,
            "evidenceSource": item.evidence_source,
        },
    )


async def _existing_codes(
    session: AsyncSession, model: type[Any], codes: Iterable[str]
) -> dict[str, tuple[str, bool]]:
    """code -> (id, active), em uma consulta `IN (...)` por lote de códigos."""
    found: dict[str, tuple[str, bool]] = {}
    for chunk in _chunks(codes):
        rows = await session.execute(select(model.code, model.id, model.active).where(model.code.in_(chunk)))
        for code, entity_id, active in rows:
            found.setdefault(code, (entity_id, bool(active)))
    return found


async def _apply_catalogs(session: AsyncSession, ctx: _ApplyContext) -> _CreatedCatalogs:
    """Monta, para a transação corrente, os catálogos que o plan revisado marcou como CREATE.

    Se algum já existir neste momento (criado por fora entre plan e apply), o
    plano está velho: PlanStaleError desfaz tudo e pede novo plan. A existência
    é verificada com uma consulta por tipo de catálogo (não uma por item).
    """
    plan, created = ctx.plan, ctx.created
    creates = [item for item in plan.catalog_items if item.action is CatalogAction.CREATE]
    eap_items = sorted(
        (item for item in creates if item.kind == "eap_node"),
        key=lambda item: (_EAP_LEVEL_ORDER.get(str(item.payload.get("level")), 9), item.key),
    )
    discipline_items = [item for item in creates if item.kind == "discipline"]
    work_package_items = [item for item in creates if item.kind == "work_package"]
    project_eap_items = [item for item in creates if item.kind == "project_eap"]

    eap_codes = {str(item.payload["code"]) for item in eap_items} | {
        str(item.payload["parentCode"]) for item in eap_items if item.payload.get("parentCode")
    }
    existing_eap = await _existing_codes(session, EapNode, eap_codes) if eap_codes else {}
    existing_disciplines = (
        await _existing_codes(session, Discipline, {str(item.payload["code"]) for item in discipline_items})
        if discipline_items
        else {}
    )
    existing_work_packages = (
        await _existing_codes(
            session, WorkPackage, {str(item.payload["code"]) for item in work_package_items}
        )
        if work_package_items
        else {}
    )

    for item in eap_items:
        code = str(item.payload["code"])
        if code in existing_eap or code in created.eap:
            raise PlanStaleError(f"EAP {code} passou a existir após o plano. Gere o plano novamente.")
        parent_code = item.payload.get("parentCode")
        parent_id: str | None = None
        if parent_code:
            parent_id = created.eap.get(str(parent_code))
            if parent_id is None:
                existing_parent = existing_eap.get(str(parent_code))
                parent_id = existing_parent[0] if existing_parent and existing_parent[1] else None
            if parent_id is None:
                raise PlanStaleError(f"Processo pai {parent_code} da EAP {code} não existe mais.")
        row = ctx.writes.insert(
            EapNode,
            {
                "code": code,
                "name": str(item.payload["name"]),
                "level": str(item.payload["level"]),
                "parent_id": parent_id,
            },
        )
        created.eap[code] = row["id"]
        _audit_catalog(ctx, entity="EapNode", entity_id=row["id"], item=item, data=dict(item.payload))

    discipline_by_code: dict[str, str] = {}
    for item in discipline_items:
        code = str(item.payload["code"])
        if code in discipline_by_code:
            # Outro valor da origem (alias explícito) aponta para a mesma disciplina.
            created.discipline[item.key] = discipline_by_code[code]
            continue
        if code in existing_disciplines:
            raise PlanStaleError(f"Disciplina {code} passou a existir após o plano. Gere o plano novamente.")
        name = str(item.payload.get("name") or item.key)
        row = ctx.writes.insert(Discipline, {"code": code, "name": name})
        created.discipline[item.key] = row["id"]
        discipline_by_code[code] = row["id"]
        _audit_catalog(
            ctx, entity="Discipline", entity_id=row["id"], item=item, data={"code": code, "name": name}
        )

    created_work_package_codes: set[str] = set()
    for item in work_package_items:
        code = str(item.payload["code"])
        if code in existing_work_packages or code in created_work_package_codes:
            raise PlanStaleError(
                f"Work Package {code} passou a existir após o plano. Gere o plano novamente."
            )
        name = str(item.payload["name"])
        row = ctx.writes.insert(WorkPackage, {"code": code, "name": name})
        created.work_package[item.key] = row["id"]
        created_work_package_codes.add(code)
        _audit_catalog(
            ctx, entity="WorkPackage", entity_id=row["id"], item=item, data={"code": code, "name": name}
        )

    linked: set[str] = set()
    existing_targets = [item.target_id for item in project_eap_items if item.target_id]
    for chunk in _chunks(existing_targets):
        linked.update(
            await session.scalars(
                select(ProjectEap.eap_node_id).where(
                    ProjectEap.project_context_id == plan.project_context_id,
                    ProjectEap.eap_node_id.in_(chunk),
                )
            )
        )
    for item in project_eap_items:
        node_id = item.target_id or created.eap.get(item.key)
        if node_id is None:
            raise RuntimeError(f"ProjectEap sem EAP resolvida para {item.key}")
        if node_id in linked:
            continue  # idempotente: vínculo já existe
        row = ctx.writes.insert(
            ProjectEap, {"project_context_id": plan.project_context_id, "eap_node_id": node_id}
        )
        linked.add(node_id)
        _audit_catalog(
            ctx,
            entity="ProjectEap",
            entity_id=row["id"],
            item=item,
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


# --- estado atual (prefetch do plano, com fallback em lote) ----------------------------


def _usable(instance: Any, model: type[Any]) -> bool:
    """Objeto persistente com todas as colunas carregadas (ler não dispara I/O)."""
    state = sa_inspect(instance)
    if not state.persistent:
        return False
    return not (state.unloaded & {prop.key for prop in sa_inspect(model).column_attrs})


async def _load_by_id(
    session: AsyncSession, model: type[Any], ids: Iterable[str], known: dict[str, Any]
) -> dict[str, Any]:
    """Instâncias por id: primeiro o que o plano já carregou (prefetch/identity map),
    depois uma consulta `IN (...)` por lote só para o que faltar."""
    found: dict[str, Any] = {}
    missing: list[str] = []
    identity_map = session.sync_session.identity_map
    for entity_id in dict.fromkeys(ids):
        instance = known.get(entity_id) or identity_map.get(identity_key(model, entity_id))
        if instance is not None and _usable(instance, model):
            found[entity_id] = instance
        else:
            missing.append(entity_id)
    for chunk in _chunks(missing):
        for instance in await session.scalars(select(model).where(model.id.in_(chunk))):
            found[instance.id] = instance
    return found


async def _load_current_state(session: AsyncSession, ctx: _ApplyContext) -> None:
    plan = ctx.plan
    prefetch = plan.prefetch

    updated_equipments = [item for item in plan.equipments if item.action == "UPDATE"]
    ctx.equipments = await _load_by_id(
        session,
        Equipment,
        (item.target_entity_id for item in updated_equipments if item.target_entity_id),
        dict(prefetch.equipments) if prefetch is not None else {},
    )

    needs_links = [
        item.target_entity_id
        for item in updated_equipments
        if "work_package_ids" in item.payload and item.target_entity_id
    ]
    missing_links: list[str] = []
    for equipment_id in dict.fromkeys(needs_links):
        equipment = ctx.equipments.get(equipment_id)
        if equipment is not None and "work_package_links" not in sa_inspect(equipment).unloaded:
            ctx.work_package_links[equipment_id] = list(equipment.work_package_links)
        else:
            missing_links.append(equipment_id)
            ctx.work_package_links[equipment_id] = []
    for chunk in _chunks(missing_links):
        for link in await session.scalars(
            select(EquipmentWorkPackage).where(EquipmentWorkPackage.equipment_id.in_(chunk))
        ):
            ctx.work_package_links[link.equipment_id].append(link)

    needs_supplier = [
        item.target_entity_id
        for item in updated_equipments
        if item.payload.get("supplier_id") is not None and item.target_entity_id
    ]
    missing_suppliers: list[str] = []
    for equipment_id in dict.fromkeys(needs_supplier):
        # O prefetch consultou fornecedores de todos os equipamentos que carregou.
        if prefetch is not None and equipment_id in prefetch.equipments:
            supplier_id = prefetch.current_supplier.get(equipment_id)
            link_id = prefetch.current_supplier_link.get(equipment_id)
            ctx.active_supplier[equipment_id] = (
                (link_id, supplier_id) if supplier_id is not None and link_id is not None else None
            )
        else:
            missing_suppliers.append(equipment_id)
            ctx.active_supplier[equipment_id] = None
    for chunk in _chunks(missing_suppliers):
        rows = await session.execute(
            select(EquipmentSupplier.equipment_id, EquipmentSupplier.id, EquipmentSupplier.supplier_id).where(
                EquipmentSupplier.equipment_id.in_(chunk), EquipmentSupplier.ended_at.is_(None)
            )
        )
        for equipment_id, link_id, supplier_id in rows:
            if ctx.active_supplier.get(equipment_id) is None:
                ctx.active_supplier[equipment_id] = (link_id, supplier_id)

    for list_name, kind in _SUB_ENTITY_LIST_KINDS.items():
        model = _SUB_ENTITY_MODELS[kind]
        known = (
            {row.id: row for row in prefetch.sub_entities.get(model, {}).values()}
            if prefetch is not None
            else {}
        )
        ctx.sub_entities[model] = await _load_by_id(
            session,
            model,
            (
                item.target_entity_id
                for item in getattr(plan, list_name)
                if item.action == "UPDATE" and item.target_entity_id
            ),
            known,
        )

    ctx.components = await _load_by_id(
        session,
        EquipmentComponent,
        (
            item.target_entity_id
            for item in plan.components
            if item.action == "UPDATE" and item.target_entity_id
        ),
        dict(prefetch.components) if prefetch is not None else {},
    )


# --- fase em memória -------------------------------------------------------------------


def _operational_status_rows(
    ctx: _ApplyContext, *, equipment_id: str, previous_status: str, stage: int, target: str, source_key: str
) -> None:
    """Estado operacional da origem via evento do domínio (nunca coluna isolada)."""
    kind = OPERATIONAL_TRANSITIONS[(previous_status, target)]
    rows = build_operational_status_change_rows(
        equipment_id=equipment_id,
        previous_status=previous_status,
        kind=kind,
        resulting_status=target,
        stage_at_event=stage,
        justification="Importação Monday: estado operacional informado no status da origem.",
        actor_id=ctx.actor.id,
        audit_action=_MIGRATION_ACTION,
        audit_metadata=_plan_metadata(
            ctx.plan, ctx.run_id, source_key, equipment_identity_strategy(source_key)
        ),
    )
    ctx.writes.status_events.append(rows.event_row)
    ctx.writes.audits.append(rows.audit_row)


def _supplier_link_values(
    ctx: _ApplyContext, *, equipment_id: str, supplier_id: str, stage: int
) -> dict[str, Any]:
    return {
        "equipment_id": equipment_id,
        "supplier_id": supplier_id,
        "is_primary": True,
        "start_stage": stage,
        "source": "MONDAY_CONFIRMED",
        "changed_by_user_id": ctx.actor.id,
    }


async def _apply_equipment(ctx: _ApplyContext, item: PlanItem) -> str:
    if item.action == "NOOP":
        assert item.target_entity_id is not None
        return item.target_entity_id

    plan, writes = ctx.plan, ctx.writes
    work_package_ids: list[str] = list(item.payload.get("work_package_ids", []))
    columns = {
        key: value
        for key, value in item.payload.items()
        if key not in {"work_package_ids", "operational_status", "supplier_id", "catalog_refs"}
    }
    operational_target = item.payload.get("operational_status")
    supplier_id = item.payload.get("supplier_id")
    metadata = _plan_metadata(plan, ctx.run_id, item.source_key, equipment_identity_strategy(item.source_key))

    if item.action == "CREATE":
        values: dict[str, Any] = {"project_context_id": plan.project_context_id, **columns}
        if len(work_package_ids) == 1:
            values["work_package_id"] = work_package_ids[0]
        row = _new_row(Equipment, values)
        equipment_id, stage = row["id"], row["current_stage"]
        initial_status = row["operational_status"]
        if operational_target is not None:
            # Estado final já no INSERT; o evento registra a transição a partir do inicial.
            row["operational_status"] = operational_target
        writes.inserts.setdefault(Equipment, []).append(row)
        for work_package_id in work_package_ids:
            writes.insert(
                EquipmentWorkPackage, {"equipment_id": equipment_id, "work_package_id": work_package_id}
            )
        if supplier_id is not None:
            writes.insert(
                EquipmentSupplier,
                _supplier_link_values(ctx, equipment_id=equipment_id, supplier_id=supplier_id, stage=stage),
            )
        writes.mapping(
            project_context_id=plan.project_context_id,
            source_entity_type="equipment",
            external_id=item.source_key,
            identity_strategy=equipment_identity_strategy(item.source_key),
            target_entity_type="Equipment",
            target_entity_id=equipment_id,
        )
        writes.audit(
            user_id=ctx.actor.id,
            entity="Equipment",
            entity_id=equipment_id,
            new_data=_json_safe({**columns, "workPackageIds": work_package_ids, "supplierId": supplier_id}),
            metadata=metadata,
        )
        if operational_target is not None:
            _operational_status_rows(
                ctx,
                equipment_id=equipment_id,
                previous_status=initial_status,
                stage=stage,
                target=operational_target,
                source_key=item.source_key,
            )
        return equipment_id

    assert item.target_entity_id is not None
    existing = ctx.equipments.get(item.target_entity_id)
    assert existing is not None
    previous: dict[str, Any] = {key: getattr(existing, key) for key in columns}
    new_values: dict[str, Any] = dict(columns)
    stage = new_values.get("current_stage", existing.current_stage)
    links_changed = False
    if "work_package_ids" in item.payload:
        existing_links = ctx.work_package_links.get(existing.id, [])
        previous["work_package_ids"] = sorted(link.work_package_id for link in existing_links)
        wanted = set(work_package_ids)
        for link in existing_links:
            if link.work_package_id not in wanted:
                writes.deletes.setdefault(EquipmentWorkPackage, []).append(link.id)
                writes.expunge.append(link)
                links_changed = True
        current_ids = {link.work_package_id for link in existing_links if link.work_package_id in wanted}
        for work_package_id in wanted - current_ids:
            writes.insert(
                EquipmentWorkPackage, {"equipment_id": existing.id, "work_package_id": work_package_id}
            )
            links_changed = True
        new_values["work_package_id"] = work_package_ids[0] if len(work_package_ids) == 1 else None
    if links_changed:
        writes.expire_links.append(existing)
    if supplier_id is not None:
        # A seleção veio explicitamente de `supplierSelections`. A troca
        # preserva a linha anterior e abre um único vínculo ativo.
        current = ctx.active_supplier.get(existing.id)
        previous["supplier_id"] = current[1] if current else None
        if current is not None and current[1] != supplier_id:
            ended = {
                "ended_at": utcnow(),
                "end_stage": stage,
                "is_primary": False,
                "change_reason": "Substituído durante revisão da importação Monday",
                "changed_by_user_id": ctx.actor.id,
            }
            ended["updated_at"] = ended["ended_at"]
            writes.updates.setdefault(EquipmentSupplier, []).append((current[0], ended))
            orm_link = (
                ctx.identity_map.get(identity_key(EquipmentSupplier, current[0]))
                if ctx.identity_map is not None
                else None
            )
            if orm_link is not None:
                writes.synced.append((orm_link, ended))
        if current is None or current[1] != supplier_id:
            writes.insert(
                EquipmentSupplier,
                _supplier_link_values(ctx, equipment_id=existing.id, supplier_id=supplier_id, stage=stage),
            )
    writes.audit(
        user_id=ctx.actor.id,
        entity="Equipment",
        entity_id=existing.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=metadata,
    )
    if operational_target is not None:
        _operational_status_rows(
            ctx,
            equipment_id=existing.id,
            previous_status=existing.operational_status,
            stage=stage,
            target=operational_target,
            source_key=item.source_key,
        )
        new_values["operational_status"] = operational_target
    writes.update(Equipment, existing, _changes(Equipment, existing, new_values))
    return existing.id


async def _apply_sub_entity(
    ctx: _ApplyContext, *, item: PlanItem, model: type[Any], equipment_id: str
) -> None:
    if item.action == "NOOP":
        return
    metadata = _plan_metadata(ctx.plan, ctx.run_id, item.source_key, "equipment-child-v1")
    if item.action == "CREATE":
        row = ctx.writes.insert(model, {"equipment_id": equipment_id, **item.payload})
        ctx.writes.audit(
            user_id=ctx.actor.id,
            entity=model.__name__,
            entity_id=row["id"],
            new_data=_json_safe(item.payload),
            metadata=metadata,
        )
        return
    assert item.target_entity_id is not None
    instance = ctx.sub_entities.get(model, {}).get(item.target_entity_id)
    assert instance is not None
    previous = {key: getattr(instance, key) for key in item.payload}
    ctx.writes.update(model, instance, _changes(model, instance, item.payload))
    ctx.writes.audit(
        user_id=ctx.actor.id,
        entity=model.__name__,
        entity_id=instance.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=metadata,
    )


async def _apply_component(ctx: _ApplyContext, *, item: PlanItem, equipment_id: str) -> str | None:
    """Devolve o id do componente criado/atualizado (None em NOOP)."""
    if item.action == "NOOP":
        return None
    metadata = _plan_metadata(
        ctx.plan, ctx.run_id, item.source_key, component_identity_strategy(item.source_key)
    )
    if item.action == "CREATE":
        row = ctx.writes.insert(EquipmentComponent, {"equipment_id": equipment_id, **item.payload})
        ctx.writes.mapping(
            project_context_id=ctx.plan.project_context_id,
            source_entity_type="component",
            external_id=item.source_key,
            identity_strategy=component_identity_strategy(item.source_key),
            target_entity_type="EquipmentComponent",
            target_entity_id=row["id"],
        )
        ctx.writes.audit(
            user_id=ctx.actor.id,
            entity="EquipmentComponent",
            entity_id=row["id"],
            new_data=_json_safe(item.payload),
            metadata=metadata,
        )
        return cast(str, row["id"])
    assert item.target_entity_id is not None
    existing_component = ctx.components.get(item.target_entity_id)
    assert existing_component is not None
    previous = {key: getattr(existing_component, key) for key in item.payload}
    ctx.writes.update(
        EquipmentComponent, existing_component, _changes(EquipmentComponent, existing_component, item.payload)
    )
    ctx.writes.audit(
        user_id=ctx.actor.id,
        entity="EquipmentComponent",
        entity_id=existing_component.id,
        previous_data=_json_safe(previous),
        new_data=_json_safe(item.payload),
        metadata=metadata,
    )
    return existing_component.id


# --- fase de escrita -------------------------------------------------------------------


def _column_row(model: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    columns = sa_inspect(model).columns
    return {columns[attr].key if attr in columns else attr: value for attr, value in values.items()}


async def _bulk_insert(
    session: AsyncSession, model: type[Any], rows: list[dict[str, Any]], *, preferred: int
) -> int:
    """INSERT multi-VALUES por lote; um statement por conjunto de colunas
    (linhas com colunas diferentes não se misturam no mesmo VALUES)."""
    table = model.__table__
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(tuple(sorted(row)), []).append(row)
    statements = 0
    for keys, group in groups.items():
        size = chunk_size_for(len(keys), preferred=preferred)
        for start in range(0, len(group), size):
            await session.execute(table.insert().values(group[start : start + size]))
            statements += 1
    return statements


async def _bulk_update(
    session: AsyncSession, model: type[Any], entries: list[tuple[str, dict[str, Any]]]
) -> int:
    """UPDATE por id em lote: `UPDATE ... FROM (VALUES ...) RETURNING id`, um statement
    por conjunto de colunas alteradas e por lote de linhas.

    Não usa executemany: o asyncpg não devolve rowcount por parâmetro, e aqui toda
    linha atualizada precisa existir (equivalente ao `StaleDataError` do ORM). Linha
    ausente — ou, no vínculo de fornecedor, já encerrada — significa plano velho."""
    table = model.__table__
    groups: dict[tuple[str, ...], list[tuple[str, dict[str, Any]]]] = {}
    for entity_id, changes in entries:
        row = _column_row(model, changes)
        groups.setdefault(tuple(sorted(row)), []).append((entity_id, row))
    statements = 0
    for key, group in groups.items():
        size = chunk_size_for(len(key) + 1, preferred=_UPDATE_ROWS_PER_STATEMENT)
        for start in range(0, len(group), size):
            chunk = group[start : start + size]
            data = sa_values(
                sa_column("b_id", table.c.id.type),
                *(sa_column(f"b_{name}", table.c[name].type) for name in key),
                name="b",
            ).data([(entity_id, *(row[name] for name in key)) for entity_id, row in chunk])
            stmt = (
                update(table)
                .where(table.c.id == data.c.b_id)
                .values({name: cast_(data.c[f"b_{name}"], table.c[name].type) for name in key})
                .returning(table.c.id)
            )
            if model is EquipmentSupplier:
                # Só encerra vínculo ainda ativo.
                stmt = stmt.where(table.c.ended_at.is_(None))
            updated = (await session.execute(stmt)).scalars().all()
            statements += 1
            if len(updated) != len(chunk):
                raise PlanStaleError(
                    f"{len(chunk) - len(updated)} registro(s) de {table.name} a atualizar não existem "
                    "mais ou mudaram após o plano. Gere o plano novamente."
                )
    return statements


async def _insert_external_mappings(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """`ON CONFLICT DO NOTHING RETURNING`: todo mapping do apply aponta para uma
    entidade nova, então qualquer conflito significa que a identidade passou a
    existir após o plano."""
    if not rows:
        return 0
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        identity = tuple(row[name] for name in _EXTERNAL_MAPPING_CONFLICT)
        if identity in seen:
            raise RuntimeError(
                f"identidade de origem duplicada no plano ({row['source_entity_type']} "
                f"{row['external_id']!r}); o plano não deveria repetir source_key."
            )
        seen.add(identity)
    table = cast(Table, ExternalMapping.__table__)
    size = chunk_size_for(len(rows[0]), preferred=_JSONB_ROWS_PER_STATEMENT)
    statements = 0
    for start in range(0, len(rows), size):
        chunk = rows[start : start + size]
        inserted = (
            await session.execute(
                pg_insert(table)
                .values(chunk)
                .on_conflict_do_nothing(index_elements=_EXTERNAL_MAPPING_CONFLICT)
                .returning(table.c.id)
            )
        ).scalars().all()
        statements += 1
        if len(inserted) != len(chunk):
            raise PlanStaleError(
                f"{len(chunk) - len(inserted)} identidade(s) de origem passaram a ter vínculo "
                "(ExternalMapping) após o plano. Gere o plano novamente."
            )
    return statements


async def _write(session: AsyncSession, writes: _WriteSet) -> int:
    statements = 0
    for model in _WRITE_ORDER:
        table = model.__table__
        ids = writes.deletes.get(model, [])
        for start in range(0, len(ids), _DEFAULT_ROWS_PER_STATEMENT):
            await session.execute(
                delete(table).where(table.c.id.in_(ids[start : start + _DEFAULT_ROWS_PER_STATEMENT]))
            )
            statements += 1
        # UPDATE antes do INSERT: o vínculo de fornecedor anterior é encerrado
        # antes de abrir o novo (índice único de vínculo ativo).
        statements += await _bulk_update(session, model, writes.updates.get(model, []))
        statements += await _bulk_insert(
            session, model, writes.inserts.get(model, []), preferred=_DEFAULT_ROWS_PER_STATEMENT
        )
    statements += await _insert_external_mappings(session, writes.mappings)
    statements += await _bulk_insert(
        session, OperationalStatusEvent, writes.status_events, preferred=_DEFAULT_ROWS_PER_STATEMENT
    )
    # `createdAt` tem precisão de ms e a leitura ordena só por ele: linhas montadas
    # no mesmo instante ganham +1 ms cada, preservando a ordem lógica de geração.
    if writes.audits:
        base = writes.audits[0]["createdAt"]
        for index, audit_row in enumerate(writes.audits):
            audit_row["createdAt"] = base + timedelta(milliseconds=index)
    statements += await bulk_insert_audit(
        session,
        writes.audits,
        chunk_size=chunk_size_for(len(AuditLog.__table__.columns), preferred=_JSONB_ROWS_PER_STATEMENT),
    )
    return statements


def _sync_session_state(session: AsyncSession, writes: _WriteSet) -> None:
    """Objetos já carregados na sessão (prefetch) passam a refletir o que foi
    gravado, sem virar UPDATE de novo no commit (`expire_on_commit=False`)."""
    for instance, values in writes.synced:
        for attr, value in values.items():
            set_committed_value(instance, attr, value)
    for link in writes.expunge:
        if link in session:
            session.expunge(link)
    for equipment in writes.expire_links:
        # Mesmo padrão de `equipments/services.py`: a coleção recarrega na próxima
        # consulta com `selectinload` (ex.: reconciliação logo após o apply).
        session.expire(equipment, ["work_package_links"])


async def _stamp_final_entities(
    session: AsyncSession, *, plan: MigrationPlan, resolutions: dict[str, tuple[str, str]]
) -> None:
    """`resolutions`: source_key -> (final_entity_type, final_entity_id).

    UPDATE por (batch, source_key) via executemany, sem reler os registros
    (o SELECT antigo trazia o raw_payload inteiro de cada linha)."""
    if not resolutions:
        return
    table = cast(Table, MondayImportRecord.__table__)
    stmt = (
        update(table)
        .where(
            table.c.batch_id == any_(bindparam("b_batch_ids", type_=ARRAY(String))),
            table.c.source_key == bindparam("b_source_key"),
        )
        .values(final_entity_type=bindparam("b_type"), final_entity_id=bindparam("b_id"))
    )
    batch_ids_list = list(dict.fromkeys(plan.batch_ids))
    params = [
        {"b_batch_ids": batch_ids_list, "b_source_key": source_key, "b_type": entity_type, "b_id": entity_id}
        for source_key, (entity_type, entity_id) in resolutions.items()
    ]
    for start in range(0, len(params), _UPDATE_ROWS_PER_STATEMENT):
        await session.execute(stmt, params[start : start + _UPDATE_ROWS_PER_STATEMENT])

    batch_ids = set(plan.batch_ids)
    for instance in list(session.sync_session.identity_map.values()):
        if not isinstance(instance, MondayImportRecord):
            continue
        state = sa_inspect(instance)
        if {"batch_id", "source_key"} & state.unloaded or instance.batch_id not in batch_ids:
            continue
        resolution = resolutions.get(instance.source_key)
        if resolution is not None:
            set_committed_value(instance, "final_entity_type", resolution[0])
            set_committed_value(instance, "final_entity_id", resolution[1])


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

    ctx = _ApplyContext(
        plan=plan, run_id=run.id, actor=actor, identity_map=session.sync_session.identity_map
    )
    try:
        async with session.begin_nested():
            run.status = "APPLYING"
            resolutions: dict[str, tuple[str, str]] = {}
            equipment_ids: dict[str, str] = {}

            # Fase 1 — em memória (só leituras em lote do estado atual).
            await _load_current_state(session, ctx)
            created = await _apply_catalogs(session, ctx)

            for planned in plan.equipments:
                item = _materialize(planned, created)
                equipment_id = await _apply_equipment(ctx, item)
                equipment_ids[item.source_key] = equipment_id
                resolutions[item.source_key] = ("Equipment", equipment_id)

            for list_name, kind in _SUB_ENTITY_LIST_KINDS.items():
                model = _SUB_ENTITY_MODELS[kind]
                for item in getattr(plan, list_name):
                    parent_key = item.parent_source_key or item.source_key
                    parent_equipment_id = equipment_ids.get(parent_key)
                    if parent_equipment_id is None:
                        raise RuntimeError(f"equipamento pai não resolvido para {item.source_key}")
                    await _apply_sub_entity(ctx, item=item, model=model, equipment_id=parent_equipment_id)

            for item in plan.components:
                assert item.parent_source_key is not None
                component_parent_id = equipment_ids.get(item.parent_source_key)
                if component_parent_id is None:
                    raise RuntimeError(f"equipamento pai não resolvido para componente {item.source_key}")
                component_id = await _apply_component(ctx, item=item, equipment_id=component_parent_id)
                if item.action != "NOOP":
                    component_id = component_id or item.target_entity_id
                    if not component_id:
                        raise RuntimeError(f"componente sem id resolvido para {item.source_key}")
                    resolutions[item.source_key] = ("EquipmentComponent", component_id)

            # Fase 2 — escrita em lote, uma tabela por vez na ordem das FKs.
            await _write(session, ctx.writes)
            _sync_session_state(session, ctx.writes)

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
        # Descarta valores "fantasmas" que `_sync_session_state` aplicou em objetos
        # da sessão antes do rollback do savepoint.
        session.expire_all()
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
