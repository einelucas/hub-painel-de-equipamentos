"""Relações de prazo confirmadas nas 164 linhas, isoladas do workflow."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal


@dataclass(slots=True, frozen=True)
class ComponentSchedule:
    startup_at: date | None
    pre_start_days: int | None
    freight_days: int | None
    lead_time_days: int | None
    negotiation_buffer_days: int = 21
    blank_freight_days_default: int | None = 0


@dataclass(slots=True, frozen=True)
class CalculatedDeadlines:
    delivery_deadline: date | None
    collection_available_at: date | None
    contract_or_po_deadline: date | None
    negotiation_deadline: date | None


@dataclass(slots=True, frozen=True)
class ComponentDeadlineValues:
    lead_time_days: int | None = None
    pre_start_days: int | None = None
    freight_days: int | None = None
    delivery_deadline: date | None = None
    contract_or_po_deadline: date | None = None
    negotiation_deadline: date | None = None


@dataclass(slots=True, frozen=True)
class EquipmentDeadlineAggregates:
    max_lead_time_days: int | None
    max_pre_start_days: int | None
    max_freight_days: int | None
    min_delivery_deadline: date | None
    min_contract_or_po_deadline: date | None
    min_negotiation_deadline: date | None


def calculate_component_deadlines(schedule: ComponentSchedule) -> CalculatedDeadlines:
    """Cadeia observada: startup - antecedência - frete - fabricação - 21 dias."""
    delivery = (
        schedule.startup_at - timedelta(days=schedule.pre_start_days)
        if schedule.startup_at is not None and schedule.pre_start_days is not None
        else None
    )
    freight_days = (
        schedule.freight_days if schedule.freight_days is not None else schedule.blank_freight_days_default
    )
    collection = (
        delivery - timedelta(days=freight_days) if delivery is not None and freight_days is not None else None
    )
    contract = (
        collection - timedelta(days=schedule.lead_time_days)
        if collection is not None and schedule.lead_time_days is not None
        else None
    )
    negotiation = (
        contract - timedelta(days=schedule.negotiation_buffer_days) if contract is not None else None
    )
    return CalculatedDeadlines(delivery, collection, contract, negotiation)


def days_until(deadline: date, *, reference_date: date) -> int:
    """Nunca consulta o relógio do servidor; a data-base é obrigatória."""
    return (deadline - reference_date).days


def negotiation_status(
    *, negotiated_at: date | None, days_remaining: int
) -> Literal["CONCLUIDO", "ATRASADO", "PENDENTE_THRESHOLDS"]:
    if negotiated_at is not None:
        return "CONCLUIDO"
    if days_remaining < 0:
        return "ATRASADO"
    return "PENDENTE_THRESHOLDS"


def delivery_margin_days(*, delivery_deadline: date, contract_delivery_at: date) -> int:
    return (delivery_deadline - contract_delivery_at).days


def delivery_adherence_candidate(margin_days: int) -> Literal["ATENDE", "PENDENTE_VALIDACAO"]:
    """Somente margens positivas têm evidência suficiente no conjunto analisado."""
    return "ATENDE" if margin_days > 0 else "PENDENTE_VALIDACAO"


def _optional_max(values: Iterable[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _optional_min_date(values: Iterable[date | None]) -> date | None:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def aggregate_component_deadlines(
    components: Iterable[ComponentDeadlineValues],
) -> EquipmentDeadlineAggregates:
    items = list(components)
    return EquipmentDeadlineAggregates(
        max_lead_time_days=_optional_max(item.lead_time_days for item in items),
        max_pre_start_days=_optional_max(item.pre_start_days for item in items),
        max_freight_days=_optional_max(item.freight_days for item in items),
        min_delivery_deadline=_optional_min_date(item.delivery_deadline for item in items),
        min_contract_or_po_deadline=_optional_min_date(item.contract_or_po_deadline for item in items),
        min_negotiation_deadline=_optional_min_date(item.negotiation_deadline for item in items),
    )
