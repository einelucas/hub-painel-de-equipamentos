"""CRUD de unidades, obras e cenários próprios; nenhuma consulta ao domínio operacional."""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.models.common import utcnow
from app.models.startup_simulation import (
    SimulationProject,
    SimulationUnit,
    StartupScenario,
    StartupScenarioEquipment,
)
from app.modules.startup_simulations.calculations import calculate_dates, summarize
from app.modules.startup_simulations.schemas import (
    NamedSimulationIn,
    ScenarioCloneIn,
    ScenarioCreateIn,
    ScenarioItemIn,
    ScenarioItemOut,
    ScenarioListOut,
    ScenarioOut,
    ScenarioSummaryOut,
    ScenarioUpdateIn,
    SimulationProjectListOut,
    SimulationProjectOut,
    SimulationUnitListOut,
    SimulationUnitOut,
)


def _key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char)).casefold().split()
    )


async def _unit(session: AsyncSession, unit_id: str) -> SimulationUnit:
    item = await session.get(SimulationUnit, unit_id)
    if item is None:
        raise NotFoundError("Unidade do simulador não encontrada")
    return item


async def _project(session: AsyncSession, project_id: str) -> SimulationProject:
    item = await session.get(SimulationProject, project_id)
    if item is None:
        raise NotFoundError("Obra do simulador não encontrada")
    return item


async def list_units(session: AsyncSession) -> SimulationUnitListOut:
    items = (
        await session.execute(select(SimulationUnit).order_by(SimulationUnit.name))
    ).scalars().all()
    return SimulationUnitListOut(
        items=[SimulationUnitOut.model_validate(item) for item in items]
    )


async def create_unit(
    session: AsyncSession, body: NamedSimulationIn
) -> SimulationUnitOut:
    name_key = _key(body.name)
    if not name_key:
        raise DomainError("Informe uma unidade válida")
    if (await session.execute(
        select(SimulationUnit.id).where(SimulationUnit.name_key == name_key)
    )).scalar_one_or_none():
        raise ConflictError("Esta unidade já existe no simulador")
    unit = SimulationUnit(name=body.name, name_key=name_key)
    session.add(unit)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Esta unidade já existe no simulador") from exc
    return SimulationUnitOut.model_validate(unit)


async def delete_unit(session: AsyncSession, unit_id: str) -> None:
    unit = await _unit(session, unit_id)
    linked = (await session.execute(
        select(SimulationProject.id).where(SimulationProject.unit_id == unit_id).limit(1)
    )).scalar_one_or_none()
    if linked is not None:
        raise ConflictError("Exclua as obras da unidade antes de excluí-la")
    await session.delete(unit)
    await session.flush()


async def list_projects(
    session: AsyncSession, unit_id: str
) -> SimulationProjectListOut:
    await _unit(session, unit_id)
    projects = (await session.execute(
        select(SimulationProject).where(SimulationProject.unit_id == unit_id)
        .order_by(SimulationProject.name)
    )).scalars().all()
    return SimulationProjectListOut(
        items=[SimulationProjectOut.model_validate(p) for p in projects]
    )


async def create_project(
    session: AsyncSession, unit_id: str, body: NamedSimulationIn
) -> SimulationProjectOut:
    await _unit(session, unit_id)
    name_key = _key(body.name)
    if not name_key:
        raise DomainError("Informe uma obra válida")
    exists = (await session.execute(
        select(SimulationProject.id).where(
            SimulationProject.unit_id == unit_id,
            SimulationProject.name_key == name_key,
        )
    )).scalar_one_or_none()
    if exists is not None:
        raise ConflictError("Esta obra já existe nessa unidade do simulador")
    project = SimulationProject(unit_id=unit_id, name=body.name, name_key=name_key)
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Esta obra já existe nessa unidade do simulador") from exc
    return SimulationProjectOut.model_validate(project)


async def delete_project(session: AsyncSession, project_id: str) -> None:
    project = await _project(session, project_id)
    linked = (await session.execute(
        select(StartupScenario.id).where(
            StartupScenario.simulation_project_id == project_id
        ).limit(1)
    )).scalar_one_or_none()
    if linked is not None:
        raise ConflictError("Exclua as simulações da obra antes de excluí-la")
    await session.delete(project)
    await session.flush()


def _item_payload(item: StartupScenarioEquipment) -> ScenarioItemIn:
    return ScenarioItemIn(
        name=item.name, origin=item.origin, discipline=item.discipline,
        supplier=item.supplier, area=item.area, responsible=item.responsible,
        startup_at=item.startup_at, supplies_days=item.supplies_days,
        legal_days=item.legal_days, manufacture_days=item.manufacture_days,
        pre_start_days=item.pre_start_days,
    )


def _make_items(
    scenario: StartupScenario, values: Iterable[ScenarioItemIn]
) -> list[StartupScenarioEquipment]:
    return [
        StartupScenarioEquipment(scenario=scenario, position=index, **item.model_dump())
        for index, item in enumerate(values)
    ]


def _serialize(scenario: StartupScenario) -> ScenarioOut:
    rows: list[dict] = []
    output: list[ScenarioItemOut] = []
    for item in sorted(scenario.items, key=lambda row: row.position):
        planned = calculate_dates(
            item.startup_at or scenario.startup_at,
            item.pre_start_days, item.manufacture_days, item.legal_days,
        )
        rows.append({
            "negotiation_deadline": planned.negotiation,
            "contract_deadline": planned.contract,
            "delivery_deadline": planned.delivery,
            "manufacture_days": item.manufacture_days,
            "pre_start_days": item.pre_start_days,
        })
        output.append(ScenarioItemOut(
            id=item.id, **_item_payload(item).model_dump(),
            delivery_deadline=planned.delivery, contract_deadline=planned.contract,
            negotiation_deadline=planned.negotiation,
        ))
    return ScenarioOut(
        id=scenario.id, simulation_project_id=scenario.simulation_project_id,
        name=scenario.name, startup_at=scenario.startup_at, source=scenario.source,
        created_at=scenario.created_at, updated_at=scenario.updated_at,
        items=output, summary=ScenarioSummaryOut(**summarize(rows)),
    )


async def _load(session: AsyncSession, scenario_id: str) -> StartupScenario:
    scenario = (
        await session.execute(select(StartupScenario).where(StartupScenario.id == scenario_id).options(
            selectinload(StartupScenario.items)
        ))
    ).scalar_one_or_none()
    if scenario is None:
        raise NotFoundError("Simulação não encontrada")
    return scenario


async def list_scenarios(
    session: AsyncSession, simulation_project_id: str
) -> ScenarioListOut:
    await _project(session, simulation_project_id)
    scenarios = (await session.execute(
        select(StartupScenario)
        .where(StartupScenario.simulation_project_id == simulation_project_id)
        .options(selectinload(StartupScenario.items))
        .order_by(StartupScenario.created_at, StartupScenario.id)
    )).scalars().all()
    return ScenarioListOut(items=[_serialize(scenario) for scenario in scenarios])


async def create_scenario(
    session: AsyncSession, actor: CurrentUser, body: ScenarioCreateIn
) -> ScenarioOut:
    await _project(session, body.simulation_project_id)
    scenario = StartupScenario(
        simulation_project_id=body.simulation_project_id, created_by_id=actor.id,
        name=body.name.strip(), startup_at=body.startup_at, source=body.source,
    )
    scenario.items = _make_items(scenario, body.items)
    session.add(scenario)
    await session.flush()
    return _serialize(scenario)


async def update_scenario(
    session: AsyncSession, scenario_id: str, body: ScenarioUpdateIn
) -> ScenarioOut:
    scenario = await _load(session, scenario_id)
    scenario.name = body.name.strip()
    scenario.startup_at = body.startup_at
    # A posição é única por cenário: liberar as posições antigas primeiro.
    scenario.items.clear()
    await session.flush()
    scenario.items = _make_items(scenario, body.items)
    scenario.updated_at = utcnow()
    await session.flush()
    return _serialize(scenario)


async def clone_scenario(
    session: AsyncSession, actor: CurrentUser, scenario_id: str, body: ScenarioCloneIn
) -> ScenarioOut:
    original = await _load(session, scenario_id)
    scenario = StartupScenario(
        simulation_project_id=original.simulation_project_id,
        created_by_id=actor.id, name=body.name.strip(),
        startup_at=body.startup_at, source="MANUAL",
    )
    scenario.items = _make_items(scenario, (_item_payload(item) for item in original.items))
    session.add(scenario)
    await session.flush()
    return _serialize(scenario)


async def delete_scenario(session: AsyncSession, scenario_id: str) -> None:
    scenario = await _load(session, scenario_id)
    await session.delete(scenario)
    await session.flush()
