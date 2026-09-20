from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.shared.schema import CamelModel


class StageDistributionOut(CamelModel):
    stage: int
    name: str
    count: int


class DashboardContextOut(CamelModel):
    unit_id: str | None
    equipment_id: str | None


class DashboardTotalsOut(CamelModel):
    equipments: int
    components: int
    in_progress: int
    completed: int
    purchase_orders: int
    purchase_order_amount: Decimal
    capex_estimated: Decimal


class NegotiationSummaryOut(CamelModel):
    """Contagens derivadas do estágio e de `negotiation`, sem fórmula inventada."""

    open: int
    completed: int
    in_negotiation: int


class DeadlinesSummaryOut(CamelModel):
    """As fórmulas oficiais de prazo não foram formalizadas; nada é estimado aqui."""

    available: bool
    reason: str | None = None


class StartupSummaryOut(CamelModel):
    next_at: date | None
    days_remaining: int | None
    equipment_id: str | None = None
    equipment_name: str | None = None


class DashboardSummaryOut(CamelModel):
    context: DashboardContextOut
    totals: DashboardTotalsOut
    workflow: list[StageDistributionOut]
    negotiation: NegotiationSummaryOut
    deadlines: DeadlinesSummaryOut
    startup: StartupSummaryOut
