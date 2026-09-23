"""Filas operacionais por área.

Cada fila é um recorte explícito do mesmo workflow 0–8 — não há filtro oculto
nem regra herdada de board. O critério de cada área está em `QUEUE_STAGES` e
documentado em `docs/etapa-03-dashboard-navegacao-filas.md`.

A pendência exibida em cada linha vem da mesma fonte usada pelo endpoint de
transições, para que fila e detalhe nunca divirjam.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.auth import CurrentUser
from app.core.scope import allowed_unit_ids, assert_unit_allowed, restrict_to_units
from app.models.equipment import STAGES, Equipment, EquipmentComponent, EquipmentWorkPackage, ProjectContext
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)
from app.models.supplier import EquipmentSupplier
from app.models.workflow_extras import RequirementWaiver
from app.modules.equipments.schemas import NamedRefOut, PaginationOut, UserRefOut
from app.modules.queues.schemas import (
    EngineeringQueueOut,
    EngineeringRowOut,
    LegalQueueOut,
    LegalRowOut,
    PendingRequirementOut,
    ProcurementQueueOut,
    ProcurementRowOut,
    SupplierRefOut,
)
from app.modules.suppliers.service import primary_suppliers
from app.modules.workflow.stages import FINAL_STAGE, ProcessState, groups_for

# Recorte de etapas por área. Cada intervalo é inclusivo.
QUEUE_STAGES: dict[str, tuple[int, int]] = {
    "engineering": (0, 2),
    "legal": (3, 5),
    "procurement": (6, 7),
}

ProcessModel = TypeVar(
    "ProcessModel", Negotiation, LegalProcess, Contract, PurchaseRequest, PurchaseOrder
)


@dataclass(frozen=True, slots=True)
class QueueFilters:
    unit_id: str | None = None
    equipment_id: str | None = None
    stage: int | None = None
    search: str | None = None
    responsible_user_id: str | None = None
    # Só exposto como query param em GET /queues/engineering — disciplina é
    # um requisito específico da fila de Engenharia (GAP-011), não das
    # demais. `_filtered` aplica sempre que vier preenchido, mas Jurídico e
    # Suprimentos nunca preenchem este campo (ver router.py).
    discipline_id: str | None = None
    page: int = 1
    page_size: int = 25


def _filtered(
    stmt: Select[Any],
    filters: QueueFilters,
    stage_range: tuple[int, int],
    allowed_units: set[str] | None,
) -> Select[Any]:
    stmt = stmt.join(Equipment.project_context)
    stmt = restrict_to_units(stmt, allowed_units)
    if filters.responsible_user_id:
        stmt = stmt.where(Equipment.responsible_user_id == filters.responsible_user_id)
    if filters.discipline_id:
        stmt = stmt.where(Equipment.discipline_id == filters.discipline_id)
    if filters.unit_id:
        stmt = stmt.where(ProjectContext.unit_id == filters.unit_id)
    if filters.equipment_id:
        stmt = stmt.where(Equipment.id == filters.equipment_id)
    if filters.stage is not None:
        stmt = stmt.where(Equipment.current_stage == filters.stage)
    else:
        low, high = stage_range
        stmt = stmt.where(Equipment.current_stage.between(low, high))
    if filters.search and filters.search.strip():
        stmt = stmt.where(Equipment.name.ilike(f"%{filters.search.strip()}%"))
    return stmt


async def _load_page(
    session: AsyncSession, queue: str, filters: QueueFilters, actor: CurrentUser
) -> tuple[list[Equipment], PaginationOut]:
    page = max(1, filters.page)
    page_size = min(100, max(1, filters.page_size))
    stage_range = QUEUE_STAGES[queue]
    if filters.unit_id:
        await assert_unit_allowed(session, actor, filters.unit_id)
    allowed_units = await allowed_unit_ids(session, actor)
    total = (
        await session.execute(
            _filtered(
                select(func.count()).select_from(Equipment), filters, stage_range, allowed_units
            )
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                _filtered(select(Equipment), filters, stage_range, allowed_units)
                .options(
                    joinedload(Equipment.project_context).joinedload(ProjectContext.unit),
                    joinedload(Equipment.area),
                    joinedload(Equipment.discipline),
                    selectinload(Equipment.work_package_links).joinedload(
                        EquipmentWorkPackage.work_package
                    ),
                    joinedload(Equipment.responsible_user),
                )
                .order_by(Equipment.current_stage.asc(), Equipment.name.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    pagination = PaginationOut(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
    return list(rows), pagination


async def _bulk(
    session: AsyncSession, model: type[ProcessModel], equipment_ids: list[str]
) -> dict[str, ProcessModel]:
    """Carrega um processo para toda a página de uma vez, evitando N+1."""
    if not equipment_ids:
        return {}
    rows = (
        (await session.execute(select(model).where(model.equipment_id.in_(equipment_ids))))
        .scalars()
        .all()
    )
    return {row.equipment_id: row for row in rows}


async def _bulk_many(
    session: AsyncSession, model: type[ProcessModel], equipment_ids: list[str]
) -> dict[str, list[ProcessModel]]:
    """Como `_bulk`, mas para os processos 1:N (Etapa 7A)."""
    if not equipment_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(model)
                .where(model.equipment_id.in_(equipment_ids))
                .order_by(model.equipment_id, model.created_at)
            )
        )
        .scalars()
        .all()
    )
    result: dict[str, list[ProcessModel]] = {equipment_id: [] for equipment_id in equipment_ids}
    for row in rows:
        result[row.equipment_id].append(row)
    return result


async def _process_states(
    session: AsyncSession,
    equipment_ids: list[str],
    equipments: dict[str, Equipment] | None = None,
) -> dict[str, ProcessState]:
    negotiations = await _bulk(session, Negotiation, equipment_ids)
    legals = await _bulk(session, LegalProcess, equipment_ids)
    contracts = await _bulk_many(session, Contract, equipment_ids)
    requests = await _bulk_many(session, PurchaseRequest, equipment_ids)
    orders = await _bulk_many(session, PurchaseOrder, equipment_ids)
    supplier_equipment_ids = {
        row[0]
        for row in (
            await session.execute(
                select(EquipmentSupplier.equipment_id).where(
                    EquipmentSupplier.equipment_id.in_(equipment_ids)
                )
            )
        ).all()
    }
    equipments = equipments or {}
    return {
        equipment_id: ProcessState(
            negotiation=negotiations.get(equipment_id),
            legal=legals.get(equipment_id),
            contracts=contracts.get(equipment_id, []),
            purchase_requests=requests.get(equipment_id, []),
            purchase_orders=orders.get(equipment_id, []),
            equipment=equipments.get(equipment_id),
            has_supplier=equipment_id in supplier_equipment_ids,
        )
        for equipment_id in equipment_ids
    }


async def _bulk_waived_groups(
    session: AsyncSession, equipment_ids: list[str]
) -> dict[str, set[tuple[int, str]]]:
    """Etapa 7.1: grupos dispensados (waiver ACTIVE) por equipamento, para a
    fila nunca mostrar como "pendente" algo que já foi marcado como "Não
    possui" no detalhe do equipamento."""
    if not equipment_ids:
        return {}
    rows = (
        await session.execute(
            select(
                RequirementWaiver.equipment_id,
                RequirementWaiver.stage,
                RequirementWaiver.requirement_group_code,
            ).where(
                RequirementWaiver.equipment_id.in_(equipment_ids),
                RequirementWaiver.status == "ACTIVE",
            )
        )
    ).all()
    result: dict[str, set[tuple[int, str]]] = {}
    for equipment_id, stage, code in rows:
        result.setdefault(equipment_id, set()).add((stage, code))
    return result


def _pending(
    stage: int, state: ProcessState, waived: set[tuple[int, str]]
) -> list[PendingRequirementOut]:
    if stage >= FINAL_STAGE:
        return []
    return [
        PendingRequirementOut(code=spec.code, field=", ".join(spec.fields), message=spec.message)
        for spec in groups_for(stage)
        if not spec.check(state) and (stage, spec.code) not in waived
    ]


def _named(item: Any) -> NamedRefOut | None:
    if item is None:
        return None
    return NamedRefOut(id=item.id, name=item.name, code=getattr(item, "code", None))


def _named_work_packages(links: list[EquipmentWorkPackage]) -> list[NamedRefOut]:
    return [
        NamedRefOut(id=link.work_package.id, code=link.work_package.code, name=link.work_package.name)
        for link in sorted(links, key=lambda item: item.work_package.code)
    ]


def _user(item: Any) -> UserRefOut | None:
    if item is None:
        return None
    return UserRefOut(id=item.id, name=item.name, email=item.email)


def _base_fields(
    equipment: Equipment, state: ProcessState, waived: set[tuple[int, str]]
) -> dict[str, Any]:
    stage = equipment.current_stage
    next_stage = stage + 1 if stage < FINAL_STAGE else None
    context = equipment.project_context
    return {
        "equipment_id": equipment.id,
        "equipment_name": equipment.name,
        "unit": NamedRefOut(id=context.unit.id, name=context.unit.name, code=context.unit.code),
        "project_context": NamedRefOut(id=context.id, name=context.name, code=context.code),
        "current_stage": stage,
        "current_stage_name": STAGES[stage],
        "next_stage": next_stage,
        "next_stage_name": STAGES[next_stage] if next_stage is not None else None,
        "pending": _pending(stage, state, waived),
    }


async def engineering_queue(
    session: AsyncSession, filters: QueueFilters, actor: CurrentUser
) -> EngineeringQueueOut:
    equipments, pagination = await _load_page(session, "engineering", filters, actor)
    ids = [item.id for item in equipments]
    states = await _process_states(session, ids, {item.id: item for item in equipments})
    counts = await _component_counts(session, ids)
    waived = await _bulk_waived_groups(session, ids)
    return EngineeringQueueOut(
        items=[
            EngineeringRowOut(
                **_base_fields(equipment, states[equipment.id], waived.get(equipment.id, set())),
                discipline=_named(equipment.discipline),
                area=_named(equipment.area),
                work_packages=_named_work_packages(equipment.work_package_links),
                responsible_user=_user(equipment.responsible_user),
                startup_at=equipment.startup_at,
                criticality=equipment.criticality,
                components_count=counts.get(equipment.id, 0),
            )
            for equipment in equipments
        ],
        pagination=pagination,
    )


async def _component_counts(session: AsyncSession, equipment_ids: list[str]) -> dict[str, int]:
    if not equipment_ids:
        return {}
    rows = (
        await session.execute(
            select(EquipmentComponent.equipment_id, func.count(EquipmentComponent.id))
            .where(EquipmentComponent.equipment_id.in_(equipment_ids))
            .group_by(EquipmentComponent.equipment_id)
        )
    ).all()
    return {equipment_id: count for equipment_id, count in rows}


async def legal_queue(session: AsyncSession, filters: QueueFilters, actor: CurrentUser) -> LegalQueueOut:
    equipments, pagination = await _load_page(session, "legal", filters, actor)
    ids = [item.id for item in equipments]
    states = await _process_states(session, ids, {item.id: item for item in equipments})
    waived = await _bulk_waived_groups(session, ids)
    items: list[LegalRowOut] = []
    for equipment in equipments:
        state = states[equipment.id]
        legal = state.legal
        # Etapa 7A: contrato 1:N — a fila mostra o mais recente; a lista
        # completa vem de GET /equipments/{id}/contracts.
        contract = state.contracts[-1] if state.contracts else None
        items.append(
            LegalRowOut(
                **_base_fields(equipment, state, waived.get(equipment.id, set())),
                responsible_user=_user(equipment.responsible_user),
                opened_at=legal.opened_at if legal else None,
                ticket_number=legal.ticket_number if legal else None,
                draft_prepared=bool(legal and legal.draft_prepared),
                draft_approved=bool(legal and legal.draft_approved),
                contract_number=contract.contract_number if contract else None,
                executed_at=contract.executed_at if contract else None,
                contractual_delivery_start=equipment.contractual_delivery_start,
                contractual_delivery_end=equipment.contractual_delivery_end,
            )
        )
    return LegalQueueOut(items=items, pagination=pagination)


async def procurement_queue(
    session: AsyncSession, filters: QueueFilters, actor: CurrentUser
) -> ProcurementQueueOut:
    equipments, pagination = await _load_page(session, "procurement", filters, actor)
    ids = [item.id for item in equipments]
    states = await _process_states(session, ids, {item.id: item for item in equipments})
    suppliers = await primary_suppliers(session, ids)
    waived = await _bulk_waived_groups(session, ids)
    items: list[ProcurementRowOut] = []
    for equipment in equipments:
        state = states[equipment.id]
        # Etapa 7A: SC/OCI e OC 1:N — a fila mostra a mais recente de cada.
        request = state.purchase_requests[-1] if state.purchase_requests else None
        order = state.purchase_orders[-1] if state.purchase_orders else None
        supplier = suppliers.get(equipment.id)
        items.append(
            ProcurementRowOut(
                **_base_fields(equipment, state, waived.get(equipment.id, set())),
                responsible_user=_user(equipment.responsible_user),
                primary_supplier=(
                    SupplierRefOut(
                        id=supplier.id,
                        legal_name=supplier.legal_name,
                        trade_name=supplier.trade_name,
                    )
                    if supplier
                    else None
                ),
                kind=request.kind if request else None,
                request_number=request.request_number if request else None,
                requested_at=request.requested_at if request else None,
                order_number=order.order_number if order else None,
                ordered_at=order.ordered_at if order else None,
                amount=order.amount if order else None,
            )
        )
    return ProcurementQueueOut(items=items, pagination=pagination)
