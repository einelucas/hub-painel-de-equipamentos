"""Planilha NMT Armazém 05 (Fase 0): colunas financeiras e de acompanhamento do Monday."""

from __future__ import annotations

from decimal import Decimal

from app.modules.monday_import.normalization import normalize_decimal, normalize_integer
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.plan import _capex_from_normalized, _purchase_order_amount
from tests.unit.monday_xlsx_fixture import build_xlsx

_HEADER = [
    "Name",
    "Subelementos",
    "A.Status",
    "0.Custo Previsto",
    "7.Numero OC",
    "7.Valor da OC",
    "Conferência",
    "Diferença Negociação",
    "Status de Prazo",
    "Pessoas",
]


def _workbook() -> bytes:
    return build_xlsx(
        [
            ["Equipamentos - NMT ARMAZÉM 05"],
            ["Fase 0 - Nova Demanda"],
            _HEADER,
            ["Carro Tripper", "Carro Tripper", "0.Nova demanda", 550000, None, 0, None, 47, None, None],
            [
                "Eletrocentro",
                "QNB, QDCA",
                "0.Nova demanda",
                "R$ 4.417.366,25",
                "OC-1",
                "R$ 1.234,56",
                "Validação Final",
                -3,
                "No prazo",
                "Ana, Bruno",
            ],
            ["Válvulas", None, "0.Nova demanda", "#REF!", None, "#N/A", None, "#DIV/0!", None, None],
        ]
    )


def test_all_columns_of_the_sheet_are_recognized() -> None:
    parsed = parse_monday_xlsx(_workbook(), source_name="nmt.xlsx")
    assert parsed.unknown_equipment_fields == set()
    assert [i.code for i in parsed.issues if i.severity == "error"] == []


def test_values_are_collected_per_column() -> None:
    first, second, third = parse_monday_xlsx(_workbook(), source_name="nmt.xlsx").equipments
    assert first.normalized["planned_cost_candidate"] == "550000"
    assert first.normalized["purchase_order_amount"] == "0"
    assert first.normalized["negotiation_difference_days_observed"] == 47
    assert second.normalized["planned_cost_candidate"] == "4417366.25"
    assert second.normalized["purchase_order_amount"] == "1234.56"
    assert second.normalized["review_status_observed"] == "Validação Final"
    assert second.normalized["negotiation_difference_days_observed"] == -3
    assert second.normalized["deadline_status_observed"] == "No prazo"
    assert second.normalized["people_observed"] == "Ana, Bruno"
    assert "capex_estimated" not in second.normalized
    # Erros de fórmula viram vazio, sem issue de erro.
    assert third.normalized["planned_cost_candidate"] is None
    assert third.normalized["purchase_order_amount"] is None
    assert third.normalized["negotiation_difference_days_observed"] is None


def test_formula_errors_and_brazilian_currency_normalization() -> None:
    assert normalize_decimal("R$ 1.234,56") == "1234.56"
    assert normalize_decimal("#REF!") is None
    assert normalize_decimal("") is None
    assert normalize_integer("#N/A") is None


def test_plan_helpers_use_planned_cost_as_capex_fallback_and_ignore_zero_amount() -> None:
    assert _capex_from_normalized({"planned_cost_candidate": "165000"}) == Decimal("165000")
    both = {"capex_estimated": "10", "planned_cost_candidate": "165000"}
    assert _capex_from_normalized(both) == Decimal("10")
    assert _capex_from_normalized({}) is None
    assert _purchase_order_amount({"purchase_order_amount": "0"}) is None
    assert _purchase_order_amount({"purchase_order_amount": "-5"}) is None
    assert _purchase_order_amount({"purchase_order_amount": "97500.00"}) == Decimal("97500.00")
