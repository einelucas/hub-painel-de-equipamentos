from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.queues import service
from app.modules.queues.schemas import (
    EngineeringQueueOut,
    LegalQueueOut,
    ProcurementQueueOut,
)
from app.modules.queues.service import QueueFilters

router = APIRouter(prefix="/queues", tags=["filas"])

_read = require_permission(Permission.EQUIPMENTS_READ)


def _queue_filters(
    unit_id: str | None = Query(default=None),
    equipment_id: str | None = Query(default=None),
    stage: int | None = Query(default=None, ge=0, le=8),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, alias="pageSize", ge=1, le=100),
) -> QueueFilters:
    return QueueFilters(
        unit_id=unit_id,
        equipment_id=equipment_id,
        stage=stage,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/engineering", response_model=EngineeringQueueOut)
async def get_engineering_queue(
    filters: QueueFilters = Depends(_queue_filters),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> EngineeringQueueOut:
    return await service.engineering_queue(session, filters)


@router.get("/legal", response_model=LegalQueueOut)
async def get_legal_queue(
    filters: QueueFilters = Depends(_queue_filters),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> LegalQueueOut:
    return await service.legal_queue(session, filters)


@router.get("/procurement", response_model=ProcurementQueueOut)
async def get_procurement_queue(
    filters: QueueFilters = Depends(_queue_filters),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(_read),
) -> ProcurementQueueOut:
    return await service.procurement_queue(session, filters)
