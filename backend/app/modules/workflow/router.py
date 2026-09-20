from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.workflow import service
from app.modules.workflow.schemas import (
    AvailableTransitionsOut,
    HistoryOut,
    TransitionRequestIn,
)

router = APIRouter(tags=["workflow"])


@router.get(
    "/equipments/{equipment_id}/available-transitions", response_model=AvailableTransitionsOut
)
async def get_available_transitions(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> AvailableTransitionsOut:
    return await service.available_transitions(session, equipment_id, actor)


@router.post("/equipments/{equipment_id}/transitions", response_model=AvailableTransitionsOut)
async def post_transition(
    equipment_id: str,
    body: TransitionRequestIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.WORKFLOW_TRANSITION)),
) -> AvailableTransitionsOut:
    return await service.execute_transition(
        session,
        equipment_id=equipment_id,
        target_stage=body.target_stage,
        reason=body.reason,
        actor=actor,
    )


@router.get("/equipments/{equipment_id}/history", response_model=HistoryOut)
async def get_history(
    equipment_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.WORKFLOW_READ)),
) -> HistoryOut:
    return await service.history(session, equipment_id)
