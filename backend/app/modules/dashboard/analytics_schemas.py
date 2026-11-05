"""Contratos de leitura do Dashboard Geral 2.0.

As séries são agregações do recorte autorizado, não snapshots históricos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.shared.schema import CamelModel


class DistributionItemOut(CamelModel):
    id: str | None = None
    label: str
    count: int


class EapStageItemOut(CamelModel):
    eap_id: str | None = None
    label: str
    counts: list[int]
    total: int


class EapRiskItemOut(CamelModel):
    eap_id: str | None = None
    label: str
    critical: int
    warning: int
    safe: int
    not_calculable: int


class DeliveryWindowOut(CamelModel):
    equipment_id: str
    equipment_name: str
    start_at: date
    end_at: date


class UpcomingStartupOut(CamelModel):
    equipment_id: str
    equipment_name: str
    startup_at: date


class MonthlyAmountOut(CamelModel):
    month: str
    amount: Decimal
    orders: int
    informed_orders: int


class MonthlyCountOut(CamelModel):
    month: str
    count: int


class StageCapexOut(CamelModel):
    stage: int
    label: str
    amount: Decimal
    informed: int


class DashboardAnalyticsOut(CamelModel):
    by_discipline: list[DistributionItemOut]
    by_project: list[DistributionItemOut]
    by_eap_stage: list[EapStageItemOut]
    risk_by_eap: list[EapRiskItemOut]
    delivery_windows: list[DeliveryWindowOut]
    upcoming_startups: list[UpcomingStartupOut]
    incomplete_delivery_windows: int
    monthly_purchase_orders: list[MonthlyAmountOut]
    purchase_orders_without_date: int
    purchase_orders_without_amount: int
    capex_by_stage: list[StageCapexOut]
    monthly_workflow_movements: list[MonthlyCountOut]
