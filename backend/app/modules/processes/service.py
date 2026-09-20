"""Persistência dos dados do processo de aquisição.

Cada processo é 1:1 com o equipamento e criado sob demanda. A criação usa
savepoint + unicidade do banco para não duplicar registros em chamadas
concorrentes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.scope import assert_equipment_allowed
from app.models.equipment import Equipment
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)
from app.modules.processes.schemas import (
    ContractOut,
    EquipmentProcessesOut,
    LegalProcessOut,
    NegotiationOut,
    PurchaseOrderOut,
    PurchaseRequestOut,
)
from app.shared.audit import record_audit

ProcessModel = TypeVar(
    "ProcessModel", Negotiation, LegalProcess, Contract, PurchaseRequest, PurchaseOrder
)


async def _assert_equipment(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> Equipment:
    return await assert_equipment_allowed(session, actor, equipment_id)


async def get_process(
    session: AsyncSession, model: type[ProcessModel], equipment_id: str
) -> ProcessModel | None:
    stmt = select(model).where(model.equipment_id == equipment_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def ensure_process(
    session: AsyncSession, model: type[ProcessModel], equipment_id: str
) -> ProcessModel:
    existing = await get_process(session, model, equipment_id)
    if existing is not None:
        return existing
    try:
        async with session.begin_nested():
            instance = model(equipment_id=equipment_id)
            session.add(instance)
            await session.flush()
    except IntegrityError:
        concurrent = await get_process(session, model, equipment_id)
        if concurrent is None:
            raise
        return concurrent
    return instance


async def assert_readable(session: AsyncSession, equipment_id: str, actor: CurrentUser) -> None:
    await _assert_equipment(session, equipment_id, actor)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


async def update_process(
    session: AsyncSession,
    *,
    model: type[ProcessModel],
    entity_name: str,
    equipment_id: str,
    changes: dict[str, Any],
    actor: CurrentUser,
) -> ProcessModel:
    await _assert_equipment(session, equipment_id, actor)
    instance = await ensure_process(session, model, equipment_id)
    previous: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    for field, value in changes.items():
        old_value = getattr(instance, field)
        if old_value != value:
            previous[field] = _json_value(old_value)
            changed[field] = _json_value(value)
            setattr(instance, field, value)
    if changed:
        await record_audit(
            session,
            user_id=actor.id,
            action=f"{entity_name.lower()}.update",
            entity=entity_name,
            entity_id=instance.id,
            previous_data=previous,
            new_data=changed,
            metadata={"equipmentId": equipment_id},
        )
    await session.commit()
    await session.refresh(instance)
    return instance


def negotiation_out(equipment_id: str, item: Negotiation | None) -> NegotiationOut:
    if item is None:
        return NegotiationOut(equipment_id=equipment_id)
    return NegotiationOut.model_validate(item)


def legal_out(equipment_id: str, item: LegalProcess | None) -> LegalProcessOut:
    if item is None:
        return LegalProcessOut(equipment_id=equipment_id)
    return LegalProcessOut.model_validate(item)


def contract_out(equipment_id: str, item: Contract | None) -> ContractOut:
    if item is None:
        return ContractOut(equipment_id=equipment_id)
    return ContractOut.model_validate(item)


def purchase_request_out(equipment_id: str, item: PurchaseRequest | None) -> PurchaseRequestOut:
    if item is None:
        return PurchaseRequestOut(equipment_id=equipment_id)
    return PurchaseRequestOut.model_validate(item)


def purchase_order_out(equipment_id: str, item: PurchaseOrder | None) -> PurchaseOrderOut:
    if item is None:
        return PurchaseOrderOut(equipment_id=equipment_id)
    return PurchaseOrderOut.model_validate(item)


async def get_all_processes(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> EquipmentProcessesOut:
    await _assert_equipment(session, equipment_id, actor)
    return EquipmentProcessesOut(
        negotiation=negotiation_out(
            equipment_id, await get_process(session, Negotiation, equipment_id)
        ),
        legal=legal_out(equipment_id, await get_process(session, LegalProcess, equipment_id)),
        contract=contract_out(equipment_id, await get_process(session, Contract, equipment_id)),
        purchase_request=purchase_request_out(
            equipment_id, await get_process(session, PurchaseRequest, equipment_id)
        ),
        purchase_order=purchase_order_out(
            equipment_id, await get_process(session, PurchaseOrder, equipment_id)
        ),
    )
