"""Compat: a lógica real mudou para `app.domain.equipment_calculations`
(Etapa 6B/FUN-001) — a mesma implementação passou a ser usada também pela
API viva (`app/modules/equipments`), então não existem mais duas contas
independentes da mesma fórmula. Este módulo só reexporta os nomes para não
quebrar os testes e imports já existentes do importador."""

from __future__ import annotations

from app.domain.equipment_calculations import (
    CalculatedDeadlines,
    ComponentDeadlineValues,
    ComponentSchedule,
    EquipmentDeadlineAggregates,
    NegotiationStatus,
    WorkNeedStatus,
    aggregate_component_deadlines,
    calculate_component_deadlines,
    calculate_negotiation_status,
    calculate_work_need_status,
    days_until,
    delivery_adherence_candidate,
    delivery_margin_days,
)

__all__ = [
    "CalculatedDeadlines",
    "ComponentDeadlineValues",
    "ComponentSchedule",
    "EquipmentDeadlineAggregates",
    "NegotiationStatus",
    "WorkNeedStatus",
    "aggregate_component_deadlines",
    "calculate_component_deadlines",
    "calculate_negotiation_status",
    "calculate_work_need_status",
    "days_until",
    "delivery_adherence_candidate",
    "delivery_margin_days",
]
