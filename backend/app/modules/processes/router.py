from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.models.process import (
    Contract,
    LegalProcess,
    Negotiation,
    PurchaseOrder,
    PurchaseRequest,
)
from app.modules.processes import service
from app.modules.processes.schemas import (
    ContractOut,
    ContractUpdateIn,
    EquipmentProcessesOut,
    LegalProcessOut,
    LegalProcessUpdateIn,
    NegotiationOut,
    NegotiationUpdateIn,
    PurchaseOrderOut,
    PurchaseOrderUpdateIn,
    PurchaseRequestOut,
    PurchaseRequestUpdateIn,
)

router = APIRouter(tags=["processo-aquisicao"])

_read = require_permission(Permission.EQUIPMENTS_READ)
_write = require_permission(Permission.PROCESS_WRITE)


@router.get("/equipments/{equipment_id}/processes", response_model=EquipmentProcessesOut)
async def get_processes(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> EquipmentProcessesOut:
    return await service.get_all_processes(session, equipment_id)


@router.get("/equipments/{equipment_id}/negotiation", response_model=NegotiationOut)
async def get_negotiation(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> NegotiationOut:
    return service.negotiation_out(
        equipment_id, await service.get_process(session, Negotiation, equipment_id)
    )


@router.patch("/equipments/{equipment_id}/negotiation", response_model=NegotiationOut)
async def patch_negotiation(
    equipment_id: str,
    body: NegotiationUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> NegotiationOut:
    item = await service.update_process(
        session,
        model=Negotiation,
        entity_name="Negotiation",
        equipment_id=equipment_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return NegotiationOut.model_validate(item)


@router.get("/equipments/{equipment_id}/legal", response_model=LegalProcessOut)
async def get_legal(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> LegalProcessOut:
    return service.legal_out(
        equipment_id, await service.get_process(session, LegalProcess, equipment_id)
    )


@router.patch("/equipments/{equipment_id}/legal", response_model=LegalProcessOut)
async def patch_legal(
    equipment_id: str,
    body: LegalProcessUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> LegalProcessOut:
    item = await service.update_process(
        session,
        model=LegalProcess,
        entity_name="LegalProcess",
        equipment_id=equipment_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return LegalProcessOut.model_validate(item)


@router.get("/equipments/{equipment_id}/contract", response_model=ContractOut)
async def get_contract(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> ContractOut:
    return service.contract_out(
        equipment_id, await service.get_process(session, Contract, equipment_id)
    )


@router.patch("/equipments/{equipment_id}/contract", response_model=ContractOut)
async def patch_contract(
    equipment_id: str,
    body: ContractUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ContractOut:
    item = await service.update_process(
        session,
        model=Contract,
        entity_name="Contract",
        equipment_id=equipment_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return ContractOut.model_validate(item)


@router.get("/equipments/{equipment_id}/purchase-request", response_model=PurchaseRequestOut)
async def get_purchase_request(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> PurchaseRequestOut:
    return service.purchase_request_out(
        equipment_id, await service.get_process(session, PurchaseRequest, equipment_id)
    )


@router.patch("/equipments/{equipment_id}/purchase-request", response_model=PurchaseRequestOut)
async def patch_purchase_request(
    equipment_id: str,
    body: PurchaseRequestUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> PurchaseRequestOut:
    item = await service.update_process(
        session,
        model=PurchaseRequest,
        entity_name="PurchaseRequest",
        equipment_id=equipment_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return PurchaseRequestOut.model_validate(item)


@router.get("/equipments/{equipment_id}/purchase-order", response_model=PurchaseOrderOut)
async def get_purchase_order(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> PurchaseOrderOut:
    return service.purchase_order_out(
        equipment_id, await service.get_process(session, PurchaseOrder, equipment_id)
    )


@router.patch("/equipments/{equipment_id}/purchase-order", response_model=PurchaseOrderOut)
async def patch_purchase_order(
    equipment_id: str,
    body: PurchaseOrderUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> PurchaseOrderOut:
    item = await service.update_process(
        session,
        model=PurchaseOrder,
        entity_name="PurchaseOrder",
        equipment_id=equipment_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return PurchaseOrderOut.model_validate(item)
