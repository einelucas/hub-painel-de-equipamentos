"""Agregações do painel.

Todas as contagens são calculadas no banco sobre o recorte (unidade/equipamento)
selecionado. Métricas sem fórmula oficial confirmada não são estimadas: elas
retornam estado explicitamente não calculável.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, Subquery, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.auth import CurrentUser
from app.core.scope import allowed_unit_ids, assert_unit_allowed, restrict_to_units
from app.domain.equipment_calculations import (
    NegotiationStatus,
    WorkNeedStatus,
    aggregate_component_deadlines,
    calculate_negotiation_status,
    calculate_work_need_status,
    component_deadline_values,
)
from app.models.equipment import STAGES, Equipment, EquipmentComponent, ProjectContext
from app.models.process import Negotiation, PurchaseOrder
from app.modules.dashboard.schemas import (
    DashboardContextOut,
    DashboardSummaryOut,
    DashboardTotalsOut,
    DeadlinesSummaryOut,
    NegotiationDeadlineStatusSummaryOut,
    NegotiationSummaryOut,
    StageDistributionOut,
    StartupSummaryOut,
)
from app.modules.workflow.stages import FINAL_STAGE

# Estágios em que o equipamento está sob negociação/equalização.
NEGOTIATION_STAGES = (1, 2)

_WORK_NEED_FIELD_BY_STATUS = {
    WorkNeedStatus.CHECK_DELIVERY_FUP: "check_delivery_fup",
    WorkNeedStatus.NEEDED_TODAY: "needed_today",
    WorkNeedStatus.LT_30_DAYS: "lt_30_days",
    WorkNeedStatus.LT_60_DAYS: "lt_60_days",
    WorkNeedStatus.LT_90_DAYS: "lt_90_days",
    WorkNeedStatus.SAFE: "safe",
}

# Widget do Monday "Status dos prazos de negociação": 5 categorias
# (Atrasado/Urgente/Próximo/No prazo/Concluído). CRITICAL/DUE_TODAY/URGENT
# — sub-estados do NegotiationStatus oficial (GAP-014) mais finos do que o
# widget — caem juntos em "urgent": nos 41 equipamentos reais do C2,
# CRITICAL e DUE_TODAY nunca ocorreram isoladamente (ver
# docs/validation/etapa-06c1-negotiation-deadline-status.md); essa fusão
# ainda depende de confirmação formal se o Monday algum dia distinguir os
# três na prática. NOT_APPLICABLE não tem bucket próprio no widget — cai em
# not_calculable, como `deliveryDeadline` ausente no card de prazos.
_NEGOTIATION_DEADLINE_FIELD_BY_STATUS = {
    NegotiationStatus.OVERDUE: "overdue",
    NegotiationStatus.DUE_TODAY: "urgent",
    NegotiationStatus.CRITICAL: "urgent",
    NegotiationStatus.URGENT: "urgent",
    NegotiationStatus.UPCOMING: "upcoming",
    NegotiationStatus.ON_TRACK: "on_track",
    NegotiationStatus.COMPLETED: "completed",
}


def _scope(
    unit_id: str | None, equipment_id: str | None, allowed: set[str] | None
) -> Select[tuple[str, int, date | None]]:
    """Recorte base: equipamentos visíveis no filtro atual e nas unidades autorizadas."""
    stmt = select(Equipment.id, Equipment.current_stage, Equipment.startup_at).join(
        Equipment.project_context
    )
    stmt = restrict_to_units(stmt, allowed)
    if unit_id:
        stmt = stmt.where(ProjectContext.unit_id == unit_id)
    if equipment_id:
        stmt = stmt.where(Equipment.id == equipment_id)
    return stmt


async def get_summary(
    session: AsyncSession, *, actor: CurrentUser, unit_id: str | None, equipment_id: str | None
) -> DashboardSummaryOut:
    if unit_id:
        await assert_unit_allowed(session, actor, unit_id)
    allowed = await allowed_unit_ids(session, actor)
    scope = _scope(unit_id, equipment_id, allowed).subquery()

    stage_rows = (
        await session.execute(
            select(scope.c.current_stage, func.count())
            .select_from(scope)
            .group_by(scope.c.current_stage)
        )
    ).all()
    counts: dict[int, int] = {stage: count for stage, count in stage_rows}
    total = sum(counts.values())
    completed = counts.get(FINAL_STAGE, 0)

    components = (
        await session.execute(
            select(func.count(EquipmentComponent.id)).join(
                scope, EquipmentComponent.equipment_id == scope.c.id
            )
        )
    ).scalar_one()

    capex = (
        await session.execute(
            select(func.coalesce(func.sum(Equipment.capex_estimated), 0)).join(
                scope, Equipment.id == scope.c.id
            )
        )
    ).scalar_one()

    order_count, order_amount = (
        await session.execute(
            select(
                func.count(PurchaseOrder.id),
                func.coalesce(func.sum(PurchaseOrder.amount), 0),
            )
            .join(scope, PurchaseOrder.equipment_id == scope.c.id)
            .where(PurchaseOrder.order_number.is_not(None))
        )
    ).one()

    negotiations_done = (
        await session.execute(
            select(func.count(Negotiation.id))
            .join(scope, Negotiation.equipment_id == scope.c.id)
            .where(Negotiation.negotiated_at.is_not(None))
        )
    ).scalar_one()

    startup = await _next_startup(session, scope)
    reference_date = datetime.now(UTC).date()
    scoped_equipments = await _load_scoped_equipments(session, scope)
    deadlines = _deadlines_summary(scoped_equipments, reference_date=reference_date)
    negotiation_deadline_status = _negotiation_deadline_status_summary(
        scoped_equipments, reference_date=reference_date
    )

    return DashboardSummaryOut(
        context=DashboardContextOut(unit_id=unit_id, equipment_id=equipment_id),
        totals=DashboardTotalsOut(
            equipments=total,
            components=components,
            in_progress=total - completed,
            completed=completed,
            purchase_orders=order_count,
            purchase_order_amount=Decimal(order_amount or 0),
            capex_estimated=Decimal(capex or 0),
        ),
        workflow=[
            StageDistributionOut(stage=stage, name=name, count=counts.get(stage, 0))
            for stage, name in STAGES.items()
        ],
        negotiation=NegotiationSummaryOut(
            open=total - negotiations_done,
            completed=negotiations_done,
            in_negotiation=sum(counts.get(stage, 0) for stage in NEGOTIATION_STAGES),
        ),
        deadlines=deadlines,
        negotiation_deadline_status=negotiation_deadline_status,
        startup=startup,
    )


async def _load_scoped_equipments(session: AsyncSession, scope: Subquery) -> Sequence[Equipment]:
    """Carrega uma vez só os equipamentos do recorte com tudo que as duas
    agregações de prazo (`_deadlines_summary` e
    `_negotiation_deadline_status_summary`) precisam — evita repetir a
    mesma consulta duas vezes por chamada de `/dashboard/summary`."""
    return (
        (
            await session.execute(
                select(Equipment)
                .join(scope, Equipment.id == scope.c.id)
                .options(selectinload(Equipment.components), joinedload(Equipment.negotiation))
            )
        )
        .unique()
        .scalars()
        .all()
    )


def _component_deadline_aggregates(equipment: Equipment):
    return aggregate_component_deadlines(
        component_deadline_values(
            startup_at=component.startup_at,
            pre_start_days=component.pre_start_days,
            freight_days=component.freight_days,
            lead_time_days=component.lead_time_days,
        )
        for component in equipment.components
    )


def _deadlines_summary(equipments: Sequence[Equipment], *, reference_date: date) -> DeadlinesSummaryOut:
    """Card "Situação de prazos" (Etapa 6C.1): distribui o recorte atual
    pelo Status Necessidade da Obra oficial. Mesma função de domínio do
    detalhe do equipamento (`calculate_work_need_status`) — nada é
    recalculado ou reclassificado aqui, só agregado por contagem."""
    counts = dict.fromkeys(_WORK_NEED_FIELD_BY_STATUS.values(), 0)
    without_deadline = 0
    for equipment in equipments:
        aggregates = _component_deadline_aggregates(equipment)
        status = calculate_work_need_status(
            delivery_deadline=aggregates.min_delivery_deadline, reference_date=reference_date
        )
        if status is None:
            without_deadline += 1
        else:
            counts[_WORK_NEED_FIELD_BY_STATUS[status]] += 1

    total = len(equipments)
    return DeadlinesSummaryOut(
        available=True,
        total=total,
        with_deadline=total - without_deadline,
        without_deadline=without_deadline,
        **counts,
    )


def _negotiation_deadline_status_summary(
    equipments: Sequence[Equipment], *, reference_date: date
) -> NegotiationDeadlineStatusSummaryOut:
    """Card "Status dos prazos de negociação": widget do Monday equivalente
    ao GAP-014, agregado por contagem sobre o recorte atual. Mesma função
    de domínio do detalhe do equipamento (`calculate_negotiation_status`,
    sobre `min(component.negotiationDeadline)` e `Negotiation.negotiated_at`)
    — nenhum threshold novo, só a agregação das 5 categorias do widget
    (ver `_NEGOTIATION_DEADLINE_FIELD_BY_STATUS`)."""
    counts = dict.fromkeys(_NEGOTIATION_DEADLINE_FIELD_BY_STATUS.values(), 0)
    not_calculable = 0
    for equipment in equipments:
        aggregates = _component_deadline_aggregates(equipment)
        negotiated_at = equipment.negotiation.negotiated_at if equipment.negotiation else None
        status = calculate_negotiation_status(
            negotiation_deadline=aggregates.min_negotiation_deadline,
            negotiated_at=negotiated_at,
            reference_date=reference_date,
        )
        field = _NEGOTIATION_DEADLINE_FIELD_BY_STATUS.get(status) if status is not None else None
        if field is None:
            not_calculable += 1
        else:
            counts[field] += 1

    return NegotiationDeadlineStatusSummaryOut(
        total=len(equipments), not_calculable=not_calculable, **counts
    )


async def _next_startup(session: AsyncSession, scope: Subquery) -> StartupSummaryOut:
    """Próxima startup futura do recorte.

    Regra explícita: menor `startup_at` maior ou igual a hoje (UTC). Datas
    passadas são ignoradas porque a startup já ocorreu; empates são resolvidos
    pelo nome do equipamento, para a resposta ser determinística.
    """
    today = datetime.now(UTC).date()
    row = (
        await session.execute(
            select(Equipment.id, Equipment.name, Equipment.startup_at)
            .join(scope, Equipment.id == scope.c.id)
            .where(Equipment.startup_at.is_not(None), Equipment.startup_at >= today)
            .order_by(Equipment.startup_at.asc(), Equipment.name.asc())
            .limit(1)
        )
    ).first()
    if row is None:
        return StartupSummaryOut(next_at=None, days_remaining=None)
    equipment_id, name, startup_at = row
    return StartupSummaryOut(
        next_at=startup_at,
        days_remaining=(startup_at - today).days,
        equipment_id=equipment_id,
        equipment_name=name,
    )
