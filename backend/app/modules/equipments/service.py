from __future__ import annotations

import math
from datetime import UTC, date, datetime
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
from app.domain.equipment_calculations import (
    ComponentDeadlineValues,
    ComponentSchedule,
    aggregate_component_deadlines,
    calculate_component_deadlines,
    calculate_negotiation_status,
    calculate_work_need_status,
    component_deadline_values,
    days_until,
    delivery_margin_days,
)
from app.models.equipment import (
    STAGES,
    Area,
    Discipline,
    Equipment,
    EquipmentComponent,
    EquipmentWorkPackage,
    ProjectContext,
    WorkflowTransition,
    WorkPackage,
)
from app.models.user import User
from app.modules.equipments.schemas import (
    ComponentCalculatedOut,
    ComponentOut,
    EquipmentCalculatedOut,
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
        selectinload(Equipment.work_package_links).joinedload(EquipmentWorkPackage.work_package),
        joinedload(Equipment.responsible_user),
        # Necessário para os agregados de FUN-001 (`EquipmentOut.calculated`),
        # que dependem dos prazos de cada componente. Volume pequeno por
        # equipamento — não é um N+1, é um único SELECT em lote (selectinload).
        selectinload(Equipment.components),
        # GAP-014: `negotiated_at` decide `negotiationStatus` (prioridade 2
        # da fórmula oficial), então precisa estar carregado junto.
        joinedload(Equipment.negotiation),
    )


def _reference_date() -> date:
    """Data-base dos prazos dinâmicos (ex.: dias restantes de negociação).
    Nunca persistida — recalculada a cada leitura, mesmo padrão já usado em
    `dashboard/service.py` (`_next_startup`)."""
    return datetime.now(UTC).date()


def _component_deadlines(component: EquipmentComponent) -> ComponentDeadlineValues:
    return component_deadline_values(
        startup_at=component.startup_at,
        pre_start_days=component.pre_start_days,
        freight_days=component.freight_days,
        lead_time_days=component.lead_time_days,
    )


def _component_calculated_out(component: EquipmentComponent, *, reference_date: date) -> ComponentCalculatedOut:
    deadlines = calculate_component_deadlines(
        ComponentSchedule(
            startup_at=component.startup_at,
            pre_start_days=component.pre_start_days,
            freight_days=component.freight_days,
            lead_time_days=component.lead_time_days,
        )
    )
    negotiation_days_remaining = (
        days_until(deadlines.negotiation_deadline, reference_date=reference_date)
        if deadlines.negotiation_deadline is not None
        else None
    )
    margin = (
        delivery_margin_days(
            delivery_deadline=deadlines.delivery_deadline,
            contract_delivery_at=component.contract_delivery_at,
        )
        if deadlines.delivery_deadline is not None and component.contract_delivery_at is not None
        else None
    )
    return ComponentCalculatedOut(
        delivery_deadline=deadlines.delivery_deadline,
        available_for_collection=deadlines.collection_available_at,
        contract_order_deadline=deadlines.contract_or_po_deadline,
        negotiation_deadline=deadlines.negotiation_deadline,
        negotiation_days_remaining=negotiation_days_remaining,
        delivery_margin_days=margin,
    )


def component_out(component: EquipmentComponent, *, reference_date: date | None = None) -> ComponentOut:
    """Único ponto de montagem de `ComponentOut` — garante que toda resposta
    (listar, criar, editar) traga `calculated` consistente."""
    ref = reference_date or _reference_date()
    return ComponentOut(
        id=component.id,
        equipment_id=component.equipment_id,
        name=component.name,
        tag=component.tag,
        startup_at=component.startup_at,
        sector=component.sector,
        lead_time_days=component.lead_time_days,
        pre_start_days=component.pre_start_days,
        contract_delivery_at=component.contract_delivery_at,
        freight_days=component.freight_days,
        calculated=_component_calculated_out(component, reference_date=ref),
        created_at=component.created_at,
        updated_at=component.updated_at,
    )


def _equipment_calculated_out(equipment: Equipment, *, reference_date: date) -> EquipmentCalculatedOut:
    aggregates = aggregate_component_deadlines(
        _component_deadlines(component) for component in equipment.components
    )
    negotiation_days_remaining = (
        days_until(aggregates.min_negotiation_deadline, reference_date=reference_date)
        if aggregates.min_negotiation_deadline is not None
        else None
    )
    negotiated_at = equipment.negotiation.negotiated_at if equipment.negotiation else None
    # `operational_status` fica de fora por enquanto: o Hub ainda não
    # modela um campo equivalente ao A.Status do Monday (ver GAP-014 em
    # docs/validation/etapa-06c-dates-negotiation-status.md) — nenhum
    # equipamento real do C2 hoje passa por essa prioridade da fórmula.
    negotiation_status = calculate_negotiation_status(
        negotiation_deadline=aggregates.min_negotiation_deadline,
        negotiated_at=negotiated_at,
        reference_date=reference_date,
    )
    work_need_days_remaining = (
        days_until(aggregates.min_delivery_deadline, reference_date=reference_date)
        if aggregates.min_delivery_deadline is not None
        else None
    )
    work_need_status = calculate_work_need_status(
        delivery_deadline=aggregates.min_delivery_deadline, reference_date=reference_date
    )
    return EquipmentCalculatedOut(
        max_lead_time_days=aggregates.max_lead_time_days,
        max_pre_start_days=aggregates.max_pre_start_days,
        max_freight_days=aggregates.max_freight_days,
        delivery_deadline=aggregates.min_delivery_deadline,
        contract_order_deadline=aggregates.min_contract_or_po_deadline,
        negotiation_deadline=aggregates.min_negotiation_deadline,
        negotiation_days_remaining=negotiation_days_remaining,
        work_need_days_remaining=work_need_days_remaining,
        work_need_status=work_need_status,
        negotiation_status=negotiation_status,
    )


def _equipment_out(equipment: Equipment, components_count: int | None = None) -> EquipmentOut:
    context = equipment.project_context
    reference_date = _reference_date()
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
        work_packages=[
            NamedRefOut(id=link.work_package.id, code=link.work_package.code, name=link.work_package.name)
            for link in sorted(equipment.work_package_links, key=lambda item: item.work_package.code)
        ],
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
        calculated=_equipment_calculated_out(equipment, reference_date=reference_date),
        created_at=equipment.created_at,
        updated_at=equipment.updated_at,
    )


async def _validate_relations(
    session: AsyncSession,
    *,
    project_context_id: str,
    area_id: str | None,
    discipline_id: str | None,
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
    if responsible_user_id:
        user = await session.get(User, responsible_user_id)
        if user is None or not user.active:
            raise DomainError("Responsável inválido ou inativo")
        if not await user_can_access_unit(session, responsible_user_id, context.unit_id):
            raise DomainError("O responsável não tem acesso à unidade do equipamento")
    return context


async def _validate_work_packages(
    session: AsyncSession, *, project_context_id: str, work_package_ids: list[str]
) -> None:
    """Cada ID deve existir, estar ativo e pertencer ao mesmo ProjectContext
    do Equipment. Duplicatas já são rejeitadas no schema (nível de request);
    aqui é o nível que só o banco sabe responder."""
    if not work_package_ids:
        return
    rows = (
        await session.execute(select(WorkPackage).where(WorkPackage.id.in_(work_package_ids)))
    ).scalars().all()
    found = {row.id: row for row in rows}
    for work_package_id in work_package_ids:
        work_package = found.get(work_package_id)
        if work_package is None or not work_package.active:
            raise DomainError(f"Pacote de trabalho inválido ou inativo: {work_package_id}")
        if work_package.project_context_id != project_context_id:
            raise DomainError(
                f"O pacote de trabalho {work_package_id} pertence a outro contexto de projeto"
            )


async def _sync_work_packages(
    session: AsyncSession, *, equipment: Equipment, work_package_ids: list[str]
) -> tuple[list[str], list[str]]:
    """Sincroniza `equipment_work_package` para o conjunto exato informado.
    Não apaga registros do catálogo `WorkPackage`, só os vínculos. Devolve
    (ids anteriores, ids novos) ordenados, para auditoria determinística."""
    existing_links = {link.work_package_id: link for link in equipment.work_package_links}
    previous_ids = sorted(existing_links)
    wanted = set(work_package_ids)
    for work_package_id, link in existing_links.items():
        if work_package_id not in wanted:
            await session.delete(link)
    for work_package_id in wanted - set(existing_links):
        session.add(EquipmentWorkPackage(equipment_id=equipment.id, work_package_id=work_package_id))
    return previous_ids, sorted(wanted)


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
    work_package_ids = sorted(set(values.pop("work_package_ids", None) or []))
    await _validate_relations(
        session,
        project_context_id=values["project_context_id"],
        area_id=values.get("area_id"),
        discipline_id=values.get("discipline_id"),
        responsible_user_id=values.get("responsible_user_id"),
    )
    await _validate_work_packages(
        session, project_context_id=values["project_context_id"], work_package_ids=work_package_ids
    )
    equipment = Equipment(**values, current_stage=0)
    session.add(equipment)
    await session.flush()
    for work_package_id in work_package_ids:
        session.add(EquipmentWorkPackage(equipment_id=equipment.id, work_package_id=work_package_id))
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="equipment.create",
        entity="Equipment",
        entity_id=equipment.id,
        new_data=_json_dict({**values, "current_stage": 0, "work_package_ids": work_package_ids}),
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
        components=[component_out(item) for item in equipment.components],
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

    # Ausente no PATCH (chave fora de `changes`) -> vínculos não são tocados.
    # `[]` explícito -> `work_package_ids_provided` é True e o conjunto some.
    work_package_ids_provided = "work_package_ids" in changes
    new_work_package_ids = (
        sorted(set(changes.pop("work_package_ids", None) or [])) if work_package_ids_provided else None
    )

    await _validate_relations(
        session,
        project_context_id=new_context,
        area_id=changes.get("area_id", equipment.area_id),
        discipline_id=changes.get("discipline_id", equipment.discipline_id),
        responsible_user_id=changes.get("responsible_user_id", equipment.responsible_user_id),
    )
    if work_package_ids_provided:
        assert new_work_package_ids is not None
        await _validate_work_packages(
            session, project_context_id=new_context, work_package_ids=new_work_package_ids
        )

    previous: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    for field, value in changes.items():
        old_value = getattr(equipment, field)
        if old_value != value:
            previous[field] = _json_value(old_value)
            changed[field] = _json_value(value)
            setattr(equipment, field, value)

    if work_package_ids_provided:
        assert new_work_package_ids is not None
        previous_ids, new_ids = await _sync_work_packages(
            session, equipment=equipment, work_package_ids=new_work_package_ids
        )
        if previous_ids != new_ids:
            previous["work_package_ids"] = previous_ids
            changed["work_package_ids"] = new_ids

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
    if work_package_ids_provided:
        # GAP-001: `expire_on_commit=False` + `work_package_links` já carregada
        # por `get_equipment_model` no início desta função significam que o
        # SQLAlchemy não recarrega essa coleção sozinho — sem isto, a resposta
        # deste PATCH devolveria os vínculos de ANTES da sincronização, mesmo
        # com o banco já correto (confirmado por teste de regressão). Expirar
        # a coleção força `get_equipment_out` (abaixo) a recarregá-la de fato
        # via o `selectinload` de `get_equipment_model`.
        session.expire(equipment, ["work_package_links"])
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
