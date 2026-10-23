"""API global do Catálogo Mestre e criação transacional de obra."""
# ruff: noqa: I001

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission, assert_can
from app.models.master_catalog import MasterArea, MasterComponentOption, MasterEquipment
from app.modules.master_catalog import services
from app.modules.master_catalog.schemas import (
    MasterAreaAssignmentIn,
    MasterAreaCreateIn,
    MasterAreaOut,
    MasterCatalogOut,
    MasterCatalogSeedIn,
    MasterCatalogSeedOut,
    MasterComponentCreateIn,
    MasterComponentOut,
    MasterEquipmentCreateIn,
    MasterProjectCreateIn,
    MasterProjectCreatedOut,
    MasterUpdateIn,
)

router = APIRouter(prefix="/master-catalog", tags=["catálogo mestre"])


@router.get("", response_model=MasterCatalogOut)
async def get_catalog(
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_READ)),
) -> MasterCatalogOut:
    if include_inactive:
        assert_can(actor.role, Permission.CATALOGS_MANAGE)
    return await services.catalog(session, include_inactive=include_inactive)


@router.post("/seed", response_model=MasterCatalogSeedOut)
async def post_seed(
    body: MasterCatalogSeedIn,
    dry_run: bool = Query(True),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> MasterCatalogSeedOut:
    return await services.seed_catalog(session, body, actor, dry_run=dry_run)


@router.post("/projects", response_model=MasterProjectCreatedOut, status_code=status.HTTP_201_CREATED)
async def post_project(
    body: MasterProjectCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> MasterProjectCreatedOut:
    assert_can(actor.role, Permission.EQUIPMENTS_WRITE)
    return await services.create_project_from_master(session, body, actor)


@router.post("/areas", response_model=MasterAreaOut, status_code=201)
async def post_area(
    body: MasterAreaCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> MasterAreaOut:
    return MasterAreaOut.model_validate(
        await services.create_area(session, name=body.name, actor=actor)
    )


@router.post("/equipments", status_code=201)
async def post_master_equipment(
    body: MasterEquipmentCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> dict[str, str]:
    item = await services.create_master_equipment(
        session, name=body.name, area_ids=body.area_ids, actor=actor
    )
    return {"id": item.id}


@router.post("/equipments/{equipment_id}/components", response_model=MasterComponentOut, status_code=201)
async def post_option(
    equipment_id: str,
    body: MasterComponentCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> MasterComponentOut:
    return MasterComponentOut.model_validate(
        await services.create_option(
            session, equipment_id=equipment_id, name=body.name, actor=actor
        )
    )


@router.put("/equipments/{equipment_id}/areas", status_code=204, response_model=None)
async def put_areas(
    equipment_id: str,
    body: MasterAreaAssignmentIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> None:
    await services.assign_areas(
        session, equipment_id=equipment_id, area_ids=body.area_ids, actor=actor
    )


@router.patch("/areas/{item_id}", status_code=204, response_model=None)
async def patch_area(
    item_id: str,
    body: MasterUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> None:
    await services.update_item(session, model=MasterArea, item_id=item_id,
                               name=body.name, active=body.active, actor=actor)


@router.patch("/equipments/{item_id}", status_code=204, response_model=None)
async def patch_master_equipment(
    item_id: str,
    body: MasterUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> None:
    await services.update_item(session, model=MasterEquipment, item_id=item_id,
                               name=body.name, active=body.active, actor=actor)


@router.patch("/components/{item_id}", status_code=204, response_model=None)
async def patch_master_component(
    item_id: str,
    body: MasterUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> None:
    await services.update_item(session, model=MasterComponentOption, item_id=item_id,
                               name=body.name, active=body.active, actor=actor)
