"""API do simulador de startup; escopo por obra e permissão de equipamentos."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.startup_simulations import services
from app.modules.startup_simulations.schemas import (
    ScenarioCloneIn,
    ScenarioCreateIn,
    ScenarioListOut,
    ScenarioOut,
    ScenarioUpdateIn,
)

router = APIRouter(prefix="/startup-scenarios", tags=["simulacoes-startup"])


@router.get("", response_model=ScenarioListOut)
async def get_startup_scenarios(
    project_context_id: str = Query(),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> ScenarioListOut:
    return await services.list_scenarios(session, actor, project_context_id)


@router.post("", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def post_startup_scenario(
    body: ScenarioCreateIn, session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> ScenarioOut:
    return await services.create_scenario(session, actor, body)


@router.put("/{scenario_id}", response_model=ScenarioOut)
async def put_startup_scenario(
    scenario_id: str, body: ScenarioUpdateIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> ScenarioOut:
    return await services.update_scenario(session, actor, scenario_id, body)


@router.post("/{scenario_id}/clone", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def post_clone_startup_scenario(
    scenario_id: str, body: ScenarioCloneIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> ScenarioOut:
    return await services.clone_scenario(session, actor, scenario_id, body)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_startup_scenario(
    scenario_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> None:
    await services.delete_scenario(session, actor, scenario_id)
