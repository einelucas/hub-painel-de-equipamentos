from __future__ import annotations

from datetime import date

import pytest

from app.modules.monday_import.calculations import (
    ComponentDeadlineValues,
    ComponentSchedule,
    aggregate_component_deadlines,
    calculate_component_deadlines,
    days_until,
    delivery_adherence_candidate,
    delivery_margin_days,
    negotiation_status,
)


def test_four_confirmed_deadline_relations() -> None:
    calculated = calculate_component_deadlines(
        ComponentSchedule(
            startup_at=date(2027, 10, 27),
            pre_start_days=75,
            freight_days=5,
            lead_time_days=145,
        )
    )
    assert calculated.delivery_deadline == date(2027, 8, 13)
    assert calculated.collection_available_at == date(2027, 8, 8)
    assert calculated.contract_or_po_deadline == date(2027, 3, 16)
    assert calculated.negotiation_deadline == date(2027, 2, 23)


def test_blank_freight_policy_is_explicit_and_parameterizable() -> None:
    observed = calculate_component_deadlines(
        ComponentSchedule(
            startup_at=date(2027, 10, 27),
            pre_start_days=60,
            freight_days=None,
            lead_time_days=90,
        )
    )
    strict = calculate_component_deadlines(
        ComponentSchedule(
            startup_at=date(2027, 10, 27),
            pre_start_days=60,
            freight_days=None,
            lead_time_days=90,
            blank_freight_days_default=None,
        )
    )
    assert observed.collection_available_at == observed.delivery_deadline
    assert strict.collection_available_at is None


def test_parent_aggregations_use_max_for_durations_and_min_for_dates() -> None:
    result = aggregate_component_deadlines(
        [
            ComponentDeadlineValues(
                lead_time_days=120,
                pre_start_days=90,
                freight_days=5,
                delivery_deadline=date(2027, 8, 1),
                contract_or_po_deadline=date(2027, 3, 1),
                negotiation_deadline=date(2027, 2, 8),
            ),
            ComponentDeadlineValues(
                lead_time_days=180,
                pre_start_days=120,
                freight_days=10,
                delivery_deadline=date(2027, 7, 1),
                contract_or_po_deadline=date(2027, 1, 1),
                negotiation_deadline=date(2026, 12, 11),
            ),
        ]
    )
    assert result.max_lead_time_days == 180
    assert result.max_pre_start_days == 120
    assert result.max_freight_days == 10
    assert result.min_delivery_deadline == date(2027, 7, 1)
    assert result.min_contract_or_po_deadline == date(2027, 1, 1)
    assert result.min_negotiation_deadline == date(2026, 12, 11)


def test_days_until_requires_explicit_reference_date() -> None:
    assert days_until(date(2026, 10, 16), reference_date=date(2026, 9, 21)) == 25


def test_only_confirmed_negotiation_status_boundaries_are_applied() -> None:
    assert negotiation_status(negotiated_at=date(2026, 8, 1), days_remaining=-67) == "CONCLUIDO"
    assert negotiation_status(negotiated_at=None, days_remaining=-67) == "ATRASADO"
    for observed_days in (10, 25, 30, 40):
        assert negotiation_status(negotiated_at=None, days_remaining=observed_days) == "PENDENTE_THRESHOLDS"


@pytest.mark.parametrize(("contract_date", "expected"), [(date(2027, 8, 20), 8)])
def test_positive_delivery_margin_is_the_only_confirmed_adherence(contract_date, expected) -> None:
    margin = delivery_margin_days(delivery_deadline=date(2027, 8, 28), contract_delivery_at=contract_date)
    assert margin == expected
    assert delivery_adherence_candidate(margin) == "ATENDE"
    assert delivery_adherence_candidate(-1) == "PENDENTE_VALIDACAO"
