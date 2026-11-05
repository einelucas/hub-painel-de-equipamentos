"""Agregações para os gráficos ApexCharts do Dashboard Geral.

Somente leitura. Reutiliza exatamente o mesmo escopo e as funções de domínio
oficiais do /dashboard/summary, sem inferir dados faltantes da origem Monday.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.core.scope import allowed_unit_ids, assert_context_allowed, ensure_unit_allowed
from app.domain.equipment_calculations import WorkNeedStatus, calculate_work_need_status
from app.models.equipment import (
    STAGES,
    Discipline,
    EapNode,
    Equipment,
    ProjectContext,
    Unit,
    WorkflowTransition,
)
from app.models.process import PurchaseOrder
from app.modules.dashboard import services
from app.modules.dashboard.analytics_schemas import (
    DashboardAnalyticsOut,
    DeliveryWindowOut,
    DistributionItemOut,
    EapRiskItemOut,
    EapStageItemOut,
    MonthlyAmountOut,
    MonthlyCountOut,
    StageCapexOut,
    UpcomingStartupOut,
)

_CRITICAL = {
    WorkNeedStatus.CHECK_DELIVERY_FUP,
    WorkNeedStatus.NEEDED_TODAY,
    WorkNeedStatus.LT_30_DAYS,
}
_WARNING = {WorkNeedStatus.LT_60_DAYS, WorkNeedStatus.LT_90_DAYS}


def _last_12_months(today: date) -> list[str]:
    """Rótulos YYYY-MM estáveis, sem dependência de locale ou banco."""
    absolute_month = today.year * 12 + today.month - 1
    months = []
    for offset in range(11, -1, -1):
        index = absolute_month - offset
        year, month_index = divmod(index, 12)
        months.append(f"{year:04d}-{month_index + 1:02d}")
    return months


async def get_analytics(
    session: AsyncSession,
    *,
    actor: CurrentUser,
    unit_id: str | None,
    project_context_id: str | None,
    equipment_id: str | None,
    filters: services.DashboardFilters,
) -> DashboardAnalyticsOut:
    if project_context_id:
        await assert_context_allowed(session, actor, project_context_id)
    allowed = await allowed_unit_ids(session, actor)
    if unit_id:
        ensure_unit_allowed(allowed, unit_id)

    scope = services._scope(  # noqa: SLF001 - mesma fonte de verdade do summary
        unit_id, project_context_id, equipment_id, allowed, filters
    ).subquery()

    rows = (
        await session.execute(
            select(
                Equipment,
                Discipline.name,
                ProjectContext.name,
                Unit.name,
                EapNode.name,
                EapNode.code,
            )
            .join(scope, Equipment.id == scope.c.id)
            .join(ProjectContext, ProjectContext.id == Equipment.project_context_id)
            .join(Unit, Unit.id == ProjectContext.unit_id)
            .outerjoin(Discipline, Discipline.id == Equipment.discipline_id)
            .outerjoin(EapNode, EapNode.id == Equipment.eap_node_id)
        )
    ).all()

    discipline_counts: dict[tuple[str | None, str], int] = defaultdict(int)
    project_counts: dict[tuple[str, str], int] = defaultdict(int)
    eap_counts: dict[tuple[str | None, str], list[int]] = {}
    eap_names: dict[str | None, str] = {}
    capex_amounts: dict[int, Decimal] = defaultdict(Decimal)
    capex_informed: dict[int, int] = defaultdict(int)
    delivery_windows: list[DeliveryWindowOut] = []
    startups: list[UpcomingStartupOut] = []
    incomplete_delivery_windows = 0
    today = datetime.now(UTC).date()

    for equipment, discipline, project, unit, eap_name, eap_code in rows:
        discipline_counts[(equipment.discipline_id, discipline or "Sem disciplina")] += 1
        project_counts[(equipment.project_context_id, f"{unit} · {project}")] += 1
        eap_label = f"{eap_code} · {eap_name}" if eap_code else "Sem EAP"
        eap_key = (equipment.eap_node_id, eap_label)
        if eap_key not in eap_counts:
            eap_counts[eap_key] = [0] * 9
        eap_counts[eap_key][equipment.current_stage] += 1
        eap_names[equipment.eap_node_id] = eap_label

        if equipment.capex_estimated is not None:
            capex_amounts[equipment.current_stage] += equipment.capex_estimated
            capex_informed[equipment.current_stage] += 1

        start = equipment.contractual_delivery_start
        end = equipment.contractual_delivery_end
        if start and end and start <= end:
            if end >= today:
                delivery_windows.append(
                    DeliveryWindowOut(
                        equipment_id=equipment.id,
                        equipment_name=equipment.name,
                        start_at=start,
                        end_at=end,
                    )
                )
        elif start or end:
            incomplete_delivery_windows += 1

        if equipment.startup_at and equipment.startup_at >= today:
            startups.append(
                UpcomingStartupOut(
                    equipment_id=equipment.id,
                    equipment_name=equipment.name,
                    startup_at=equipment.startup_at,
                )
            )

    delivery_windows.sort(key=lambda row: (row.end_at, row.equipment_name))
    startups.sort(key=lambda row: (row.startup_at, row.equipment_name))

    # Exatamente a classificação do indicador Situação de prazos do summary.
    risk_counts: dict[str | None, dict[str, int]] = defaultdict(
        lambda: {"critical": 0, "warning": 0, "safe": 0, "not_calculable": 0}
    )
    for equipment in await services._load_scoped_equipments(session, scope):  # noqa: SLF001
        aggregates = services._component_deadline_aggregates(equipment)  # noqa: SLF001
        status = calculate_work_need_status(
            delivery_deadline=aggregates.min_delivery_deadline,
            reference_date=today,
        )
        bucket = (
            "critical" if status in _CRITICAL else
            "warning" if status in _WARNING else
            "safe" if status == WorkNeedStatus.SAFE else "not_calculable"
        )
        risk_counts[equipment.eap_node_id][bucket] += 1

    months = _last_12_months(today)
    month_set = set(months)
    purchase_totals: dict[str, Decimal] = defaultdict(Decimal)
    purchase_counts: dict[str, int] = defaultdict(int)
    purchase_informed: dict[str, int] = defaultdict(int)
    orders_without_date = 0
    orders_without_amount = 0
    purchase_orders = (
        await session.execute(
            select(PurchaseOrder)
            .join(scope, PurchaseOrder.equipment_id == scope.c.id)
            .where(PurchaseOrder.order_number.is_not(None))
        )
    ).scalars().all()
    for order in purchase_orders:
        if order.amount is None:
            orders_without_amount += 1
        if order.ordered_at is None:
            orders_without_date += 1
            continue
        month = order.ordered_at.isoformat()[:7]
        if month not in month_set:
            continue
        purchase_counts[month] += 1
        if order.amount is not None:
            purchase_totals[month] += order.amount
            purchase_informed[month] += 1

    movement_counts: dict[str, int] = defaultdict(int)
    transitions = (
        await session.execute(
            select(WorkflowTransition.occurred_at)
            .join(scope, WorkflowTransition.equipment_id == scope.c.id)
        )
    ).scalars().all()
    for occurred_at in transitions:
        month = occurred_at.strftime("%Y-%m")
        if month in month_set:
            movement_counts[month] += 1

    return DashboardAnalyticsOut(
        by_discipline=[
            DistributionItemOut(id=key[0], label=key[1], count=count)
            for key, count in sorted(
                discipline_counts.items(), key=lambda item: (-item[1], item[0][1])
            )
        ],
        by_project=[
            DistributionItemOut(id=key[0], label=key[1], count=count)
            for key, count in sorted(
                project_counts.items(), key=lambda item: (-item[1], item[0][1])
            )
        ],
        by_eap_stage=[
            EapStageItemOut(eap_id=key[0], label=key[1], counts=counts, total=sum(counts))
            for key, counts in sorted(
                eap_counts.items(), key=lambda item: (-sum(item[1]), item[0][1])
            )
        ],
        risk_by_eap=[
            EapRiskItemOut(eap_id=eap_id, label=eap_names.get(eap_id, "Sem EAP"), **counts)
            for eap_id, counts in sorted(
                risk_counts.items(), key=lambda item: (-sum(item[1].values()), eap_names.get(item[0], ""))
            )
        ],
        delivery_windows=delivery_windows[:20],
        upcoming_startups=startups[:10],
        incomplete_delivery_windows=incomplete_delivery_windows,
        monthly_purchase_orders=[
            MonthlyAmountOut(
                month=month, amount=purchase_totals[month], orders=purchase_counts[month],
                informed_orders=purchase_informed[month]
            )
            for month in months
        ],
        purchase_orders_without_date=orders_without_date,
        purchase_orders_without_amount=orders_without_amount,
        capex_by_stage=[
            StageCapexOut(
                stage=stage, label=name, amount=capex_amounts[stage], informed=capex_informed[stage]
            )
            for stage, name in STAGES.items()
        ],
        monthly_workflow_movements=[
            MonthlyCountOut(month=month, count=movement_counts[month]) for month in months
        ],
    )
