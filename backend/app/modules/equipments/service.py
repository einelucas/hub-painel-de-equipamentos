from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.auth import CurrentUser
from app.core.errors import DomainError, NotFoundError
from app.core.scope import (
    allowed_unit_ids,
    assert_context_allowed,
    assert_equipment_allowed,
    restrict_to_units,
    user_can_access_unit,
)
from app.models.equipment import (
    STAGES,
    Area,
    Discipline,
    Equipment,
    EquipmentComponent,
    ProjectContext,
    WorkflowTransition,
    WorkPackage,
)
from app.models.user import User
from app.modules.equipments.schemas import (
    ComponentOut,
    EquipmentDetailOut,
    EquipmentListOut,
    EquipmentOut,
    NamedRefOut,
    PaginationOut,
    TransitionOut,
    UserRefOut,
)
from app.shared.audit import record_audit

_SORT_COLUMNS = {
    "name": Equipment.name,
    "currentStage": Equipment.current_stage,
    "startupAt": Equipment.startup_at,
    "updatedAt": Equipment.updated_at,
}


def _base_load_options() -> tuple[Any, ...]:
    return (
        joinedload(Equipment.project_context).joinedload(ProjectContext.unit),
        joinedload(Equipment.area),
        joinedload(Equipment.discipline),
        joinedload(Equipment.work_package),
        joinedload(Equipment.responsible_user),
    )


def _equipment_out(equipment: Equipment, components_count: int | None = None) -> EquipmentOut:
    context = equipment.project_context
    return EquipmentOut(
        id=equipment.id,
        name=equipment.name,
        origin=equipment.origin,
        startup_at=equipment.startup_at,
        criticality=equipment.criticality,
        current_stage=equipment.current_stage,
        stage_name=STAGES[equipment.current_stage],
        capex_estimated=equipment.capex_estimated,
        project_context=NamedRefOut(id=context.id, code=context.code, name=context.name),
        unit=NamedRefOut(id=context.unit.id, code=context.unit.code, name=context.unit.name),
        discipline=(
            NamedRefOut(
                id=equipment.discipline.id,
                code=equipment.discipline.code,
                name=equipment.discipline.name,
            )
            if equipment.discipline
            else None
        ),
        area=(NamedRefOut(id=equipment.area.id, name=equipment.area.name) if equipment.area else None),
        work_package=(
            NamedRefOut(
                id=equipment.work_package.id,
                code=equipment.work_package.code,
                name=equipment.work_package.name,
            )
            if equipment.work_package
            else None
        ),
        responsible_user=(
            UserRefOut(
                id=equipment.responsible_user.id,
                name=equipment.responsible_user.name,
                email=equipment.responsible_user.email,
            )
            if equipment.responsible_user
            else None
        ),
        components_count=(len(equipment.components) if components_count is None else components_count),
        created_at=equipment.created_at,
        updated_at=equipment.updated_at,
    )


async def _validate_relations(
    session: AsyncSession,
    *,
    project_context_id: str,
    area_id: str | None,
    discipline_id: str | None,
    work_package_id: str | None,
    responsible_user_id: str | None,
) -> ProjectContext:
    context = await session.get(ProjectContext, project_context_id)
    if context is None or not context.active:
        raise DomainError("Contexto de projeto inválido ou inativo")
    if area_id:
        area = await session.get(Area, area_id)
        if area is None or not area.active:
            raise DomainError("Área inválida ou inativa")
        if area.unit_id != context.unit_id:
            raise DomainError("A área deve pertencer à mesma unidade do contexto")
    if discipline_id:
        discipline = await session.get(Discipline, discipline_id)
        if discipline is None or not discipline.active:
            raise DomainError("Disciplina inválida ou inativa")
    if work_package_id:
        work_package = await session.get(WorkPackage, work_package_id)
        if work_package is None or not work_package.active:
            raise DomainError("Pacote de trabalho inválido ou inativo")
        if work_package.project_context_id != context.id:
            raise DomainError("O pacote de trabalho deve pertencer ao contexto informado")
    if responsible_user_id:
        user = await session.get(User, responsible_user_id)
        if user is None or not user.active:
            raise DomainError("Responsável inválido ou inativo")
        if not await user_can_access_unit(session, responsible_user_id, context.unit_id):
            raise DomainError("O responsável não tem acesso à unidade do equipamento")
    return context


def _apply_filters(
    stmt: Select[Any],
    *,
    allowed_units: set[str] | None,
    unit_id: str | None,
    project_context_id: str | None,
    equipment_id: str | None,
    search: str | None,
    stage: int | None,
    discipline_id: str | None,
    responsible_user_id: str | None,
) -> Select[Any]:
    # O join com o contexto é sempre necessário: é por ele que se chega à unidade.
    stmt = stmt.join(Equipment.project_context)
    stmt = restrict_to_units(stmt, allowed_units)
    if unit_id:
        stmt = stmt.where(ProjectContext.unit_id == unit_id)
    if project_context_id:
        stmt = stmt.where(Equipment.project_context_id == project_context_id)
    if equipment_id:
        stmt = stmt.where(Equipment.id == equipment_id)
    if search and search.strip():
        stmt = stmt.where(Equipment.name.ilike(f"%{search.strip()}%"))
    if stage is not None:
        stmt = stmt.where(Equipment.current_stage == stage)
    if discipline_id:
        stmt = stmt.where(Equipment.discipline_id == discipline_id)
    if responsible_user_id:
        stmt = stmt.where(Equipment.responsible_user_id == responsible_user_id)
    return stmt


async def list_equipments(
    session: AsyncSession,
    *,
    actor: CurrentUser,
    unit_id: str | None,
    project_context_id: str | None,
    equipment_id: str | None,
    search: str | None,
    stage: int | None,
    discipline_id: str | None,
    responsible_user_id: str | None,
    page: int,
    page_size: int,
    sort_by: str,
    sort_dir: str,
) -> EquipmentListOut:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    allowed_units = await allowed_unit_ids(session, actor)
    count_stmt = _apply_filters(
        select(func.count()).select_from(Equipment),
        allowed_units=allowed_units,
        unit_id=unit_id,
        project_context_id=project_context_id,
        equipment_id=equipment_id,
        search=search,
        stage=stage,
        discipline_id=discipline_id,
        responsible_user_id=responsible_user_id,
    )
    total = (await session.execute(count_stmt)).scalar_one()
    component_count = (
        select(func.count(EquipmentComponent.id))
        .where(EquipmentComponent.equipment_id == Equipment.id)
        .correlate(Equipment)
        .scalar_subquery()
    )
    stmt = _apply_filters(
        select(Equipment, component_count.label("components_count")),
        allowed_units=allowed_units,
        unit_id=unit_id,
        project_context_id=project_context_id,
        equipment_id=equipment_id,
        search=search,
        stage=stage,
        discipline_id=discipline_id,
        responsible_user_id=responsible_user_id,
    ).options(*_base_load_options())
    sort_column = _SORT_COLUMNS.get(sort_by, Equipment.name)
    stmt = stmt.order_by(desc(sort_column) if sort_dir == "desc" else asc(sort_column), Equipment.id.asc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(stmt)).all()
    return EquipmentListOut(
        items=[_equipment_out(item, count) for item, count in rows],
        pagination=PaginationOut(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size),
        ),
    )


async def create_equipment(
    session: AsyncSession, *, values: dict[str, Any], actor: CurrentUser
) -> EquipmentOut:
    await assert_context_allowed(session, actor, values["project_context_id"])
    await _validate_relations(
        session,
        project_context_id=values["project_context_id"],
        area_id=values.get("area_id"),
        discipline_id=values.get("discipline_id"),
        work_package_id=values.get("work_package_id"),
        responsible_user_id=values.get("responsible_user_id"),
    )
    equipment = Equipment(**values, current_stage=0)
    session.add(equipment)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="equipment.create",
        entity="Equipment",
        entity_id=equipment.id,
        new_data=_json_dict({**values, "current_stage": 0}),
    )
    await session.commit()
    return await get_equipment_out(session, equipment.id)


async def get_equipment_model(session: AsyncSession, equipment_id: str) -> Equipment:
    stmt = (
        select(Equipment)
        .where(Equipment.id == equipment_id)
        .options(
            *_base_load_options(),
            selectinload(Equipment.components),
            selectinload(Equipment.transitions).joinedload(WorkflowTransition.actor),
        )
    )
    equipment = (await session.execute(stmt)).scalar_one_or_none()
    if equipment is None:
        raise NotFoundError("Equipamento não encontrado")
    return equipment


async def get_equipment_out(session: AsyncSession, equipment_id: str) -> EquipmentOut:
    equipment = await get_equipment_model(session, equipment_id)
    return _equipment_out(equipment)


async def get_equipment_detail(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> EquipmentDetailOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    equipment = await get_equipment_model(session, equipment_id)
    return EquipmentDetailOut(
        equipment=_equipment_out(equipment),
        components=[ComponentOut.model_validate(item) for item in equipment.components],
        history=[
            TransitionOut(
                id=item.id,
                from_stage=item.from_stage,
                from_stage_name=STAGES[item.from_stage],
                to_stage=item.to_stage,
                to_stage_name=STAGES[item.to_stage],
                reason=item.reason,
                actor=(
                    UserRefOut(id=item.actor.id, name=item.actor.name, email=item.actor.email)
                    if item.actor
                    else None
                ),
                occurred_at=item.occurred_at,
            )
            for item in sorted(
                equipment.transitions,
                key=lambda transition: transition.occurred_at,
                reverse=True,
            )
        ],
    )


async def update_equipment(
    session: AsyncSession, *, equipment_id: str, changes: dict[str, Any], actor: CurrentUser
) -> EquipmentOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    equipment = await get_equipment_model(session, equipment_id)
    new_context = changes.get("project_context_id", equipment.project_context_id)
    if new_context != equipment.project_context_id:
        await assert_context_allowed(session, actor, new_context)
    await _validate_relations(
        session,
        project_context_id=new_context,
        area_id=changes.get("area_id", equipment.area_id),
        discipline_id=changes.get("discipline_id", equipment.discipline_id),
        work_package_id=changes.get("work_package_id", equipment.work_package_id),
        responsible_user_id=changes.get("responsible_user_id", equipment.responsible_user_id),
    )
    previous: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    for field, value in changes.items():
        old_value = getattr(equipment, field)
        if old_value != value:
            previous[field] = _json_value(old_value)
            changed[field] = _json_value(value)
            setattr(equipment, field, value)
    if changed:
        await record_audit(
            session,
            user_id=actor.id,
            action="equipment.update",
            entity="Equipment",
            entity_id=equipment.id,
            previous_data=previous,
            new_data=changed,
        )
    await session.commit()
    return await get_equipment_out(session, equipment.id)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def _json_dict(values: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_value(value) for key, value in values.items()}


async def list_components(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> list[EquipmentComponent]:
    await assert_equipment_allowed(session, actor, equipment_id)
    stmt = select(EquipmentComponent).where(EquipmentComponent.equipment_id == equipment_id).order_by(
        EquipmentComponent.name.asc()
    )
    return list((await session.execute(stmt)).scalars().all())


async def create_component(
    session: AsyncSession, *, equipment_id: str, values: dict[str, Any], actor: CurrentUser
) -> EquipmentComponent:
    await assert_equipment_allowed(session, actor, equipment_id)
    component = EquipmentComponent(equipment_id=equipment_id, **values)
    session.add(component)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="component.create",
        entity="EquipmentComponent",
        entity_id=component.id,
        new_data=_json_dict({"equipment_id": equipment_id, **values}),
    )
    await session.commit()
    await session.refresh(component)
    return component


async def update_component(
    session: AsyncSession, *, component_id: str, changes: dict[str, Any], actor: CurrentUser
) -> EquipmentComponent:
    component = await session.get(EquipmentComponent, component_id)
    if component is None:
        raise NotFoundError("Componente não encontrado")
    await assert_equipment_allowed(session, actor, component.equipment_id)
    previous: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    for field, value in changes.items():
        old_value = getattr(component, field)
        if old_value != value:
            previous[field] = _json_value(old_value)
            changed[field] = _json_value(value)
            setattr(component, field, value)
    if changed:
        await record_audit(
            session,
            user_id=actor.id,
            action="component.update",
            entity="EquipmentComponent",
            entity_id=component.id,
            previous_data=previous,
            new_data=changed,
        )
    await session.commit()
    await session.refresh(component)
    return component
