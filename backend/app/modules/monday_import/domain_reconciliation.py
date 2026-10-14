"""Reconciliação campo a campo: Hub aplicado versus staging Monday mais
recente. Não altera dados; apenas compara e relata.

Diferente de `reconciliation.py` (contagens agregadas origem/destino), este
módulo compara equipamento a equipamento, campo a campo, usando os vínculos
já registrados em `external_mapping`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.equipment import Equipment
from app.models.monday_import import ExternalMapping, MondayImportBatch, MondayImportRecord
from app.models.process import Contract, LegalProcess, PurchaseOrder, PurchaseRequest
from app.modules.monday_import.catalog_evidence import CatalogEvidence
from app.modules.monday_import.catalog_planner import CatalogPlanner
from app.modules.monday_import.mapping_file import ValidatedMapping
from app.modules.monday_import.mappings import SOURCE_SYSTEM
from app.modules.monday_import.plan import _as_date, _group_phase, _merge_group

FieldStatus = Literal["MATCH", "MISMATCH", "NOT_COMPARABLE", "PENDING_MAPPING"]


@dataclass(slots=True, frozen=True)
class FieldComparison:
    field: str
    status: FieldStatus
    hub_value: Any = None
    source_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "status": self.status,
            "hubValue": _safe(self.hub_value),
            "sourceValue": _safe(self.source_value),
        }


@dataclass(slots=True, frozen=True)
class EquipmentReconciliation:
    equipment_id: str
    equipment_name: str
    source_key: str
    fields: list[FieldComparison]

    def to_dict(self) -> dict[str, Any]:
        return {
            "equipmentId": self.equipment_id,
            "equipmentName": self.equipment_name,
            "sourceKey": self.source_key,
            "fields": [item.to_dict() for item in self.fields],
        }


@dataclass(slots=True)
class DomainReconciliationReport:
    equipments: list[EquipmentReconciliation] = field(default_factory=list)
    equipments_compared: int = 0
    components_compared: int = 0

    @property
    def field_totals(self) -> dict[FieldStatus, int]:
        totals: dict[FieldStatus, int] = {
            "MATCH": 0,
            "MISMATCH": 0,
            "NOT_COMPARABLE": 0,
            "PENDING_MAPPING": 0,
        }
        for equipment in self.equipments:
            for item in equipment.fields:
                totals[item.status] += 1
        return totals

    def to_dict(self) -> dict[str, Any]:
        return {
            "equipmentsCompared": self.equipments_compared,
            "componentsCompared": self.components_compared,
            "fieldTotals": self.field_totals,
            "equipments": [item.to_dict() for item in self.equipments],
        }


def _safe(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _compare(
    hub_value: Any, source_value: Any, *, pending: bool = False, max_length: int | None = None
) -> FieldStatus:
    if pending:
        return "PENDING_MAPPING"
    if source_value is None and hub_value is None:
        return "NOT_COMPARABLE"
    if source_value is None:
        return "NOT_COMPARABLE"
    if max_length is not None and isinstance(source_value, str) and len(source_value) > max_length:
        # O plan não grava texto maior que a coluna (FIELD_TOO_LONG): não é divergência.
        return "NOT_COMPARABLE"
    return "MATCH" if hub_value == source_value else "MISMATCH"


def _length(model: type[Any], column: str) -> int | None:
    return getattr(model.__table__.columns[column].type, "length", None)


# Limite de valores por `IN (...)`: o asyncpg aceita até 32767 parâmetros por statement.
_IN_CHUNK = 1000


def _chunks(values: Iterable[str]) -> Iterator[list[str]]:
    ordered = sorted(set(values))
    for start in range(0, len(ordered), _IN_CHUNK):
        yield ordered[start : start + _IN_CHUNK]


def _merge_normalized(records: list[MondayImportRecord]) -> tuple[dict[str, Any] | None, bool]:
    """Mescla todos os batches já staged do contexto para um identificador.
    Devolve `(None, True)` quando há conflito entre batches (não comparável)."""
    if not records:
        return None, False
    merged = _merge_group([(record.batch_id, record) for record in records])
    if merged.conflict_detail is not None:
        return None, True
    return merged.normalized, False


async def _staged_by_source_key(
    session: AsyncSession, *, project_context_id: str, record_kind: str, source_keys: Iterable[str]
) -> dict[str, list[MondayImportRecord]]:
    """Registros staged do contexto (todos os batches) agrupados por `source_key`,
    em poucas consultas `IN (...)` em vez de uma por identificador."""
    grouped: dict[str, list[MondayImportRecord]] = defaultdict(list)
    for chunk in _chunks(source_keys):
        records = (
            await session.scalars(
                select(MondayImportRecord)
                .join(MondayImportBatch, MondayImportBatch.id == MondayImportRecord.batch_id)
                .where(
                    MondayImportBatch.project_context_id == project_context_id,
                    MondayImportRecord.record_kind == record_kind,
                    MondayImportRecord.source_key.in_(chunk),
                )
            )
        ).all()
        for record in records:
            grouped[record.source_key].append(record)
    return grouped


async def _latest_normalized(
    session: AsyncSession, *, project_context_id: str, record_kind: str, source_key: str
) -> tuple[dict[str, Any] | None, bool]:
    """Versão unitária (mantida por compatibilidade) de `_staged_by_source_key`."""
    grouped = await _staged_by_source_key(
        session, project_context_id=project_context_id, record_kind=record_kind, source_keys=[source_key]
    )
    return _merge_normalized(grouped.get(source_key, []))


async def _load_equipments(session: AsyncSession, equipment_ids: Iterable[str]) -> dict[str, Equipment]:
    equipments: dict[str, Equipment] = {}
    for chunk in _chunks(equipment_ids):
        rows = (
            (
                await session.scalars(
                    select(Equipment)
                    .where(Equipment.id.in_(chunk))
                    .options(
                        joinedload(Equipment.discipline),
                        joinedload(Equipment.responsible_user),
                        selectinload(Equipment.work_package_links),
                        joinedload(Equipment.negotiation),
                        joinedload(Equipment.legal_process),
                        selectinload(Equipment.contracts),
                        selectinload(Equipment.purchase_requests),
                        selectinload(Equipment.purchase_orders),
                        selectinload(Equipment.components),
                    )
                )
            )
            .unique()
            .all()
        )
        for equipment in rows:
            equipments[equipment.id] = equipment
    return equipments


async def reconcile_domain(
    session: AsyncSession, *, project_context_id: str, mapping: ValidatedMapping | None = None
) -> DomainReconciliationReport:
    mappings = (
        (
            await session.execute(
                select(ExternalMapping).where(
                    ExternalMapping.project_context_id == project_context_id,
                    ExternalMapping.source_system == SOURCE_SYSTEM,
                    ExternalMapping.source_entity_type == "equipment",
                )
            )
        )
        .scalars()
        .all()
    )

    report = DomainReconciliationReport()
    # Mesma resolução de catálogos do plan. Após o apply, tudo que foi criado é
    # EXISTING; o que segue pendente não é comparável (nunca divergência inventada).
    catalogs = await CatalogPlanner.load(
        session,
        project_context_id=project_context_id,
        mapping=mapping or ValidatedMapping(project_context_id=project_context_id, sha256=""),
        evidence=CatalogEvidence(),
    )
    components_compared = 0

    # Banco remoto (Neon): tudo que o laço compara é carregado em lote (poucas
    # consultas `IN (...)`), e o laço só consulta dicionários. O escopo continua
    # sendo a obra inteira (todos os vínculos de equipamento do contexto).
    equipments = await _load_equipments(session, (item.target_entity_id for item in mappings))
    equipment_staged = await _staged_by_source_key(
        session,
        project_context_id=project_context_id,
        record_kind="equipment",
        source_keys=(item.external_id for item in mappings if item.target_entity_id in equipments),
    )
    component_ids = {component.id for equipment in equipments.values() for component in equipment.components}
    component_mappings_by_target: dict[str, list[ExternalMapping]] = defaultdict(list)
    for chunk in _chunks(component_ids):
        for component_mapping in (
            await session.scalars(
                select(ExternalMapping).where(
                    ExternalMapping.project_context_id == project_context_id,
                    ExternalMapping.source_system == SOURCE_SYSTEM,
                    ExternalMapping.source_entity_type == "component",
                    ExternalMapping.target_entity_id.in_(chunk),
                )
            )
        ).all():
            component_mappings_by_target[component_mapping.target_entity_id].append(component_mapping)
    component_staged = await _staged_by_source_key(
        session,
        project_context_id=project_context_id,
        record_kind="component",
        source_keys=(item.external_id for items in component_mappings_by_target.values() for item in items),
    )

    for equipment_mapping in mappings:
        equipment = equipments.get(equipment_mapping.target_entity_id)
        if equipment is None:
            continue

        normalized, conflict = _merge_normalized(equipment_staged.get(equipment_mapping.external_id, []))
        fields: list[FieldComparison] = []
        if conflict or normalized is None:
            status: FieldStatus = "NOT_COMPARABLE"
            fields.append(FieldComparison("name", status))
            report.equipments.append(
                EquipmentReconciliation(equipment.id, equipment.name, equipment_mapping.external_id, fields)
            )
            report.equipments_compared += 1
            continue

        fields.append(
            FieldComparison(
                "name",
                _compare(equipment.name, normalized.get("name")),
                equipment.name,
                normalized.get("name"),
            )
        )
        source_startup_at = _as_date(normalized.get("startup_at"))
        fields.append(
            FieldComparison(
                "startup_at",
                _compare(equipment.startup_at, source_startup_at),
                equipment.startup_at,
                source_startup_at,
            )
        )
        # "5.Data de Entrega pelo contrato" vive no equipamento desde a migration 0007.
        source_delivery_end = _as_date(normalized.get("contract_delivery_at"))
        fields.append(
            FieldComparison(
                "contractual_delivery_end",
                _compare(equipment.contractual_delivery_end, source_delivery_end),
                equipment.contractual_delivery_end,
                source_delivery_end,
            )
        )

        observed_stage = normalized.get("current_stage")
        phase_stage = normalized.get("group_name") and _group_phase(normalized["group_name"])
        source_stage = observed_stage if observed_stage is not None else phase_stage
        fields.append(
            FieldComparison(
                "current_stage",
                _compare(equipment.current_stage, source_stage),
                equipment.current_stage,
                source_stage,
            )
        )

        source_operational = normalized.get("operational_status") or "ACTIVE"
        if not (equipment.operational_status == "IN_SANITATION" and source_operational == "ACTIVE"):
            fields.append(
                FieldComparison(
                    "operational_status",
                    _compare(equipment.operational_status, source_operational),
                    equipment.operational_status,
                    source_operational,
                )
            )
        # Localização: só a EAP canônica é comparável; sem EAP única na origem, o
        # vínculo fica pendente (nunca é divergência inventada).
        resolved = await catalogs.resolve(session, normalized)
        fields.append(
            FieldComparison(
                "eap",
                _compare(equipment.eap_node_id, resolved.eap_node_id),
                equipment.eap_node_id,
                resolved.eap_node_id if resolved.eap_node_id is not None else normalized.get("area_name"),
            )
        )
        fields.append(
            FieldComparison(
                "discipline",
                _compare(equipment.discipline_id, resolved.discipline_id),
                equipment.discipline_id,
                resolved.discipline_id,
            )
        )
        fields.append(
            FieldComparison(
                "responsible",
                _compare(equipment.responsible_user_id, resolved.responsible_user_id),
                equipment.responsible_user_id,
                resolved.responsible_user_id,
            )
        )
        hub_work_packages = sorted(link.work_package_id for link in equipment.work_package_links)
        source_work_packages = sorted(resolved.work_package_ids)
        if not resolved.has_work_package_source or not resolved.work_packages_complete:
            work_package_status: FieldStatus = "NOT_COMPARABLE"
        else:
            work_package_status = "MATCH" if hub_work_packages == source_work_packages else "MISMATCH"
        fields.append(
            FieldComparison("work_packages", work_package_status, hub_work_packages, source_work_packages)
        )

        hub_equalized = equipment.negotiation.equalized if equipment.negotiation else None
        fields.append(
            FieldComparison(
                "negotiation_equalized",
                _compare(hub_equalized, normalized.get("equalized")),
                hub_equalized,
                normalized.get("equalized"),
            )
        )
        source_negotiated_at = _as_date(normalized.get("negotiated_at"))
        fields.append(
            FieldComparison(
                "negotiation_negotiated_at",
                _compare(
                    equipment.negotiation.negotiated_at if equipment.negotiation else None,
                    source_negotiated_at,
                ),
                equipment.negotiation.negotiated_at if equipment.negotiation else None,
                source_negotiated_at,
            )
        )
        fields.append(
            FieldComparison(
                "legal_ticket_number",
                _compare(
                    equipment.legal_process.ticket_number if equipment.legal_process else None,
                    normalized.get("legal_ticket_number"),
                    max_length=_length(LegalProcess, "ticket_number"),
                ),
                equipment.legal_process.ticket_number if equipment.legal_process else None,
                normalized.get("legal_ticket_number"),
            )
        )
        fields.append(
            FieldComparison(
                "contract_number",
                _compare(
                    (equipment.contracts[0].contract_number if equipment.contracts else None),
                    normalized.get("contract_number"),
                    max_length=_length(Contract, "contract_number"),
                ),
                (equipment.contracts[0].contract_number if equipment.contracts else None),
                normalized.get("contract_number"),
            )
        )
        fields.append(
            FieldComparison(
                "purchase_request_number",
                _compare(
                    (equipment.purchase_requests[0].request_number if equipment.purchase_requests else None),
                    normalized.get("purchase_request_number"),
                    max_length=_length(PurchaseRequest, "request_number"),
                ),
                (equipment.purchase_requests[0].request_number if equipment.purchase_requests else None),
                normalized.get("purchase_request_number"),
            )
        )
        fields.append(FieldComparison("purchase_request_kind", "PENDING_MAPPING"))
        fields.append(
            FieldComparison(
                "purchase_order_number",
                _compare(
                    (equipment.purchase_orders[0].order_number if equipment.purchase_orders else None),
                    normalized.get("purchase_order_number"),
                    max_length=_length(PurchaseOrder, "order_number"),
                ),
                (equipment.purchase_orders[0].order_number if equipment.purchase_orders else None),
                normalized.get("purchase_order_number"),
            )
        )

        component_pairs = [
            (component, component_mapping)
            for component in {item.id: item for item in equipment.components}.values()
            for component_mapping in component_mappings_by_target.get(component.id, [])
        ]
        component_match = 0
        component_mismatch = 0
        component_total = len(component_pairs)
        for component, component_mapping in component_pairs:
            component_normalized, component_conflict = _merge_normalized(
                component_staged.get(component_mapping.external_id, [])
            )
            components_compared += 1
            if component_conflict or component_normalized is None:
                continue
            component_status = _compare(component.lead_time_days, component_normalized.get("lead_time_days"))
            if component_status == "MATCH":
                component_match += 1
            elif component_status == "MISMATCH":
                component_mismatch += 1
        # Divergência só quando algum componente diverge de fato; componente sem valor
        # na origem (não comparável) não é divergência.
        if component_mismatch:
            components_status: FieldStatus = "MISMATCH"
        elif component_match:
            components_status = "MATCH"
        else:
            components_status = "NOT_COMPARABLE"
        fields.append(FieldComparison("components", components_status, component_match, component_total))

        report.equipments.append(
            EquipmentReconciliation(equipment.id, equipment.name, equipment_mapping.external_id, fields)
        )
        report.equipments_compared += 1

    report.components_compared = components_compared
    return report


def render_human(report: DomainReconciliationReport) -> str:
    lines: list[str] = []
    for equipment in report.equipments:
        lines.append(f"Equipment: {equipment.equipment_name}")
        for item in equipment.fields:
            lines.append(f"  {item.field:<26} {item.status}")
        lines.append("")
    totals = report.field_totals
    lines.append(f"Equipamentos comparados: {report.equipments_compared}")
    lines.append(f"Subitens comparados: {report.components_compared}")
    lines.append(f"Campos MATCH: {totals['MATCH']}")
    lines.append(f"Campos MISMATCH: {totals['MISMATCH']}")
    lines.append(f"Campos PENDING_MAPPING: {totals['PENDING_MAPPING']}")
    lines.append(f"Campos NOT_COMPARABLE: {totals['NOT_COMPARABLE']}")
    return "\n".join(lines)
