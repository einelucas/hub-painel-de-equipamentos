"""Agregações do painel.

Todas as contagens são calculadas no banco sobre o recorte (unidade/equipamento)
selecionado. Métricas sem fórmula oficial confirmada não são estimadas: elas
retornam estado explicitamente não calculável.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, Subquery, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipment import STAGES, Equipment, EquipmentComponent, ProjectContext
from app.models.process import Negotiation, PurchaseOrder
from app.modules.dashboard.schemas import (
    DashboardContextOut,
    DashboardSummaryOut,
    DashboardTotalsOut,
    DeadlinesSummaryOut,
    NegotiationSummaryOut,
    StageDistributionOut,
    StartupSummaryOut,
)
from app.modules.workflow.stages import FINAL_STAGE

DEADLINE_UNAVAILABLE_REASON = (
    "Regras oficiais de prazo ainda não formalizadas pelo negócio."
)

# Estágios em que o equipamento está sob negociação/equalização.
NEGOTIATION_STAGES = (1, 2)


def _scope(unit_id: str | None, equipment_id: str | None) -> Select[tuple[str, int, date | None]]:
    """Recorte base: ids/estágios dos equipamentos visíveis no filtro atual."""
    stmt = select(Equipment.id, Equipment.current_stage, Equipment.startup_at).join(
        Equipment.project_context
    )
    if unit_id:
        stmt = stmt.where(ProjectContext.unit_id == unit_id)
    if equipment_id:
        stmt = stmt.where(Equipment.id == equipment_id)
    return stmt


async def get_summary(
    session: AsyncSession, *, unit_id: str | None, equipment_id: str | None
) -> DashboardSummaryOut:
    scope = _scope(unit_id, equipment_id).subquery()

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
        deadlines=DeadlinesSummaryOut(available=False, reason=DEADLINE_UNAVAILABLE_REASON),
        startup=startup,
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
