"""Compara staging + mapping + banco atual e produz um plano determinístico.

`plan` nunca grava no domínio. Ele resolve identidade, mapeia catálogos,
detecta conflitos entre batches sobrepostos e entre Hub/Monday, e serializa
um hash determinístico que o `apply` deve reapresentar sem alteração.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.equipment import Equipment, EquipmentComponent
from app.models.monday_import import ExternalMapping, MondayImportBatch, MondayImportRecord
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.modules.monday_import.mapping_file import ValidatedMapping
from app.modules.monday_import.mappings import SOURCE_SYSTEM
from app.modules.monday_import.normalization import canonical_text

EquipmentIdentityStrategy = "normalized-name-v1"
ComponentIdentityStrategy = "monday-item-id-v1"

PlanAction = Literal["CREATE", "UPDATE", "NOOP", "BLOCKED"]
PlanKind = Literal[
    "equipment",
    "component",
    "negotiation",
    "legal_process",
    "contract",
    "purchase_request",
    "purchase_order",
]

_STAGE_RE = re.compile(r"\bfase\s*([0-8])\b")

_MIGRATION_IMPORT_ACTION = "migration.import"


@dataclass(slots=True, frozen=True)
class PlanIssue:
    code: str
    message: str
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": self.detail}


@dataclass(slots=True, frozen=True)
class PlanItem:
    kind: PlanKind
    source_key: str
    action: PlanAction
    parent_source_key: str | None = None
    target_entity_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    issues: list[PlanIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sourceKey": self.source_key,
            "parentSourceKey": self.parent_source_key,
            "action": self.action,
            "targetEntityId": self.target_entity_id,
            "payload": _json_safe(self.payload),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class PlanCounts:
    create: int = 0
    update: int = 0
    noop: int = 0
    blocked: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"create": self.create, "update": self.update, "noop": self.noop, "blocked": self.blocked}


def _count(items: list[PlanItem]) -> PlanCounts:
    counts = PlanCounts()
    for item in items:
        if item.action == "CREATE":
            counts.create += 1
        elif item.action == "UPDATE":
            counts.update += 1
        elif item.action == "NOOP":
            counts.noop += 1
        else:
            counts.blocked += 1
    return counts


@dataclass(slots=True)
class MigrationPlan:
    project_context_id: str
    batch_ids: list[str]
    mapping_sha256: str
    equipments: list[PlanItem] = field(default_factory=list)
    components: list[PlanItem] = field(default_factory=list)
    negotiations: list[PlanItem] = field(default_factory=list)
    legal_processes: list[PlanItem] = field(default_factory=list)
    contracts: list[PlanItem] = field(default_factory=list)
    purchase_requests: list[PlanItem] = field(default_factory=list)
    purchase_orders: list[PlanItem] = field(default_factory=list)
    warnings: list[PlanIssue] = field(default_factory=list)

    @property
    def all_groups(self) -> dict[str, list[PlanItem]]:
        return {
            "equipments": self.equipments,
            "components": self.components,
            "negotiations": self.negotiations,
            "legalProcesses": self.legal_processes,
            "contracts": self.contracts,
            "purchaseRequests": self.purchase_requests,
            "purchaseOrders": self.purchase_orders,
        }

    @property
    def has_blocked(self) -> bool:
        return any(item.action == "BLOCKED" for items in self.all_groups.values() for item in items)

    @property
    def plan_sha256(self) -> str:
        payload = {
            "projectContextId": self.project_context_id,
            "batchIds": sorted(self.batch_ids),
            "mappingSha256": self.mapping_sha256,
            "groups": {
                name: [
                    {
                        "sourceKey": item.source_key,
                        "action": item.action,
                        "targetEntityId": item.target_entity_id,
                        "payload": _json_safe(item.payload),
                    }
                    for item in sorted(items, key=lambda entry: entry.source_key)
                ]
                for name, items in sorted(self.all_groups.items())
            },
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "projectContextId": self.project_context_id,
            "batchIds": sorted(self.batch_ids),
            "mappingSha256": self.mapping_sha256,
            "planSha256": self.plan_sha256,
            "counts": {name: _count(items).to_dict() for name, items in self.all_groups.items()},
            "groups": {name: [item.to_dict() for item in items] for name, items in self.all_groups.items()},
            "warnings": [issue.to_dict() for issue in self.warnings],
            "blocked": self.has_blocked,
        }


def _as_date(value: Any) -> date | None:
    """`normalized_payload` é JSONB: datas voltam como string ISO, não `date`.
    Reconverte antes de comparar com colunas do domínio ou gravar no Postgres."""
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _as_decimal(value: Any) -> Decimal | None:
    """Mesmo problema de `_as_date`: `capex_estimated` volta como string do
    JSONB. Sem reconverter, a comparação com o `Decimal` já persistido nunca
    bate e o plano nunca chega a NOOP."""
    if value is None or isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _group_phase(group_name: str) -> int | None:
    match = _STAGE_RE.search(canonical_text(group_name))
    return None if match is None else int(match.group(1))


@dataclass(slots=True, frozen=True)
class _MergedRecord:
    source_key: str
    normalized: dict[str, Any]
    record_id: str
    conflict_detail: dict[str, Any] | None = None


def _merge_group(entries: list[tuple[str, MondayImportRecord]]) -> _MergedRecord:
    """Uma identidade pode aparecer em mais de um batch informado. Payloads
    idênticos mesclam sem aviso; payloads diferentes viram IMPORT_CONFLICT —
    nunca escolhemos silenciosamente o mais novo."""
    first_batch_id, first_record = entries[0]
    if len(entries) == 1:
        return _MergedRecord(first_record.source_key, first_record.normalized_payload, first_record.id)

    baseline = entries[0][1].normalized_payload
    differences: dict[str, Any] = {}
    for batch_id, record in entries[1:]:
        for key in set(baseline) | set(record.normalized_payload):
            if baseline.get(key) != record.normalized_payload.get(key):
                differences.setdefault(key, {})[batch_id] = record.normalized_payload.get(key)
                differences[key].setdefault(first_batch_id, baseline.get(key))
    if not differences:
        return _MergedRecord(first_record.source_key, baseline, first_record.id)
    return _MergedRecord(
        first_record.source_key,
        baseline,
        first_record.id,
        conflict_detail={"batches": [batch_id for batch_id, _ in entries], "fields": differences},
    )


async def _existing_mapping(
    session: AsyncSession, *, project_context_id: str, entity_type: str, external_id: str
) -> ExternalMapping | None:
    return await session.scalar(
        select(ExternalMapping).where(
            ExternalMapping.project_context_id == project_context_id,
            ExternalMapping.source_system == SOURCE_SYSTEM,
            ExternalMapping.source_entity_type == entity_type,
            ExternalMapping.external_id == external_id,
        )
    )


async def _human_touched_after_migration(session: AsyncSession, *, entity: str, entity_id: str) -> bool:
    """Existe alteração registrada por algo além do próprio importador?"""
    row = await session.scalar(
        select(AuditLog.id)
        .where(
            AuditLog.entity == entity,
            AuditLog.entityId == entity_id,
            AuditLog.action != _MIGRATION_IMPORT_ACTION,
        )
        .limit(1)
    )
    return row is not None


def _diff(existing: Any, incoming: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for field_name, value in incoming.items():
        if getattr(existing, field_name) != value:
            changed[field_name] = value
    return changed


async def _plan_sub_entity(
    session: AsyncSession,
    *,
    kind: PlanKind,
    model: type[Any],
    entity_label: str,
    equipment_source_key: str,
    equipment_blocked: bool,
    equipment_target_id: str | None,
    payload: dict[str, Any],
) -> PlanItem | None:
    """Cria o item de plano de um processo 1:1. Sem nenhum campo de origem e
    sem registro existente, o item é omitido (nada a fazer)."""
    payload = {key: value for key, value in payload.items() if value is not None}
    if equipment_blocked:
        return PlanItem(
            kind=kind,
            source_key=equipment_source_key,
            action="BLOCKED",
            parent_source_key=equipment_source_key,
            issues=[PlanIssue("parent_blocked", f"{entity_label}: equipamento pai está bloqueado")],
        )
    existing = (
        await session.scalar(select(model).where(model.equipment_id == equipment_target_id))
        if equipment_target_id
        else None
    )
    if not payload:
        if existing is None:
            return None
        return PlanItem(
            kind=kind,
            source_key=equipment_source_key,
            action="NOOP",
            parent_source_key=equipment_source_key,
            target_entity_id=existing.id,
        )
    if existing is None:
        return PlanItem(
            kind=kind,
            source_key=equipment_source_key,
            action="CREATE",
            parent_source_key=equipment_source_key,
            payload=payload,
        )
    changed = _diff(existing, payload)
    if not changed:
        return PlanItem(
            kind=kind,
            source_key=equipment_source_key,
            action="NOOP",
            parent_source_key=equipment_source_key,
            target_entity_id=existing.id,
        )
    if await _human_touched_after_migration(session, entity=model.__name__, entity_id=existing.id):
        return PlanItem(
            kind=kind,
            source_key=equipment_source_key,
            action="BLOCKED",
            parent_source_key=equipment_source_key,
            target_entity_id=existing.id,
            payload=changed,
            issues=[
                PlanIssue(
                    "hub_monday_conflict",
                    f"{entity_label}: dado no Hub diverge do Monday e já foi alterado fora da migração",
                    detail={"changedFields": _json_safe(changed)},
                )
            ],
        )
    return PlanItem(
        kind=kind,
        source_key=equipment_source_key,
        action="UPDATE",
        parent_source_key=equipment_source_key,
        target_entity_id=existing.id,
        payload=changed,
    )


async def build_plan(
    session: AsyncSession,
    *,
    project_context_id: str,
    batch_ids: list[str],
    mapping: ValidatedMapping,
) -> MigrationPlan:
    if not batch_ids:
        raise ValueError("informe ao menos um batch")

    batches = (
        (await session.execute(select(MondayImportBatch).where(MondayImportBatch.id.in_(batch_ids))))
        .scalars()
        .all()
    )
    found_ids = {batch.id for batch in batches}
    missing = set(batch_ids) - found_ids
    if missing:
        raise ValueError(f"batch(es) não encontrado(s): {sorted(missing)}")
    wrong_context = [batch.id for batch in batches if batch.project_context_id != project_context_id]
    if wrong_context:
        raise ValueError(f"batch(es) de outro contexto: {sorted(wrong_context)}")

    records = (
        (
            await session.execute(
                select(MondayImportRecord).where(MondayImportRecord.batch_id.in_(batch_ids))
            )
        )
        .scalars()
        .all()
    )
    records_by_id = {record.id: record for record in records}

    equipment_groups: dict[str, list[tuple[str, MondayImportRecord]]] = {}
    component_groups: dict[tuple[str, str], list[tuple[str, MondayImportRecord]]] = {}
    for record in records:
        if record.record_kind == "equipment":
            equipment_groups.setdefault(record.source_key, []).append((record.batch_id, record))
        else:
            parent = records_by_id.get(record.parent_record_id or "")
            parent_key = parent.source_key if parent is not None else "orphan"
            component_groups.setdefault((parent_key, record.source_key), []).append(
                (record.batch_id, record)
            )

    plan = MigrationPlan(
        project_context_id=project_context_id, batch_ids=list(batch_ids), mapping_sha256=mapping.sha256
    )

    equipment_target_ids: dict[str, str | None] = {}
    equipment_blocked: dict[str, bool] = {}

    for source_key, entries in sorted(equipment_groups.items()):
        merged = _merge_group(entries)
        if merged.conflict_detail is not None:
            plan.equipments.append(
                PlanItem(
                    kind="equipment",
                    source_key=source_key,
                    action="BLOCKED",
                    issues=[
                        PlanIssue(
                            "IMPORT_CONFLICT",
                            "Identidade repetida em batches com payload diferente",
                            detail=merged.conflict_detail,
                        )
                    ],
                )
            )
            equipment_blocked[source_key] = True
            equipment_target_ids[source_key] = None
            continue

        normalized = merged.normalized
        issues: list[PlanIssue] = []

        if normalized.get("suppliers_raw"):
            plan.warnings.append(
                PlanIssue(
                    "SUPPLIER_MIGRATION_PENDING",
                    f"Fornecedores de '{normalized.get('name')}' não são migrados por esta versão",
                    detail={"equipmentSourceKey": source_key},
                )
            )

        area_id = mapping.resolve_area(normalized.get("area_name"))
        if normalized.get("area_name") and area_id is None:
            issues.append(
                PlanIssue("unmapped_area", f"Área sem mapeamento: {normalized['area_name']}")
            )
        discipline_id = mapping.resolve_discipline(normalized.get("discipline_name"))
        if normalized.get("discipline_name") and discipline_id is None:
            issues.append(
                PlanIssue(
                    "unmapped_discipline",
                    f"Disciplina sem mapeamento: {normalized['discipline_name']}",
                )
            )
        responsible_id = mapping.resolve_responsible(normalized.get("responsible_name"))
        if normalized.get("responsible_name") and responsible_id is None:
            issues.append(
                PlanIssue(
                    "unmapped_responsible",
                    f"Responsável sem mapeamento: {normalized['responsible_name']}",
                )
            )
        work_package_codes = normalized.get("work_package_codes") or []
        work_package_ids: list[str] = []
        for code in work_package_codes:
            resolved = mapping.resolve_work_package(code)
            if resolved is None:
                issues.append(PlanIssue("unmapped_work_package", f"Work Package sem mapeamento: {code}"))
            else:
                work_package_ids.append(resolved)

        observed_stage = normalized.get("current_stage")
        phase_stage = _group_phase(entries[0][1].group_name)
        if observed_stage is not None and phase_stage is not None and observed_stage != phase_stage:
            issues.append(
                PlanIssue(
                    "STAGE_CONFLICT",
                    f"A.Status ({observed_stage}) diverge da fase do grupo ({phase_stage})",
                    detail={"aStatus": observed_stage, "groupPhase": phase_stage},
                )
            )
        current_stage = observed_stage if observed_stage is not None else phase_stage
        if current_stage is None:
            issues.append(PlanIssue("missing_current_stage", "Nenhuma etapa identificada na origem"))

        existing_mapping = await _existing_mapping(
            session, project_context_id=project_context_id, entity_type="equipment", external_id=source_key
        )
        target_id = existing_mapping.target_entity_id if existing_mapping else None
        if existing_mapping is None:
            colliding = await session.scalar(
                select(Equipment.id).where(
                    Equipment.project_context_id == project_context_id,
                    Equipment.name == normalized.get("name"),
                )
            )
            if colliding is not None:
                issues.append(
                    PlanIssue(
                        "PARENT_IDENTITY_CONFLICT",
                        "Já existe um equipamento com este nome no contexto, sem vínculo de origem "
                        "registrado. Resolva manualmente antes de aplicar.",
                        detail={"existingEquipmentId": colliding},
                    )
                )

        blocking_codes = {
            "IMPORT_CONFLICT",
            "STAGE_CONFLICT",
            "missing_current_stage",
            "unmapped_area",
            "unmapped_discipline",
            "unmapped_responsible",
            "unmapped_work_package",
            "PARENT_IDENTITY_CONFLICT",
        }
        is_blocked = any(issue.code in blocking_codes for issue in issues)
        equipment_blocked[source_key] = is_blocked
        equipment_target_ids[source_key] = target_id

        if is_blocked:
            plan.equipments.append(
                PlanItem(kind="equipment", source_key=source_key, action="BLOCKED", issues=issues)
            )
            continue

        payload: dict[str, Any] = {
            "name": normalized.get("name"),
            "origin": normalized.get("origin"),
            "startup_at": _as_date(normalized.get("startup_at")),
            "area_id": area_id,
            "discipline_id": discipline_id,
            "responsible_user_id": responsible_id,
            "criticality": normalized.get("criticality_observed"),
            "capex_estimated": _as_decimal(normalized.get("capex_estimated")),
            "current_stage": current_stage,
        }
        payload = {key: value for key, value in payload.items() if value is not None}
        payload["work_package_ids"] = sorted(work_package_ids)

        if target_id is None:
            plan.equipments.append(
                PlanItem(
                    kind="equipment",
                    source_key=source_key,
                    action="CREATE",
                    payload=payload,
                    issues=issues,
                )
            )
            continue

        # `session.get` faz atalho pelo identity map quando o equipamento já foi
        # carregado em outro ponto da mesma sessão, ignorando `options` — por
        # isso o eager load do N:N precisa de um `select` explícito aqui.
        existing = await session.scalar(
            select(Equipment)
            .where(Equipment.id == target_id)
            .options(selectinload(Equipment.work_package_links))
        )
        if existing is None:  # pragma: no cover - mapping órfão, anomalia de dados
            issues.append(
                PlanIssue("dangling_mapping", "external_mapping aponta para equipamento inexistente")
            )
            plan.equipments.append(
                PlanItem(kind="equipment", source_key=source_key, action="BLOCKED", issues=issues)
            )
            equipment_blocked[source_key] = True
            continue

        compare_payload = dict(payload)
        existing_work_packages = sorted(link.work_package_id for link in existing.work_package_links)
        wp_changed = compare_payload.pop("work_package_ids") != existing_work_packages
        changed = _diff(existing, compare_payload)
        if wp_changed:
            changed["work_package_ids"] = payload["work_package_ids"]
        if not changed:
            plan.equipments.append(
                PlanItem(
                    kind="equipment",
                    source_key=source_key,
                    action="NOOP",
                    target_entity_id=target_id,
                    issues=issues,
                )
            )
            continue
        if await _human_touched_after_migration(session, entity="Equipment", entity_id=target_id):
            issues.append(
                PlanIssue(
                    "hub_monday_conflict",
                    "Equipamento diverge do Monday e já foi alterado fora da migração",
                    detail={"changedFields": _json_safe(changed)},
                )
            )
            plan.equipments.append(
                PlanItem(
                    kind="equipment",
                    source_key=source_key,
                    action="BLOCKED",
                    target_entity_id=target_id,
                    payload=changed,
                    issues=issues,
                )
            )
            equipment_blocked[source_key] = True
            continue
        plan.equipments.append(
            PlanItem(
                kind="equipment",
                source_key=source_key,
                action="UPDATE",
                target_entity_id=target_id,
                payload=changed,
                issues=issues,
            )
        )

        negotiation_item = await _plan_sub_entity(
            session,
            kind="negotiation",
            model=Negotiation,
            entity_label="Negociação",
            equipment_source_key=source_key,
            equipment_blocked=False,
            equipment_target_id=target_id,
            payload={
                "equalized": normalized.get("equalized"),
                "negotiated_at": _as_date(normalized.get("negotiated_at")),
            },
        )
        if negotiation_item:
            plan.negotiations.append(negotiation_item)

        legal_item = await _plan_sub_entity(
            session,
            kind="legal_process",
            model=LegalProcess,
            entity_label="Jurídico",
            equipment_source_key=source_key,
            equipment_blocked=False,
            equipment_target_id=target_id,
            payload={
                "opened_at": _as_date(normalized.get("legal_opened_at")),
                "ticket_number": normalized.get("legal_ticket_number"),
                "draft_prepared": normalized.get("draft_prepared"),
                "draft_approved": normalized.get("draft_approved"),
            },
        )
        if legal_item:
            plan.legal_processes.append(legal_item)

        contract_item = await _plan_sub_entity(
            session,
            kind="contract",
            model=Contract,
            entity_label="Contrato",
            equipment_source_key=source_key,
            equipment_blocked=False,
            equipment_target_id=target_id,
            payload={
                "contract_number": normalized.get("contract_number"),
                "executed_at": _as_date(normalized.get("contract_executed_at")),
                "delivery_at": _as_date(normalized.get("contract_delivery_at")),
            },
        )
        if contract_item:
            plan.contracts.append(contract_item)

        request_number = normalized.get("purchase_request_number")
        request_at = _as_date(normalized.get("purchase_request_at"))
        if request_number or request_at:
            plan.warnings.append(
                PlanIssue(
                    "PURCHASE_REQUEST_KIND_UNRESOLVED",
                    f"SC/OCI de '{normalized.get('name')}' sem tipo identificável na origem",
                    detail={"equipmentSourceKey": source_key},
                )
            )
        request_item = await _plan_sub_entity(
            session,
            kind="purchase_request",
            model=PurchaseRequest,
            entity_label="SC/OCI",
            equipment_source_key=source_key,
            equipment_blocked=False,
            equipment_target_id=target_id,
            payload={"request_number": request_number, "requested_at": request_at},
        )
        if request_item:
            plan.purchase_requests.append(request_item)

        order_item = await _plan_sub_entity(
            session,
            kind="purchase_order",
            model=PurchaseOrder,
            entity_label="Ordem de compra",
            equipment_source_key=source_key,
            equipment_blocked=False,
            equipment_target_id=target_id,
            payload={
                "order_number": normalized.get("purchase_order_number"),
                "ordered_at": _as_date(normalized.get("purchase_order_at")),
            },
        )
        if order_item:
            plan.purchase_orders.append(order_item)

    # Reprocessa os itens CREATE/UPDATE dos sub-processos para equipamentos
    # recém-criados (ainda sem target_id no momento do loop acima).
    for equipment_item in plan.equipments:
        if equipment_item.action != "CREATE":
            continue
        source_key = equipment_item.source_key
        entries = equipment_groups[source_key]
        normalized = _merge_group(entries).normalized
        entries_by_kind: list[tuple[PlanKind, type[Any], str, dict[str, Any]]] = [
            (
                "negotiation",
                Negotiation,
                "Negociação",
                {
                    "equalized": normalized.get("equalized"),
                    "negotiated_at": _as_date(normalized.get("negotiated_at")),
                },
            ),
            (
                "legal_process",
                LegalProcess,
                "Jurídico",
                {
                    "opened_at": _as_date(normalized.get("legal_opened_at")),
                    "ticket_number": normalized.get("legal_ticket_number"),
                    "draft_prepared": normalized.get("draft_prepared"),
                    "draft_approved": normalized.get("draft_approved"),
                },
            ),
            (
                "contract",
                Contract,
                "Contrato",
                {
                    "contract_number": normalized.get("contract_number"),
                    "executed_at": _as_date(normalized.get("contract_executed_at")),
                    "delivery_at": _as_date(normalized.get("contract_delivery_at")),
                },
            ),
            (
                "purchase_request",
                PurchaseRequest,
                "SC/OCI",
                {
                    "request_number": normalized.get("purchase_request_number"),
                    "requested_at": _as_date(normalized.get("purchase_request_at")),
                },
            ),
            (
                "purchase_order",
                PurchaseOrder,
                "Ordem de compra",
                {
                    "order_number": normalized.get("purchase_order_number"),
                    "ordered_at": _as_date(normalized.get("purchase_order_at")),
                },
            ),
        ]
        for kind, _model, _label, payload in entries_by_kind:
            payload = {key: value for key, value in payload.items() if value is not None}
            if not payload:
                continue
            item = PlanItem(
                kind=kind,
                source_key=source_key,
                action="CREATE",
                parent_source_key=source_key,
                payload=payload,
            )
            target_list = {
                "negotiation": plan.negotiations,
                "legal_process": plan.legal_processes,
                "contract": plan.contracts,
                "purchase_request": plan.purchase_requests,
                "purchase_order": plan.purchase_orders,
            }[kind]
            target_list.append(item)
            if kind == "purchase_request" and (payload.get("request_number") or payload.get("requested_at")):
                plan.warnings.append(
                    PlanIssue(
                        "PURCHASE_REQUEST_KIND_UNRESOLVED",
                        f"SC/OCI de '{normalized.get('name')}' sem tipo identificável na origem",
                        detail={"equipmentSourceKey": source_key},
                    )
                )

    for (equipment_key, component_key), entries in sorted(component_groups.items()):
        merged = _merge_group(entries)
        parent_blocked = equipment_blocked.get(equipment_key, True)
        if merged.conflict_detail is not None:
            plan.components.append(
                PlanItem(
                    kind="component",
                    source_key=component_key,
                    parent_source_key=equipment_key,
                    action="BLOCKED",
                    issues=[
                        PlanIssue(
                            "IMPORT_CONFLICT",
                            "Identidade de componente repetida em batches com payload diferente",
                            detail=merged.conflict_detail,
                        )
                    ],
                )
            )
            continue
        if parent_blocked:
            plan.components.append(
                PlanItem(
                    kind="component",
                    source_key=component_key,
                    parent_source_key=equipment_key,
                    action="BLOCKED",
                    issues=[PlanIssue("parent_blocked", "Equipamento pai está bloqueado")],
                )
            )
            continue
        if component_key.startswith("missing-external-id:"):
            plan.components.append(
                PlanItem(
                    kind="component",
                    source_key=component_key,
                    parent_source_key=equipment_key,
                    action="BLOCKED",
                    issues=[
                        PlanIssue(
                            "missing_component_identity",
                            "Subitem sem ID do elemento não pode ser aplicado de forma idempotente",
                        )
                    ],
                )
            )
            continue

        normalized = merged.normalized
        if normalized.get("files_raw"):
            plan.warnings.append(
                PlanIssue(
                    "ATTACHMENT_MIGRATION_PENDING",
                    f"Anexos do subitem '{normalized.get('name')}' não são migrados por esta versão",
                    detail={"componentSourceKey": component_key},
                )
            )
        payload = {
            "name": normalized.get("name"),
            "tag": normalized.get("tag"),
            "startup_at": _as_date(normalized.get("startup_at")),
            "sector": normalized.get("sector"),
            "lead_time_days": normalized.get("lead_time_days"),
            "pre_start_days": normalized.get("pre_start_days"),
            "contract_delivery_at": _as_date(normalized.get("contract_delivery_at")),
            "freight_days": normalized.get("freight_days"),
        }
        payload = {key: value for key, value in payload.items() if value is not None}

        existing_mapping = await _existing_mapping(
            session, project_context_id=project_context_id, entity_type="component", external_id=component_key
        )
        if existing_mapping is None:
            action: PlanAction = "CREATE"
            target_component_id: str | None = None
            changed = payload
            item_issues: list[PlanIssue] = []
        else:
            target_component_id = existing_mapping.target_entity_id
            existing_component = await session.get(EquipmentComponent, target_component_id)
            if existing_component is None:  # pragma: no cover - mapping órfão
                action, changed, item_issues = "BLOCKED", {}, [
                    PlanIssue("dangling_mapping", "external_mapping aponta para componente inexistente")
                ]
            else:
                changed = _diff(existing_component, payload)
                if not changed:
                    action, item_issues = "NOOP", []
                elif await _human_touched_after_migration(
                    session, entity="EquipmentComponent", entity_id=existing_component.id
                ):
                    action = "BLOCKED"
                    item_issues = [
                        PlanIssue(
                            "hub_monday_conflict",
                            "Componente diverge do Monday e já foi alterado fora da migração",
                            detail={"changedFields": _json_safe(changed)},
                        )
                    ]
                else:
                    action = "UPDATE"
                    item_issues = []

        plan.components.append(
            PlanItem(
                kind="component",
                source_key=component_key,
                parent_source_key=equipment_key,
                action=action,
                target_entity_id=target_component_id,
                payload=changed if action in ("CREATE", "UPDATE") else {},
                issues=item_issues,
            )
        )

    return plan
