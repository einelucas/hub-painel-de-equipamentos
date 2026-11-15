"""API independente de unidades, obras e cenários do Simulador de Startup."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_permission
from app.core.database import get_session
from app.core.permissions import Permission
from app.modules.startup_simulations import services
from app.modules.startup_simulations.schemas import (
    NamedSimulationIn,
    ScenarioCloneIn,
    ScenarioCreateIn,
    ScenarioListOut,
    ScenarioOut,
    ScenarioUpdateIn,
    SimulationProjectListOut,
    SimulationProjectOut,
    SimulationUnitListOut,
    SimulationUnitOut,
)

units_router = APIRouter(prefix="/startup-simulation-units", tags=["simulacoes-startup"])
projects_router = APIRouter(prefix="/startup-simulation-projects", tags=["simulacoes-startup"])
router = APIRouter(prefix="/startup-scenarios", tags=["simulacoes-startup"])


@units_router.get("", response_model=SimulationUnitListOut)
async def get_simulation_units(
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> SimulationUnitListOut:
    return await services.list_units(session)


@units_router.post("", response_model=SimulationUnitOut, status_code=status.HTTP_201_CREATED)
async def post_simulation_unit(
    body: NamedSimulationIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> SimulationUnitOut:
    return await services.create_unit(session, body)


@units_router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_simulation_unit(
    unit_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> None:
    await services.delete_unit(session, unit_id)


@projects_router.get("", response_model=SimulationProjectListOut)
async def get_simulation_projects(
    unit_id: str = Query(),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> SimulationProjectListOut:
    return await services.list_projects(session, unit_id)


@projects_router.post("", response_model=SimulationProjectOut, status_code=status.HTTP_201_CREATED)
async def post_simulation_project(
    body: NamedSimulationIn,
    unit_id: str = Query(),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> SimulationProjectOut:
    return await services.create_project(session, unit_id, body)


@projects_router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_simulation_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> None:
    await services.delete_project(session, project_id)


@router.get("", response_model=ScenarioListOut)
async def get_startup_scenarios(
    simulation_project_id: str = Query(),
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_READ)),
) -> ScenarioListOut:
    return await services.list_scenarios(session, simulation_project_id)


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
    return await services.update_scenario(session, scenario_id, body)


@router.post("/{scenario_id}/clone", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
async def post_clone_startup_scenario(
    scenario_id: str, body: ScenarioCloneIn,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> ScenarioOut:
    return await services.clone_scenario(session, actor, scenario_id, body)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_startup_scenario(
    scenario_id: str,
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(require_permission(Permission.EQUIPMENTS_WRITE)),
) -> None:
    await services.delete_scenario(session, scenario_id)
