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
    """Etapa 6C.1: card "Situação de prazos" — distribuição do recorte atual
    pelo Status Necessidade da Obra oficial (`app.domain.equipment_calculations`,
    mesma função usada no detalhe do equipamento). `available=False` só
    sobra para um cenário técnico (nunca deveria acontecer em produção,
    mas o schema permanece pronto caso uma regra futura precise voltar a
    desligar o card)."""

    available: bool
    reason: str | None = None
    total: int = 0
    with_deadline: int = 0
    without_deadline: int = 0
    check_delivery_fup: int = 0
    needed_today: int = 0
    lt_30_days: int = 0
    lt_60_days: int = 0
    lt_90_days: int = 0
    safe: int = 0


class NegotiationDeadlineStatusSummaryOut(CamelModel):
    """Widget do Monday "Status dos prazos de negociação" — distribuição do
    recorte atual pelo `NegotiationStatus` oficial (GAP-014,
    `app.domain.equipment_calculations`, mesma função usada no detalhe do
    equipamento), agregado nas 5 categorias do widget: Atrasado/Urgente/
    Próximo/No prazo/Concluído. `CRITICAL`/`DUE_TODAY`/`URGENT` (sub-estados
    mais finos do enum) entram juntos em `urgent` — ver nota em
    `dashboard/service.py`. `notCalculable` conta equipamentos sem
    `negotiationDeadline` e sem `negotiatedAt` (nunca uma 6ª fatia do
    donut), o mesmo padrão de `DeadlinesSummaryOut.withoutDeadline`."""

    total: int = 0
    overdue: int = 0
    urgent: int = 0
    upcoming: int = 0
    on_track: int = 0
    completed: int = 0
    not_calculable: int = 0


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
    negotiation_deadline_status: NegotiationDeadlineStatusSummaryOut
    startup: StartupSummaryOut
