from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.suppliers import service
from app.modules.suppliers.schemas import (
    EquipmentSupplierLinkIn,
    EquipmentSupplierListOut,
    EquipmentSupplierOut,
    EquipmentSupplierUpdateIn,
    SupplierCreateIn,
    SupplierListOut,
    SupplierOut,
    SupplierUpdateIn,
)

router = APIRouter(tags=["fornecedores"])

_read = require_permission(Permission.SUPPLIERS_READ)
_write = require_permission(Permission.SUPPLIERS_WRITE)


@router.get("/suppliers", response_model=SupplierListOut)
async def get_suppliers(
    search: str | None = Query(default=None, max_length=200),
    include_inactive: bool = Query(default=False, alias="includeInactive"),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> SupplierListOut:
    items = await service.list_suppliers(session, search=search, include_inactive=include_inactive)
    return SupplierListOut(items=[SupplierOut.model_validate(item) for item in items])


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def post_supplier(
    body: SupplierCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> SupplierOut:
    item = await service.create_supplier(session, values=body.model_dump(), actor=actor)
    return SupplierOut.model_validate(item)


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> SupplierOut:
    return SupplierOut.model_validate(await service.get_supplier(session, supplier_id))


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def patch_supplier(
    supplier_id: str,
    body: SupplierUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> SupplierOut:
    item = await service.update_supplier(
        session,
        supplier_id=supplier_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return SupplierOut.model_validate(item)


@router.get("/equipments/{equipment_id}/suppliers", response_model=EquipmentSupplierListOut)
async def get_equipment_suppliers(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_read),
) -> EquipmentSupplierListOut:
    return EquipmentSupplierListOut(
        items=await service.list_equipment_suppliers(session, equipment_id, actor)
    )


@router.post(
    "/equipments/{equipment_id}/suppliers",
    response_model=EquipmentSupplierOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_equipment_supplier(
    equipment_id: str,
    body: EquipmentSupplierLinkIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> EquipmentSupplierOut:
    return await service.link_supplier(
        session,
        equipment_id=equipment_id,
        supplier_id=body.supplier_id,
        role=body.role,
        is_primary=body.is_primary,
        actor=actor,
    )


@router.patch(
    "/equipments/{equipment_id}/suppliers/{supplier_id}", response_model=EquipmentSupplierOut
)
async def patch_equipment_supplier(
    equipment_id: str,
    supplier_id: str,
    body: EquipmentSupplierUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> EquipmentSupplierOut:
    return await service.update_link(
        session,
        equipment_id=equipment_id,
        supplier_id=supplier_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )


@router.delete(
    "/equipments/{equipment_id}/suppliers/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    # `-> None` vira NoneType (truthy) e o FastAPI recusaria corpo em 204.
    response_model=None,
    response_class=Response,
)
async def delete_equipment_supplier(
    equipment_id: str,
    supplier_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_write),
) -> None:
    await service.unlink_supplier(
        session, equipment_id=equipment_id, supplier_id=supplier_id, actor=actor
    )
