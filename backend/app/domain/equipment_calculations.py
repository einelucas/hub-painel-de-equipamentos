"""Fórmulas de prazo confirmadas empiricamente nas 164 linhas do C2 (ver
`docs/migration/monday-c2-mapping.md` e `docs/validation/etapa-06b-formulas-layout.md`).

Implementação única: tanto o importador Monday (`app/modules/monday_import`,
que usa isto só para validar a migração/reconciliação) quanto a aplicação
viva (`app/modules/equipments`) consomem exatamente estas funções — nenhuma
das duas reimplementa a conta.

Regra de NULL: nenhum resultado inventa zero quando falta um dado-base
obrigatório (startup, pré-start, lead time). A única exceção é
`blank_freight_days_default`, que já é o comportamento CONFIRMADO durante a
migração (frete em branco = 0 dias, validado contra as 164 linhas reais) —
não é uma regra nova. `blank_freight_days_default=None` desliga essa exceção
para quem precisar do modo estrito.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
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


def component_deadline_values(
    *,
    startup_at: date | None,
    pre_start_days: int | None,
    freight_days: int | None,
    lead_time_days: int | None,
) -> ComponentDeadlineValues:
    """Empacota `calculate_component_deadlines` num `ComponentDeadlineValues`
    pronto para `aggregate_component_deadlines`. Único ponto de conversão
    campos-base-do-componente -> prazos — usado por `equipments/service.py`
    (detalhe/listagem) e por `dashboard/service.py` (card "Situação de
    prazos"), para as duas telas nunca divergirem em como um componente vira
    prazo."""
    deadlines = calculate_component_deadlines(
        ComponentSchedule(
            startup_at=startup_at,
            pre_start_days=pre_start_days,
            freight_days=freight_days,
            lead_time_days=lead_time_days,
        )
    )
    return ComponentDeadlineValues(
        lead_time_days=lead_time_days,
        pre_start_days=pre_start_days,
        freight_days=freight_days,
        delivery_deadline=deadlines.delivery_deadline,
        contract_or_po_deadline=deadlines.contract_or_po_deadline,
        negotiation_deadline=deadlines.negotiation_deadline,
    )


def calculate_component_deadlines(schedule: ComponentSchedule) -> CalculatedDeadlines:
    """Cadeia observada: startup - antecedência - frete - fabricação - 21 dias.

    Cada etapa só é calculada se a etapa anterior E o dado-base dela
    existirem; caso contrário o resultado (e tudo que depende dele) é
    `None` — nunca um zero inventado.
    """
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


class NegotiationStatus(str, Enum):
    """GAP-014 — fórmula oficial recebida do Monday (A.Status +
    negociação). Valor estável de domínio; nunca os emojis/rótulos do
    Monday (`⚠️Em Saneamento` etc.) — esses só entram como INPUT em
    `operational_status`, nunca como output."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    DUE_TODAY = "DUE_TODAY"
    CRITICAL = "CRITICAL"
    URGENT = "URGENT"
    UPCOMING = "UPCOMING"
    ON_TRACK = "ON_TRACK"


# A.Status do Monday cujo valor implica "fora do fluxo normal de
# negociação" — comparação insensível a maiúsculas/acentos-de-emoji, já que
# a origem tem variações de grafia (ex.: "⚠️Em Saneamento").
_NOT_APPLICABLE_OPERATIONAL_STATUSES = {"cancelado", "em saneamento", "nao se aplica", "não se aplica"}
_LEADING_NON_WORD = re.compile(r"^[^\wÀ-ÿ]+")


def _normalize_operational_status(value: str) -> str:
    return _LEADING_NON_WORD.sub("", value).strip().lower()


def calculate_negotiation_status(
    *,
    negotiation_deadline: date | None,
    negotiated_at: date | None,
    reference_date: date,
    operational_status: str | None = None,
) -> NegotiationStatus | None:
    """Ordem de precedência é a regra — nunca reordenar:

    1. `operational_status` em CANCELADO/Em Saneamento/Não se Aplica ->
       `NOT_APPLICABLE`, mesmo que `negotiated_at` esteja preenchido.
    2. `negotiated_at` preenchido -> `COMPLETED`, mesmo que o prazo de
       negociação já esteja vencido.
    3. `negotiation_deadline` ausente -> `None` (nada para classificar).
    4. Caso contrário, classifica `negotiation_deadline - reference_date`
       pela tabela oficial (`< 0` ATRASADO ... `> 30` NO PRAZO).

    O Hub ainda não modela um campo equivalente ao A.Status do Monday
    (current_stage é uma state machine 0-8, não um status de negociação) —
    `operational_status` é opcional e, para os equipamentos reais do C2
    hoje, sempre `None`. Ver `docs/validation/etapa-06c-dates-negotiation-status.md`
    para a pendência de modelagem registrada.
    """
    if operational_status is not None:
        normalized = _normalize_operational_status(operational_status)
        if normalized in _NOT_APPLICABLE_OPERATIONAL_STATUSES:
            return NegotiationStatus.NOT_APPLICABLE

    if negotiated_at is not None:
        return NegotiationStatus.COMPLETED

    if negotiation_deadline is None:
        return None

    days_remaining = days_until(negotiation_deadline, reference_date=reference_date)
    if days_remaining < 0:
        return NegotiationStatus.OVERDUE
    if days_remaining == 0:
        return NegotiationStatus.DUE_TODAY
    if days_remaining <= 7:
        return NegotiationStatus.CRITICAL
    if days_remaining <= 15:
        return NegotiationStatus.URGENT
    if days_remaining <= 30:
        return NegotiationStatus.UPCOMING
    return NegotiationStatus.ON_TRACK


class WorkNeedStatus(str, Enum):
    """Etapa 6C.1 — fórmula oficial recebida do Monday ("Status
    Necessidade da Obra"). Data-base é `deliveryDeadline`
    (`F.Limite Entrega Obra`), já calculado em `aggregate_component_deadlines`
    — nenhuma fórmula nova de data, só a classificação por faixa de dias."""

    CHECK_DELIVERY_FUP = "CHECK_DELIVERY_FUP"
    NEEDED_TODAY = "NEEDED_TODAY"
    LT_30_DAYS = "LT_30_DAYS"
    LT_60_DAYS = "LT_60_DAYS"
    LT_90_DAYS = "LT_90_DAYS"
    SAFE = "SAFE"


def calculate_work_need_status(
    *, delivery_deadline: date | None, reference_date: date
) -> WorkNeedStatus | None:
    """`delivery_deadline is None` -> `None` (nunca classificado
    artificialmente). Caso contrário, classifica
    `delivery_deadline - reference_date` pela tabela oficial."""
    if delivery_deadline is None:
        return None
    days_remaining = days_until(delivery_deadline, reference_date=reference_date)
    if days_remaining < 0:
        return WorkNeedStatus.CHECK_DELIVERY_FUP
    if days_remaining == 0:
        return WorkNeedStatus.NEEDED_TODAY
    if days_remaining < 30:
        return WorkNeedStatus.LT_30_DAYS
    if days_remaining < 60:
        return WorkNeedStatus.LT_60_DAYS
    if days_remaining < 90:
        return WorkNeedStatus.LT_90_DAYS
    return WorkNeedStatus.SAFE


def delivery_margin_days(*, delivery_deadline: date, contract_delivery_at: date) -> int:
    return (delivery_deadline - contract_delivery_at).days


def delivery_adherence_candidate(margin_days: int) -> Literal["ATENDE", "PENDENTE_VALIDACAO"]:
    """Somente margens positivas têm evidência suficiente no conjunto
    analisado. Não usada pela API ainda nesta etapa — só o número
    (`deliveryMarginDays`) é exposto; a classificação categórica fica para
    quando houver confirmação formal adicional."""
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
    """Equipamento sem componentes, ou sem nenhum componente com o dado
    correspondente preenchido, devolve `None` no agregado — nunca 0/data
    arbitrária."""
    items = list(components)
    return EquipmentDeadlineAggregates(
        max_lead_time_days=_optional_max(item.lead_time_days for item in items),
        max_pre_start_days=_optional_max(item.pre_start_days for item in items),
        max_freight_days=_optional_max(item.freight_days for item in items),
        min_delivery_deadline=_optional_min_date(item.delivery_deadline for item in items),
        min_contract_or_po_deadline=_optional_min_date(item.contract_or_po_deadline for item in items),
        min_negotiation_deadline=_optional_min_date(item.negotiation_deadline for item in items),
    )
