"""CRUD isolado de simulações; datas oficiais dos equipamentos nunca são modificadas."""
from __future__ import annotations

import unicodedata
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.core.scope import assert_context_allowed
from app.models.equipment import Equipment
from app.models.startup_simulation import StartupScenario, StartupScenarioEquipment
from app.models.supplier import EquipmentSupplier
from app.modules.startup_simulations.calculations import calculate_dates, summarize
from app.modules.startup_simulations.schemas import (
    ScenarioCloneIn, ScenarioCreateIn, ScenarioItemIn, ScenarioItemOut,
    ScenarioListOut, ScenarioOut, ScenarioSummaryOut, ScenarioUpdateIn,
)


def _normalize_name(value: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", value)
    return " ".join("".join(c for c in ascii_name if not unicodedata.combining(c)).casefold().split())


def _item_payload(item: StartupScenarioEquipment) -> ScenarioItemIn:
    return ScenarioItemIn(
        equipment_id=item.equipment_id, name=item.name, origin=item.origin,
        discipline=item.discipline, supplier=item.supplier, area=item.area,
        responsible=item.responsible, startup_at=item.startup_at,
        supplies_days=item.supplies_days, legal_days=item.legal_days,
        manufacture_days=item.manufacture_days, pre_start_days=item.pre_start_days,
    )


def _make_items(\n    scenario: StartupScenario, values: Iterable[ScenarioItemIn]\n) -> list[StartupScenarioEquipment]:
    return [
        StartupScenarioEquipment(
            scenario=scenario, position=index, **item.model_dump()
        )
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
        id=scenario.id, project_context_id=scenario.project_context_id,
        name=scenario.name, startup_at=scenario.startup_at, source=scenario.source,
        created_at=scenario.created_at, updated_at=scenario.updated_at,
        items=output, summary=ScenarioSummaryOut(**summarize(rows)),
    )


async def _catalog(
    session: AsyncSession, project_context_id: str
) -> tuple[list[ScenarioItemIn], dict[str, str]]:
    stmt = (
        select(Equipment)
        .where(Equipment.project_context_id == project_context_id)
        .options(
            selectinload(Equipment.components),
            joinedload(Equipment.discipline),
            joinedload(Equipment.area),
            joinedload(Equipment.eap_node),
            joinedload(Equipment.responsible_user),
            selectinload(Equipment.supplier_links).joinedload(EquipmentSupplier.supplier),
        )
        .order_by(Equipment.name, Equipment.id)
    )
    equipments = (await session.execute(stmt)).scalars().unique().all()
    matched: dict[str, str] = {}
    collisions: set[str] = set()
    rows: list[ScenarioItemIn] = []
    for equipment in equipments:
        key = _normalize_name(equipment.name)
        if key in matched:
            collisions.add(key)
        else:
            matched[key] = equipment.id
        manufacture = [c.lead_time_days for c in equipment.components if c.lead_time_days is not None]
        pre_start = [c.pre_start_days for c in equipment.components if c.pre_start_days is not None]
        rows.append(ScenarioItemIn(
            equipment_id=equipment.id, name=equipment.name, origin=equipment.origin,
            discipline=equipment.discipline.name if equipment.discipline else None,
            supplier=equipment.supplier_links[0].supplier.legal_name if equipment.supplier_links else None,
            area=equipment.eap_node.name if equipment.eap_node else (
                equipment.area.name if equipment.area else None
            ),
            responsible=equipment.responsible_user.name if equipment.responsible_user else None,
            # 20 dias: prazo explícito da planilha LEM F2, editável em cada simulação.
            legal_days=20,
            manufacture_days=max(manufacture) if manufacture else None,
            pre_start_days=max(pre_start) if pre_start else None,
        ))
    for key in collisions:
        matched.pop(key, None)
    return rows, matched


async def _validate_and_match(
    session: AsyncSession, project_context_id: str,
    items: list[ScenarioItemIn],
) -> list[ScenarioItemIn]:
    if len(items) > 500:
        raise DomainError("Limite de 500 equipamentos por cenário")
    _, by_name = await _catalog(session, project_context_id)
    # IDs de nomes repetidos não estão em by_name, mas ainda podem ser vinculados explicitamente.
    all_ids = set(
        (await session.execute(select(Equipment.id).where(
            Equipment.project_context_id == project_context_id
        ))).scalars().all()
    )
    resolved: list[ScenarioItemIn] = []
    for item in items:
        if item.equipment_id and item.equipment_id not in all_ids:
            raise DomainError("Equipamento fora da obra selecionada")
        related_id = item.equipment_id or by_name.get(_normalize_name(item.name))
        resolved.append(item.model_copy(update={"equipment_id": related_id}))
    return resolved


async def _load(session: AsyncSession, actor: CurrentUser, scenario_id: str) -> StartupScenario:
    scenario = (
        await session.execute(select(StartupScenario).where(StartupScenario.id == scenario_id).options(
            selectinload(StartupScenario.items)
        ))
    ).scalar_one_or_none()
    if scenario is None:
        raise NotFoundError("Cenário não encontrado")
    await assert_context_allowed(session, actor, scenario.project_context_id)
    return scenario


async def list_scenarios(
    session: AsyncSession, actor: CurrentUser, project_context_id: str
) -> ScenarioListOut:
    await assert_context_allowed(session, actor, project_context_id)
    scenarios = (await session.execute(
        select(StartupScenario)
        .where(StartupScenario.project_context_id == project_context_id)
        .options(selectinload(StartupScenario.items))
        .order_by(StartupScenario.created_at, StartupScenario.id)
    )).scalars().all()
    return ScenarioListOut(items=[_serialize(scenario) for scenario in scenarios])


async def create_scenario(
    session: AsyncSession, actor: CurrentUser, body: ScenarioCreateIn
) -> ScenarioOut:
    await assert_context_allowed(session, actor, body.project_context_id)
    if body.items is None:
        values, _ = await _catalog(session, body.project_context_id)
    else:
        values = await _validate_and_match(session, body.project_context_id, body.items)
    scenario = StartupScenario(
        project_context_id=body.project_context_id, created_by_id=actor.id,
        name=body.name.strip(), startup_at=body.startup_at, source=body.source,
    )
    scenario.items = _make_items(scenario, values)
    session.add(scenario)
    await session.flush()
    return _serialize(scenario)


async def update_scenario(
    session: AsyncSession, actor: CurrentUser, scenario_id: str, body: ScenarioUpdateIn
) -> ScenarioOut:
    scenario = await _load(session, actor, scenario_id)
    values = await _validate_and_match(session, scenario.project_context_id, body.items)
    scenario.name = body.name.strip()
    scenario.startup_at = body.startup_at
    scenario.items = _make_items(scenario, values)
    # updated_at é sempre modificado, inclusive quando apenas os itens mudam.
    from app.models.common import utcnow
    scenario.updated_at = utcnow()
    await session.flush()
    return _serialize(scenario)


async def clone_scenario(
    session: AsyncSession, actor: CurrentUser, scenario_id: str, body: ScenarioCloneIn
) -> ScenarioOut:
    original = await _load(session, actor, scenario_id)
    scenario = StartupScenario(
        project_context_id=original.project_context_id,
        created_by_id=actor.id, name=body.name.strip(),
        startup_at=body.startup_at, source="MANUAL",
    )
    scenario.items = _make_items(scenario, (_item_payload(item) for item in original.items))
    session.add(scenario)
    await session.flush()
    return _serialize(scenario)


async def delete_scenario(session: AsyncSession, actor: CurrentUser, scenario_id: str) -> None:
    scenario = await _load(session, actor, scenario_id)
    await session.delete(scenario)
    await session.flush()
