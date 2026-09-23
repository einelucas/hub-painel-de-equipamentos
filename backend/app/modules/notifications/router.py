from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.notifications import service
from app.modules.notifications.schemas import NotificationEventListOut

router = APIRouter(tags=["notificacoes"])


@router.get("/equipments/{equipment_id}/notifications", response_model=NotificationEventListOut)
async def get_notifications(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> NotificationEventListOut:
    return await service.list_notifications(session, equipment_id, actor)
