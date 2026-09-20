from __future__ import annotations

from datetime import date

import pytest

from app.modules.monday_import.dry_run import build_dry_run_report
from app.modules.monday_import.normalization import (
    normalize_boolean,
    normalize_date,
    normalize_multi_value,
)
from app.modules.monday_import.parser import parse_monday_xlsx
from tests.unit.monday_xlsx_fixture import representative_xlsx


def test_identifies_equipment_subitems_and_preserves_unknown_raw_field() -> None:
    parsed = parse_monday_xlsx(representative_xlsx(), source_name="fixture.xlsx")

    assert parsed.board_title == "Equipamentos - Teste"
    assert len(parsed.equipments) == 1
    equipment = parsed.equipments[0]
    assert equipment.row_number == 5
    assert equipment.normalized["name"] == "Bomba principal"
    assert equipment.normalized["startup_at"] == "2027-10-27"
    assert equipment.normalized["work_package_codes"] == ["CAL012", "CIV014"]
    assert equipment.normalized["equalized"] is True
    assert equipment.raw["Coluna futura"] == "raw"
    assert parsed.unknown_equipment_fields == {"Coluna futura"}

    assert len(equipment.components) == 1
    component = equipment.components[0]
    assert component.row_number == 7
    assert component.normalized["name"] == "Motor"
    assert component.external_id == "123456"
    assert component.source_key == "monday-item-id:123456"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (46687, date(2027, 10, 27)),
        ("2027/10/27", date(2027, 10, 27)),
        ("2027-10-27", date(2027, 10, 27)),
        ("27/10/2027", date(2027, 10, 27)),
        ("", None),
        (None, None),
    ],
)
def test_normalizes_supported_dates(raw, expected) -> None:
    assert normalize_date(raw) == expected


@pytest.mark.parametrize("raw", ["v", "true", "TRUE", 1, "sim", "yes", "✓"])
def test_normalizes_checked_checkbox(raw) -> None:
    assert normalize_boolean(raw) is True


@pytest.mark.parametrize("raw", [None, "", "null"])
def test_normalizes_empty_checkbox_as_null(raw) -> None:
    assert normalize_boolean(raw) is None


def test_normalizes_multivalue_without_losing_raw_value() -> None:
    raw = "CAL012, CIV014; CIV015\nCIV012"
    assert normalize_multi_value(raw) == ["CAL012", "CIV014", "CIV015", "CIV012"]


def test_reports_duplicate_external_id() -> None:
    parsed = parse_monday_xlsx(representative_xlsx(duplicate_component=True))
    assert len(parsed.equipments[0].components) == 2
    assert any(issue.code == "duplicate_component_external_id" for issue in parsed.issues)


def test_dry_run_deduplicates_repeated_snapshot() -> None:
    first = parse_monday_xlsx(representative_xlsx(), source_name="first.xlsx")
    second = parse_monday_xlsx(representative_xlsx(), source_name="second.xlsx")
    report = build_dry_run_report([first, second])

    assert report.equipments == 1
    assert report.components == 1
    assert report.groups["Fase 0"].equipments == 1
    assert report.duplicate_records == 2
    assert report.errors == 0
