from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.modules.monday_import.calculations import ComponentSchedule, calculate_component_deadlines
from app.modules.monday_import.dry_run import merge_workbooks
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.reconciliation import C2_EXPECTED, count_records, reconcile_counts


def _parsed_date(values: dict, field: str) -> date | None:
    value = values.get(field)
    return date.fromisoformat(value) if isinstance(value, str) else None


def test_real_reference_exports_reconcile_when_available() -> None:
    references = Path(__file__).resolve().parents[3] / "references" / "monday_exports"
    files = sorted(references.glob("*.xlsx"))
    if not files:
        pytest.skip("exports reais são fixtures externas opcionais")

    parsed = [parse_monday_xlsx(path) for path in files]
    equipments, duplicate_count = merge_workbooks(parsed)
    report = reconcile_counts(count_records(equipments), C2_EXPECTED)

    assert duplicate_count > 0  # snapshots reais se sobrepõem
    assert report.matched, report.to_dict()


def test_real_reference_exports_confirm_all_component_deadlines() -> None:
    references = Path(__file__).resolve().parents[3] / "references" / "monday_exports"
    files = sorted(references.glob("*.xlsx"))
    if not files:
        pytest.skip("exports reais são fixtures externas opcionais")
    equipments, _ = merge_workbooks([parse_monday_xlsx(path) for path in files])

    checked = 0
    for equipment in equipments:
        for component in equipment.components:
            values = component.normalized
            calculated = calculate_component_deadlines(
                ComponentSchedule(
                    startup_at=_parsed_date(values, "startup_at"),
                    pre_start_days=values.get("pre_start_days"),
                    freight_days=values.get("freight_days"),
                    lead_time_days=values.get("lead_time_days"),
                )
            )
            assert calculated.delivery_deadline == _parsed_date(values, "delivery_deadline")
            assert calculated.collection_available_at == _parsed_date(values, "collection_available_at")
            assert calculated.contract_or_po_deadline == _parsed_date(values, "contract_or_po_deadline")
            assert calculated.negotiation_deadline == _parsed_date(values, "negotiation_deadline")
            checked += 1
    assert checked == 164


def test_real_reference_exports_confirm_all_parent_aggregations() -> None:
    references = Path(__file__).resolve().parents[3] / "references" / "monday_exports"
    files = sorted(references.glob("*.xlsx"))
    if not files:
        pytest.skip("exports reais são fixtures externas opcionais")
    equipments, _ = merge_workbooks([parse_monday_xlsx(path) for path in files])
    mappings = [
        ("lead_time_days_mirror", "lead_time_days", max),
        ("pre_start_days_mirror", "pre_start_days", max),
        ("freight_days_mirror", "freight_days", max),
        ("delivery_deadline", "delivery_deadline", min),
        ("contract_or_po_deadline", "contract_or_po_deadline", min),
        ("negotiation_deadline", "negotiation_deadline", min),
    ]
    for equipment in equipments:
        for parent_field, component_field, aggregate in mappings:
            values = [
                component.normalized[component_field]
                for component in equipment.components
                if component.normalized.get(component_field) is not None
            ]
            expected = aggregate(values) if values else None
            assert equipment.normalized.get(parent_field) == expected
    assert len(equipments) == 41
