from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.models.equipment import Area, Discipline, ProjectContext, Unit, WorkPackage
from app.modules.catalogs import service
from app.modules.catalogs.schemas import (
    AreaCreateIn,
    AreaOut,
    CatalogListOut,
    CatalogUpdateIn,
    DisciplineCreateIn,
    DisciplineOut,
    ProjectContextCreateIn,
    ProjectContextOut,
    UnitCreateIn,
    UnitOut,
    WorkPackageCreateIn,
    WorkPackageOut,
)

router = APIRouter(tags=["catálogos"])


@router.get("/units", response_model=CatalogListOut)
async def get_units(
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_READ)),
) -> CatalogListOut:
    items = await service.list_units(session, actor)
    return CatalogListOut(items=[UnitOut.model_validate(item) for item in items])


@router.post("/units", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
async def post_unit(
    body: UnitCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> UnitOut:
    item = await service.create_catalog(session, Unit, values=body.model_dump(), actor=actor)
    return UnitOut.model_validate(item)


@router.get("/units/{unit_id}/project-contexts", response_model=CatalogListOut)
async def get_project_contexts(
    unit_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_READ)),
) -> CatalogListOut:
    items = await service.list_project_contexts(session, actor, unit_id)
    return CatalogListOut(items=[ProjectContextOut.model_validate(item) for item in items])


@router.post(
    "/units/{unit_id}/project-contexts", response_model=ProjectContextOut, status_code=status.HTTP_201_CREATED
)
async def post_project_context(
    unit_id: str,
    body: ProjectContextCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> ProjectContextOut:
    values = body.model_dump() | {"unit_id": unit_id}
    item = await service.create_catalog(session, ProjectContext, values=values, actor=actor)
    return ProjectContextOut.model_validate(item)


@router.get("/areas", response_model=CatalogListOut)
async def get_areas(
    unit_id: str = Query(alias="unit_id"),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_READ)),
) -> CatalogListOut:
    items = await service.list_areas(session, actor, unit_id)
    return CatalogListOut(items=[AreaOut.model_validate(item) for item in items])


@router.post("/areas", response_model=AreaOut, status_code=status.HTTP_201_CREATED)
async def post_area(
    body: AreaCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> AreaOut:
    return AreaOut.model_validate(
        await service.create_catalog(session, Area, values=body.model_dump(), actor=actor)
    )


@router.get("/disciplines", response_model=CatalogListOut)
async def get_disciplines(
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CATALOGS_READ)),
) -> CatalogListOut:
    return CatalogListOut(
        items=[DisciplineOut.model_validate(item) for item in await service.list_disciplines(session)]
    )


@router.post("/disciplines", response_model=DisciplineOut, status_code=status.HTTP_201_CREATED)
async def post_discipline(
    body: DisciplineCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> DisciplineOut:
    return DisciplineOut.model_validate(
        await service.create_catalog(session, Discipline, values=body.model_dump(), actor=actor)
    )


@router.get("/work-packages", response_model=CatalogListOut)
async def get_work_packages(
    project_context_id: str = Query(alias="project_context_id"),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_READ)),
) -> CatalogListOut:
    items = await service.list_work_packages(session, actor, project_context_id)
    return CatalogListOut(items=[WorkPackageOut.model_validate(item) for item in items])


@router.post("/work-packages", response_model=WorkPackageOut, status_code=status.HTTP_201_CREATED)
async def post_work_package(
    body: WorkPackageCreateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.CATALOGS_MANAGE)),
) -> WorkPackageOut:
    return WorkPackageOut.model_validate(
        await service.create_catalog(session, WorkPackage, values=body.model_dump(), actor=actor)
    )


# Manutenção administrativa: edição e ativação/desativação, sem hard delete.
_manage = require_permission(Permission.CATALOGS_MANAGE)


@router.patch("/units/{item_id}", response_model=UnitOut)
async def patch_unit(
    item_id: str,
    body: CatalogUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_manage),
) -> UnitOut:
    item = await service.update_catalog(
        session, Unit, item_id=item_id, changes=body.model_dump(exclude_unset=True), actor=actor
    )
    return UnitOut.model_validate(item)


@router.patch("/project-contexts/{item_id}", response_model=ProjectContextOut)
async def patch_project_context(
    item_id: str,
    body: CatalogUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_manage),
) -> ProjectContextOut:
    item = await service.update_catalog(
        session,
        ProjectContext,
        item_id=item_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return ProjectContextOut.model_validate(item)


@router.patch("/areas/{item_id}", response_model=AreaOut)
async def patch_area(
    item_id: str,
    body: CatalogUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_manage),
) -> AreaOut:
    changes = body.model_dump(exclude_unset=True)
    changes.pop("code", None)  # área não tem código
    item = await service.update_catalog(
        session, Area, item_id=item_id, changes=changes, actor=actor
    )
    return AreaOut.model_validate(item)


@router.patch("/disciplines/{item_id}", response_model=DisciplineOut)
async def patch_discipline(
    item_id: str,
    body: CatalogUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_manage),
) -> DisciplineOut:
    item = await service.update_catalog(
        session,
        Discipline,
        item_id=item_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return DisciplineOut.model_validate(item)


@router.patch("/work-packages/{item_id}", response_model=WorkPackageOut)
async def patch_work_package(
    item_id: str,
    body: CatalogUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_manage),
) -> WorkPackageOut:
    item = await service.update_catalog(
        session,
        WorkPackage,
        item_id=item_id,
        changes=body.model_dump(exclude_unset=True),
        actor=actor,
    )
    return WorkPackageOut.model_validate(item)
