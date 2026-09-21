"""FUN-001: fórmulas de prazo do domínio (`app.domain.equipment_calculations`).

Cobre os casos exigidos pela Etapa 6B: todos os inputs presentes, cada
input NULL isoladamente, valores zero, virada de mês/ano, ano bissexto,
equipamento sem componentes, equipamento com componentes parcialmente
preenchidos, MIN/MAX, e que o resultado muda quando o input muda
("recálculo após edição" — aqui simulado chamando a função de novo com o
novo valor, já que não há estado persistido para expirar).
"""

from __future__ import annotations

from datetime import date

from app.domain.equipment_calculations import (
    ComponentDeadlineValues,
    ComponentSchedule,
    aggregate_component_deadlines,
    calculate_component_deadlines,
    days_until,
    delivery_margin_days,
)


def _deadlines(**overrides: object) -> object:
    base = {
        "startup_at": date(2027, 10, 27),
        "pre_start_days": 75,
        "freight_days": 5,
        "lead_time_days": 145,
    }
    base.update(overrides)
    return calculate_component_deadlines(ComponentSchedule(**base))  # type: ignore[arg-type]


def test_all_inputs_present_produces_full_chain() -> None:
    result = _deadlines()
    assert result.delivery_deadline == date(2027, 8, 13)
    assert result.collection_available_at == date(2027, 8, 8)
    assert result.contract_or_po_deadline == date(2027, 3, 16)
    assert result.negotiation_deadline == date(2027, 2, 23)


def test_startup_null_makes_entire_chain_null() -> None:
    result = _deadlines(startup_at=None)
    assert result.delivery_deadline is None
    assert result.collection_available_at is None
    assert result.contract_or_po_deadline is None
    assert result.negotiation_deadline is None


def test_pre_start_days_null_makes_entire_chain_null() -> None:
    result = _deadlines(pre_start_days=None)
    assert result.delivery_deadline is None
    assert result.negotiation_deadline is None


def test_lead_time_days_null_stops_chain_at_collection() -> None:
    result = _deadlines(lead_time_days=None)
    assert result.delivery_deadline is not None
    assert result.collection_available_at is not None
    assert result.contract_or_po_deadline is None
    assert result.negotiation_deadline is None


def test_freight_days_null_defaults_to_zero_by_confirmed_migration_behavior() -> None:
    """Comportamento já confirmado durante a migração (não é regra nova)."""
    with_zero_explicit = _deadlines(freight_days=0)
    with_null = _deadlines(freight_days=None)
    assert with_null.collection_available_at == with_zero_explicit.collection_available_at


def test_freight_days_null_strict_mode_is_null_when_default_disabled() -> None:
    strict = calculate_component_deadlines(
        ComponentSchedule(
            startup_at=date(2027, 10, 27),
            pre_start_days=75,
            freight_days=None,
            lead_time_days=145,
            blank_freight_days_default=None,
        )
    )
    assert strict.collection_available_at is None
    assert strict.contract_or_po_deadline is None
    assert strict.negotiation_deadline is None


def test_zero_values_are_not_treated_as_missing() -> None:
    result = _deadlines(pre_start_days=0, freight_days=0, lead_time_days=0)
    assert result.delivery_deadline == date(2027, 10, 27)
    assert result.collection_available_at == date(2027, 10, 27)
    assert result.contract_or_po_deadline == date(2027, 10, 27)
    assert result.negotiation_deadline == date(2027, 10, 6)


def test_month_boundary_crossing() -> None:
    result = calculate_component_deadlines(
        ComponentSchedule(startup_at=date(2027, 3, 5), pre_start_days=10, freight_days=0, lead_time_days=0)
    )
    assert result.delivery_deadline == date(2027, 2, 23)


def test_year_boundary_crossing() -> None:
    result = calculate_component_deadlines(
        ComponentSchedule(startup_at=date(2027, 1, 5), pre_start_days=10, freight_days=0, lead_time_days=0)
    )
    assert result.delivery_deadline == date(2026, 12, 26)


def test_leap_year_february_29() -> None:
    # 2028 é bissexto.
    result = calculate_component_deadlines(
        ComponentSchedule(startup_at=date(2028, 3, 1), pre_start_days=1, freight_days=0, lead_time_days=0)
    )
    assert result.delivery_deadline == date(2028, 2, 29)


def test_equipment_without_components_aggregates_are_all_none() -> None:
    result = aggregate_component_deadlines([])
    assert result.max_lead_time_days is None
    assert result.max_pre_start_days is None
    assert result.max_freight_days is None
    assert result.min_delivery_deadline is None
    assert result.min_contract_or_po_deadline is None
    assert result.min_negotiation_deadline is None


def test_equipment_with_partially_filled_components_ignores_missing() -> None:
    result = aggregate_component_deadlines(
        [
            ComponentDeadlineValues(lead_time_days=100, delivery_deadline=date(2027, 5, 1)),
            ComponentDeadlineValues(lead_time_days=None, delivery_deadline=None),
            ComponentDeadlineValues(lead_time_days=50, delivery_deadline=date(2027, 4, 1)),
        ]
    )
    assert result.max_lead_time_days == 100
    assert result.min_delivery_deadline == date(2027, 4, 1)
    assert result.max_pre_start_days is None
    assert result.min_negotiation_deadline is None


def test_max_and_min_pick_correct_extremes_across_many_components() -> None:
    result = aggregate_component_deadlines(
        [
            ComponentDeadlineValues(freight_days=3, negotiation_deadline=date(2027, 6, 1)),
            ComponentDeadlineValues(freight_days=9, negotiation_deadline=date(2027, 1, 1)),
            ComponentDeadlineValues(freight_days=1, negotiation_deadline=date(2027, 12, 1)),
        ]
    )
    assert result.max_freight_days == 9
    assert result.min_negotiation_deadline == date(2027, 1, 1)


def test_recalculation_after_editing_a_base_field() -> None:
    """Não existe cache: chamar de novo com o campo-base editado já basta."""
    before = _deadlines(pre_start_days=75)
    after = _deadlines(pre_start_days=100)
    assert before.delivery_deadline != after.delivery_deadline
    assert after.delivery_deadline == date(2027, 7, 19)


def test_days_until_uses_explicit_reference_date_only() -> None:
    assert days_until(date(2026, 10, 16), reference_date=date(2026, 9, 21)) == 25
    assert days_until(date(2026, 9, 1), reference_date=date(2026, 9, 21)) == -20


def test_delivery_margin_days_positive_and_negative() -> None:
    assert delivery_margin_days(delivery_deadline=date(2027, 8, 28), contract_delivery_at=date(2027, 8, 20)) == 8
    assert delivery_margin_days(delivery_deadline=date(2027, 8, 10), contract_delivery_at=date(2027, 8, 20)) == -10
