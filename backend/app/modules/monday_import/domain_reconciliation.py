"""Reconciliação campo a campo: Hub aplicado versus staging Monday mais
recente. Não altera dados; apenas compara e relata.

Diferente de `reconciliation.py` (contagens agregadas origem/destino), este
módulo compara equipamento a equipamento, campo a campo, usando os vínculos
já registrados em `external_mapping`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.equipment import Equipment
from app.models.monday_import import ExternalMapping, MondayImportBatch, MondayImportRecord
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


def _compare(hub_value: Any, source_value: Any, *, pending: bool = False) -> FieldStatus:
    if pending:
        return "PENDING_MAPPING"
    if source_value is None and hub_value is None:
        return "NOT_COMPARABLE"
    if source_value is None:
        return "NOT_COMPARABLE"
    return "MATCH" if hub_value == source_value else "MISMATCH"


async def _latest_normalized(
    session: AsyncSession, *, project_context_id: str, record_kind: str, source_key: str
) -> tuple[dict[str, Any] | None, bool]:
    """Mescla todos os batches já staged do contexto para este identificador.
    Devolve `(None, True)` quando há conflito entre batches (não comparável)."""
    records = (
        (
            await session.execute(
                select(MondayImportRecord)
                .join(MondayImportBatch, MondayImportBatch.id == MondayImportRecord.batch_id)
                .where(
                    MondayImportBatch.project_context_id == project_context_id,
                    MondayImportRecord.record_kind == record_kind,
                    MondayImportRecord.source_key == source_key,
                )
            )
        )
        .scalars()
        .all()
    )
    if not records:
        return None, False
    entries = [(record.batch_id, record) for record in records]
    merged = _merge_group(entries)
    if merged.conflict_detail is not None:
        return None, True
    return merged.normalized, False


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
    components_compared = 0

    for equipment_mapping in mappings:
        equipment = await session.scalar(
            select(Equipment)
            .where(Equipment.id == equipment_mapping.target_entity_id)
            .options(
                joinedload(Equipment.area),
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
        if equipment is None:
            continue

        normalized, conflict = await _latest_normalized(
            session,
            project_context_id=project_context_id,
            record_kind="equipment",
            source_key=equipment_mapping.external_id,
        )
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

        if mapping is not None:
            resolved_area = mapping.resolve_area(normalized.get("area_name"))
            fields.append(
                FieldComparison(
                    "area", _compare(equipment.area_id, resolved_area), equipment.area_id, resolved_area
                )
            )
            resolved_discipline = mapping.resolve_discipline(normalized.get("discipline_name"))
            fields.append(
                FieldComparison(
                    "discipline",
                    _compare(equipment.discipline_id, resolved_discipline),
                    equipment.discipline_id,
                    resolved_discipline,
                )
            )
            resolved_responsible = mapping.resolve_responsible(normalized.get("responsible_name"))
            fields.append(
                FieldComparison(
                    "responsible",
                    _compare(equipment.responsible_user_id, resolved_responsible),
                    equipment.responsible_user_id,
                    resolved_responsible,
                )
            )
            source_codes = normalized.get("work_package_codes") or []
            resolved_work_packages = sorted(
                filter(None, (mapping.resolve_work_package(code) for code in source_codes))
            )
            hub_work_packages = sorted(link.work_package_id for link in equipment.work_package_links)
            fields.append(
                FieldComparison(
                    "work_packages",
                    "MATCH" if hub_work_packages == resolved_work_packages else "MISMATCH",
                    hub_work_packages,
                    resolved_work_packages,
                )
            )
        else:
            for field_name in ("area", "discipline", "responsible", "work_packages"):
                fields.append(FieldComparison(field_name, "PENDING_MAPPING"))

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
                ),
                (equipment.purchase_orders[0].order_number if equipment.purchase_orders else None),
                normalized.get("purchase_order_number"),
            )
        )

        component_mappings = (
            (
                await session.execute(
                    select(ExternalMapping).where(
                        ExternalMapping.project_context_id == project_context_id,
                        ExternalMapping.source_system == SOURCE_SYSTEM,
                        ExternalMapping.source_entity_type == "component",
                        ExternalMapping.target_entity_id.in_([item.id for item in equipment.components]),
                    )
                )
            )
            .scalars()
            .all()
        )
        component_match = 0
        component_total = len(component_mappings)
        for component_mapping in component_mappings:
            component = next(
                (item for item in equipment.components if item.id == component_mapping.target_entity_id), None
            )
            if component is None:
                continue
            component_normalized, component_conflict = await _latest_normalized(
                session,
                project_context_id=project_context_id,
                record_kind="component",
                source_key=component_mapping.external_id,
            )
            components_compared += 1
            if component_conflict or component_normalized is None:
                continue
            component_status = _compare(component.lead_time_days, component_normalized.get("lead_time_days"))
            if component_status == "MATCH":
                component_match += 1
        fields.append(
            FieldComparison(
                "components",
                "MATCH" if component_total and component_match == component_total else (
                    "NOT_COMPARABLE" if component_total == 0 else "MISMATCH"
                ),
                component_match,
                component_total,
            )
        )

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
