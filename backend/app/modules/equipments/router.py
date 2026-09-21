from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.equipments import service
from app.modules.equipments.schemas import (
    ComponentCreateIn,
    ComponentListOut,
    ComponentOut,
    ComponentUpdateIn,
    EquipmentCreateIn,
    EquipmentDetailOut,
    EquipmentListOut,
    EquipmentOut,
    EquipmentUpdateIn,
)

router = APIRouter(tags=["equipamentos"])


@router.get("/equipments", response_model=EquipmentListOut)
async def get_equipments(
    unit_id: str | None = Query(default=None),
    project_context_id: str | None = Query(default=None),
    equipment_id: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    stage: int | None = Query(default=None, ge=0, le=8),
    discipline_id: str | None = Query(default=None),
    responsible_user_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
    sort_by: str = Query(default="name", alias="sortBy"),
    sort_dir: str = Query(default="asc", alias="sortDir", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> EquipmentListOut:
    return await service.list_equipments(
        session,
        actor=actor,
        unit_id=unit_id,
        project_context_id=project_context_id,
        equipment_id=equipment_id,
        search=search,
        stage=stage,
        discipline_id=discipline_id,
        responsible_user_id=responsible_user_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.post("/equipments", response_model=EquipmentOut, status_code=status.HTTP_201_CREATED)
async def post_equipment(
    body: EquipmentCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> EquipmentOut:
    return await service.create_equipment(session, values=body.model_dump(), actor=actor)


@router.get("/equipments/{equipment_id}", response_model=EquipmentDetailOut)
async def get_equipment(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> EquipmentDetailOut:
    return await service.get_equipment_detail(session, equipment_id, actor)


@router.patch("/equipments/{equipment_id}", response_model=EquipmentOut)
async def patch_equipment(
    equipment_id: str,
    body: EquipmentUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> EquipmentOut:
    return await service.update_equipment(
        session, equipment_id=equipment_id, changes=body.model_dump(exclude_unset=True), actor=actor
    )


@router.get("/equipments/{equipment_id}/components", response_model=ComponentListOut)
async def get_components(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> ComponentListOut:
    return ComponentListOut(
        items=[
            service.component_out(item)
            for item in await service.list_components(session, equipment_id, actor)
        ]
    )


@router.post(
    "/equipments/{equipment_id}/components",
    response_model=ComponentOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_component(
    equipment_id: str,
    body: ComponentCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> ComponentOut:
    item = await service.create_component(
        session, equipment_id=equipment_id, values=body.model_dump(), actor=actor
    )
    return service.component_out(item)


@router.patch("/components/{component_id}", response_model=ComponentOut)
async def patch_component(
    component_id: str,
    body: ComponentUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> ComponentOut:
    item = await service.update_component(
        session, component_id=component_id, changes=body.model_dump(exclude_unset=True), actor=actor
    )
    return service.component_out(item)
