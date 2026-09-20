from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardSummaryOut

router = APIRouter(prefix="/dashboard", tags=["painel"])


@router.get("/summary", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    unit_id: str | None = Query(default=None),
    equipment_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> DashboardSummaryOut:
    return await service.get_summary(
        session, actor=actor, unit_id=unit_id, equipment_id=equipment_id
    )
