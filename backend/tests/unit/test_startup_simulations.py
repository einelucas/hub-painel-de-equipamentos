"""Testes de equivalência com a planilha Excel LEM F2 2027/2028."""
from __future__ import annotations

from datetime import date, timedelta

from app.modules.startup_simulations.calculations import calculate_dates, summarize


def test_planilha_linha_3_2027() -> None:
    result = calculate_dates(date(2027, 12, 2), 279, 180, 20)
    assert result.delivery == date(2027, 2, 26)
    assert result.contract == date(2026, 8, 30)
    assert result.negotiation == date(2026, 8, 10)


def test_adiamento_120_dias_e_equivalencia_de_formula() -> None:
    original = calculate_dates(date(2027, 12, 2), 279, 180, 20)
    shifted = calculate_dates(date(2028, 3, 31), 279, 180, 20)
    assert shifted.delivery == original.delivery + timedelta(days=120)
    assert shifted.contract == original.contract + timedelta(days=120)
    assert shifted.negotiation == original.negotiation + timedelta(days=120)


def test_suprimentos_nao_sao_descontados() -> None:
    # A coluna K não compõe as fórmulas G/H/I.
    result = calculate_dates(date(2028, 3, 31), 120, 90, 20)
    assert result.delivery == date(2027, 12, 2)
    assert result.contract == date(2027, 9, 3)
    assert result.negotiation == date(2027, 8, 14)


def test_prazos_ausentes_nao_inventam_datas() -> None:
    result = calculate_dates(date(2028, 3, 31), 120, None, 20)
    assert result.delivery == date(2027, 12, 2)
    assert result.contract is None
    assert result.negotiation is None


def test_todos_os_meses_contam_inclusive_o_primeiro() -> None:
    rows = [
        {"negotiation_deadline": date(2026, 4, 8), "contract_deadline": date(2026, 4, 28),
         "delivery_deadline": date(2026, 12, 2), "manufacture_days": 218, "pre_start_days": 365},
        {"negotiation_deadline": date(2027, 4, 1), "contract_deadline": date(2027, 4, 21),
         "delivery_deadline": date(2027, 8, 1), "manufacture_days": 102, "pre_start_days": 123},
    ]
    summary = summarize(rows)
    assert summary["equipments"] == 2
    assert sum(m["negotiations"] for m in summary["monthly"]) == 2
    assert summary["monthly"][0]["month"] == "2026-04"
    assert summary["first_negotiation"] == date(2026, 4, 8)
