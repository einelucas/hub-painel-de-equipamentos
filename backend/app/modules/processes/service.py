"""Persistência dos dados do processo de aquisição.

Negotiation e LegalProcess continuam 1:1 com o equipamento, criados sob
demanda (`ensure_process`/`update_process`). Contract, PurchaseRequest e
PurchaseOrder são 1:N desde a Etapa 7A — cada `POST` cria um registro novo;
`PATCH`/upload de arquivo agem sobre um `id` específico
(`list_items`/`create_item`/`update_item`/`delete_item`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.core.scope import assert_equipment_allowed
from app.core.storage import get_contract_file_storage
from app.models.equipment import Equipment
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)
from app.modules.equipments.schemas import UserRefOut
from app.modules.processes.schemas import (
    ContractFileOut,
    ContractOut,
    EquipmentProcessesOut,
    LegalProcessOut,
    NegotiationOut,
    PurchaseOrderOut,
    PurchaseRequestOut,
)
from app.shared.audit import record_audit

ProcessModel = TypeVar("ProcessModel", Negotiation, LegalProcess)
ManyProcessModel = TypeVar("ManyProcessModel", Contract, PurchaseRequest, PurchaseOrder)


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


def contract_out(item: Contract) -> ContractOut:
    file_out = None
    if item.file_storage_key:
        file_out = ContractFileOut(
            file_name=item.file_name or item.file_storage_key,
            file_content_type=item.file_content_type,
            file_size_bytes=item.file_size_bytes,
            file_uploaded_by=(
                UserRefOut(
                    id=item.file_uploaded_by.id,
                    name=item.file_uploaded_by.name,
                    email=item.file_uploaded_by.email,
                )
                if item.file_uploaded_by
                else None
            ),
            file_uploaded_at=item.file_uploaded_at,
        )
    return ContractOut(
        id=item.id,
        equipment_id=item.equipment_id,
        contract_number=item.contract_number,
        executed_at=item.executed_at,
        file=file_out,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def get_all_processes(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> EquipmentProcessesOut:
    await _assert_equipment(session, equipment_id, actor)
    contracts = await list_items(session, Contract, equipment_id)
    return EquipmentProcessesOut(
        negotiation=negotiation_out(
            equipment_id, await get_process(session, Negotiation, equipment_id)
        ),
        legal=legal_out(equipment_id, await get_process(session, LegalProcess, equipment_id)),
        contracts=[contract_out(item) for item in contracts],
        purchase_requests=[
            PurchaseRequestOut.model_validate(item)
            for item in await list_items(session, PurchaseRequest, equipment_id)
        ],
        purchase_orders=[
            PurchaseOrderOut.model_validate(item)
            for item in await list_items(session, PurchaseOrder, equipment_id)
        ],
    )


# --- Contract / PurchaseRequest / PurchaseOrder: 1:N (Etapa 7A) ---


def _many_load_options(model: type[ManyProcessModel]) -> tuple[Any, ...]:
    if model is Contract:
        return (joinedload(Contract.file_uploaded_by),)
    return ()


async def list_items(
    session: AsyncSession, model: type[ManyProcessModel], equipment_id: str
) -> list[ManyProcessModel]:
    stmt = (
        select(model)
        .where(model.equipment_id == equipment_id)
        .order_by(model.created_at)
        .options(*_many_load_options(model))
    )
    return list((await session.execute(stmt)).scalars().all())


async def _item_or_404(
    session: AsyncSession, model: type[ManyProcessModel], equipment_id: str, item_id: str
) -> ManyProcessModel:
    stmt = (
        select(model)
        .where(model.equipment_id == equipment_id, model.id == item_id)
        .options(*_many_load_options(model))
    )
    item = (await session.execute(stmt)).scalar_one_or_none()
    if item is None:
        raise NotFoundError("Registro não encontrado")
    return item


async def create_item(
    session: AsyncSession,
    *,
    model: type[ManyProcessModel],
    entity_name: str,
    equipment_id: str,
    values: dict[str, Any],
    actor: CurrentUser,
) -> ManyProcessModel:
    await _assert_equipment(session, equipment_id, actor)
    instance = model(equipment_id=equipment_id, **values)
    session.add(instance)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action=f"{entity_name.lower()}.create",
        entity=entity_name,
        entity_id=instance.id,
        new_data={key: _json_value(value) for key, value in values.items()},
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()
    await session.refresh(instance)
    return instance


async def update_item(
    session: AsyncSession,
    *,
    model: type[ManyProcessModel],
    entity_name: str,
    equipment_id: str,
    item_id: str,
    changes: dict[str, Any],
    actor: CurrentUser,
) -> ManyProcessModel:
    await _assert_equipment(session, equipment_id, actor)
    instance = await _item_or_404(session, model, equipment_id, item_id)
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


async def delete_item(
    session: AsyncSession,
    *,
    model: type[ManyProcessModel],
    entity_name: str,
    equipment_id: str,
    item_id: str,
    actor: CurrentUser,
) -> None:
    await _assert_equipment(session, equipment_id, actor)
    instance = await _item_or_404(session, model, equipment_id, item_id)
    if isinstance(instance, Contract) and instance.file_storage_key:
        await get_contract_file_storage().delete(instance.file_storage_key)
    await session.delete(instance)
    await record_audit(
        session,
        user_id=actor.id,
        action=f"{entity_name.lower()}.delete",
        entity=entity_name,
        entity_id=item_id,
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()


_MAX_CONTRACT_FILE_BYTES = 20 * 1024 * 1024  # 20 MB — teto explícito de upload.


async def upload_contract_file(
    session: AsyncSession,
    *,
    equipment_id: str,
    contract_id: str,
    file_name: str,
    content_type: str | None,
    content: bytes,
    actor: CurrentUser,
) -> Contract:
    """Cada contrato tem no máximo um arquivo — um novo upload substitui o
    anterior (metadado no Postgres, bytes no storage configurado)."""
    await _assert_equipment(session, equipment_id, actor)
    contract = await _item_or_404(session, Contract, equipment_id, contract_id)
    if len(content) > _MAX_CONTRACT_FILE_BYTES:
        raise DomainError("Arquivo excede o tamanho máximo permitido (20 MB).")
    storage = get_contract_file_storage()
    key = f"contracts/{contract.id}/{file_name}"
    await storage.save(key, content)
    if contract.file_storage_key and contract.file_storage_key != key:
        await storage.delete(contract.file_storage_key)
    contract.file_storage_key = key
    contract.file_name = file_name
    contract.file_content_type = content_type
    contract.file_size_bytes = len(content)
    contract.file_uploaded_by_id = actor.id
    contract.file_uploaded_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="contract.file_uploaded",
        entity="Contract",
        entity_id=contract.id,
        new_data={"fileName": file_name, "fileSizeBytes": len(content)},
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()
    await session.refresh(contract)
    return contract


async def download_contract_file(
    session: AsyncSession, *, equipment_id: str, contract_id: str, actor: CurrentUser
) -> tuple[bytes, Contract]:
    await _assert_equipment(session, equipment_id, actor)
    contract = await _item_or_404(session, Contract, equipment_id, contract_id)
    if not contract.file_storage_key:
        raise NotFoundError("Este contrato não possui arquivo.")
    content = await get_contract_file_storage().load(contract.file_storage_key)
    return content, contract
