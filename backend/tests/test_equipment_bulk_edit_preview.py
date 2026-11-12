"""Etapa 01 — semântica pura do diff (nenhum SQL ou PATCH)."""

from datetime import date

import pytest

from app.modules.equipments.bulk_edit_contracts import EquipmentCellChange
from app.modules.equipments.bulk_edit_preview import preview_equipment_changes


def _change(field, operation, value=None):
    return EquipmentCellChange(field=field, operation=operation, value=value)


def test_fill_empty_does_not_replace_nonempty_field():
    diffs = preview_equipment_changes(
        equipment_id="eq-1",
        current_values={"origin": "Monday"},
        changes=[_change("origin", "FILL_EMPTY", "Manual")],
    )
    assert diffs[0].proposed_value == "Monday"
    assert diffs[0].skipped_reason == "ALREADY_FILLED"


def test_clear_is_explicit_and_empty_is_not_patch():
    changes = [_change("origin", "CLEAR")]
    result = preview_equipment_changes(
        equipment_id="eq-1", current_values={"origin": "Monday"}, changes=changes
    )
    assert result[0].proposed_value is None
    assert result[0].skipped_reason is None


def test_wp_add_remove_replace_preview():
    for op, value, expected in (
        ("ADD", ["b"], ["a", "b"]),
        ("REMOVE", ["a"], []),
        ("REPLACE", ["c"], ["c"]),
        ("CLEAR", None, []),
    ):
        diff = preview_equipment_changes(
            equipment_id="eq-1",
            current_values={"work_package_ids": ["a"]},
            changes=[_change("work_package_ids", op, value)],
        )[0]
        assert diff.proposed_value == expected
        assert diff.previous_value == ["a"]


def test_unmodified_values_are_skipped_and_source_is_untouched():
    snapshot = {"startup_at": date(2027, 10, 27), "work_package_ids": ["a"]}
    diff = preview_equipment_changes(
        equipment_id="eq-1",
        current_values=snapshot,
        changes=[_change("startup_at", "SET", date(2027, 10, 27))],
    )[0]
    assert diff.skipped_reason == "UNCHANGED"
    assert snapshot == {"startup_at": date(2027, 10, 27), "work_package_ids": ["a"]}


def test_missing_snapshot_field_is_rejected_instead_of_assumed_empty():
    with pytest.raises(ValueError, match="Campo ausente"):
        preview_equipment_changes(
            equipment_id="eq-1",
            current_values={},
            changes=[_change("origin", "FILL_EMPTY", "Manual")],
        )


def test_bad_work_package_snapshot_is_rejected():
    with pytest.raises(ValueError, match="Snapshot inválido"):
        preview_equipment_changes(
            equipment_id="eq-1",
            current_values={"work_package_ids": "wp1"},
            changes=[_change("work_package_ids", "ADD", ["wp2"])],
        )


def test_fill_empty_accepts_whitespace_only_but_not_real_text():
    diff = preview_equipment_changes(
        equipment_id="eq-1",
        current_values={"origin": "   "},
        changes=[_change("origin", "FILL_EMPTY", "Manual")],
    )[0]
    assert diff.proposed_value == "Manual"
    assert diff.skipped_reason is None
