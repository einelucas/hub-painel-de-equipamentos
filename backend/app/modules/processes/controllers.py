from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
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
    ContractCreateIn,
    ContractListOut,
    ContractOut,
    ContractUpdateIn,
    EquipmentProcessesOut,
    LegalProcessOut,
    LegalProcessUpdateIn,
    NegotiationOut,
    NegotiationUpdateIn,
    PurchaseOrderCreateIn,
    PurchaseOrderListOut,
    PurchaseOrderOut,
    PurchaseOrderUpdateIn,
    PurchaseRequestCreateIn,
    PurchaseRequestListOut,
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
    actor: CurrentUser = Depends(_read),
) -> EquipmentProcessesOut:
    return await service.get_all_processes(session, equipment_id, actor)


@router.get("/equipments/{equipment_id}/negotiation", response_model=NegotiationOut)
async def get_negotiation(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> NegotiationOut:
    await service.assert_readable(session, equipment_id, actor)
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
    actor: CurrentUser = Depends(_read),
) -> LegalProcessOut:
    await service.assert_readable(session, equipment_id, actor)
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



# --- Contratos (1:N desde a Etapa 7A) ---


@router.get("/equipments/{equipment_id}/contracts", response_model=ContractListOut)
async def list_contracts(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> ContractListOut:
    await service.assert_readable(session, equipment_id, actor)
    items = await service.list_items(session, Contract, equipment_id)
    return ContractListOut(items=[service.contract_out(item) for item in items])


@router.post(
    "/equipments/{equipment_id}/contracts", response_model=ContractOut, status_code=status.HTTP_201_CREATED
)
async def post_contract(
    equipment_id: str,
    body: ContractCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ContractOut:
    item = await service.create_item(
        session,
        model=Contract,
        entity_name="Contract",
        equipment_id=equipment_id,
        values=body.model_dump(),
        actor=actor,
    )
    return service.contract_out(item)


@router.patch("/equipments/{equipment_id}/contracts/{contract_id}", response_model=ContractOut)
async def patch_contract(
    equipment_id: str,
    contract_id: str,
    body: ContractUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ContractOut:
    item = await service.update_item(
        session,
        model=Contract,
        entity_name="Contract",
        equipment_id=equipment_id,
        item_id=contract_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return service.contract_out(item)


@router.delete(
    "/equipments/{equipment_id}/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def delete_contract(
    equipment_id: str,
    contract_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> None:
    await service.delete_item(
        session,
        model=Contract,
        entity_name="Contract",
        equipment_id=equipment_id,
        item_id=contract_id,
        actor=actor,
    )


_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.put("/equipments/{equipment_id}/contracts/{contract_id}/file", response_model=ContractOut)
async def put_contract_file(
    equipment_id: str,
    contract_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> ContractOut:
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Arquivo excede o tamanho máximo permitido (20 MB).")
    item = await service.upload_contract_file(
        session,
        equipment_id=equipment_id,
        contract_id=contract_id,
        file_name=file.filename or "contrato",
        content_type=file.content_type,
        content=content,
        actor=actor,
    )
    return service.contract_out(item)


@router.get("/equipments/{equipment_id}/contracts/{contract_id}/file")
async def get_contract_file(
    equipment_id: str,
    contract_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> Response:
    content, contract = await service.download_contract_file(
        session, equipment_id=equipment_id, contract_id=contract_id, actor=actor
    )
    return Response(
        content=content,
        media_type=contract.file_content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{contract.file_name}"'},
    )


# --- SC/OCI (1:N desde a Etapa 7A) ---


@router.get("/equipments/{equipment_id}/purchase-requests", response_model=PurchaseRequestListOut)
async def list_purchase_requests(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> PurchaseRequestListOut:
    await service.assert_readable(session, equipment_id, actor)
    items = await service.list_items(session, PurchaseRequest, equipment_id)
    return PurchaseRequestListOut(items=[PurchaseRequestOut.model_validate(item) for item in items])


@router.post(
    "/equipments/{equipment_id}/purchase-requests",
    response_model=PurchaseRequestOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_purchase_request(
    equipment_id: str,
    body: PurchaseRequestCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> PurchaseRequestOut:
    item = await service.create_item(
        session,
        model=PurchaseRequest,
        entity_name="PurchaseRequest",
        equipment_id=equipment_id,
        values=body.model_dump(),
        actor=actor,
    )
    return PurchaseRequestOut.model_validate(item)


@router.patch(
    "/equipments/{equipment_id}/purchase-requests/{request_id}", response_model=PurchaseRequestOut
)
async def patch_purchase_request(
    equipment_id: str,
    request_id: str,
    body: PurchaseRequestUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> PurchaseRequestOut:
    item = await service.update_item(
        session,
        model=PurchaseRequest,
        entity_name="PurchaseRequest",
        equipment_id=equipment_id,
        item_id=request_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return PurchaseRequestOut.model_validate(item)


@router.delete(
    "/equipments/{equipment_id}/purchase-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def delete_purchase_request(
    equipment_id: str,
    request_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> None:
    await service.delete_item(
        session,
        model=PurchaseRequest,
        entity_name="PurchaseRequest",
        equipment_id=equipment_id,
        item_id=request_id,
        actor=actor,
    )


# --- Ordens de Compra (1:N desde a Etapa 7A) ---


@router.get("/equipments/{equipment_id}/purchase-orders", response_model=PurchaseOrderListOut)
async def list_purchase_orders(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> PurchaseOrderListOut:
    await service.assert_readable(session, equipment_id, actor)
    items = await service.list_items(session, PurchaseOrder, equipment_id)
    return PurchaseOrderListOut(items=[PurchaseOrderOut.model_validate(item) for item in items])


@router.post(
    "/equipments/{equipment_id}/purchase-orders",
    response_model=PurchaseOrderOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_purchase_order(
    equipment_id: str,
    body: PurchaseOrderCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> PurchaseOrderOut:
    item = await service.create_item(
        session,
        model=PurchaseOrder,
        entity_name="PurchaseOrder",
        equipment_id=equipment_id,
        values=body.model_dump(),
        actor=actor,
    )
    return PurchaseOrderOut.model_validate(item)


@router.patch("/equipments/{equipment_id}/purchase-orders/{order_id}", response_model=PurchaseOrderOut)
async def patch_purchase_order(
    equipment_id: str,
    order_id: str,
    body: PurchaseOrderUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> PurchaseOrderOut:
    item = await service.update_item(
        session,
        model=PurchaseOrder,
        entity_name="PurchaseOrder",
        equipment_id=equipment_id,
        item_id=order_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return PurchaseOrderOut.model_validate(item)


@router.delete(
    "/equipments/{equipment_id}/purchase-orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    response_class=Response,
)
async def delete_purchase_order(
    equipment_id: str,
    order_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> None:
    await service.delete_item(
        session,
        model=PurchaseOrder,
        entity_name="PurchaseOrder",
        equipment_id=equipment_id,
        item_id=order_id,
        actor=actor,
    )
