"""Migration 0012: `equipment_component.name` VARCHAR(500), sem truncamento.

Dados sintéticos; sem banco.
"""

from __future__ import annotations

import pytest

from app.models.equipment import EquipmentComponent
from app.modules.monday_import.mappings import parent_name_ordinal_component_key
from app.modules.monday_import.plan import _fit_text_columns


def test_component_name_column_is_500_and_not_null() -> None:
    column = EquipmentComponent.__table__.columns["name"]
    assert column.type.length == 500
    assert column.nullable is False


@pytest.mark.parametrize("length", [200, 233, 500])
def test_component_name_up_to_500_is_kept_whole(length: int) -> None:
    name = ("Componente sintético " * 40)[:length]
    fitted, issues, blocking = _fit_text_columns(EquipmentComponent, {"name": name}, source_key="k")
    assert (blocking, issues) == (False, [])
    assert fitted["name"] == name and len(fitted["name"]) == length  # conteúdo integral


def test_component_name_over_500_blocks_instead_of_truncating() -> None:
    name = "X" * 501
    fitted, issues, blocking = _fit_text_columns(EquipmentComponent, {"name": name}, source_key="k")
    assert blocking is True
    assert [issue.code for issue in issues] == ["FIELD_TOO_LONG_REQUIRED"]
    assert fitted["name"] == name  # nunca truncado


def test_component_identity_uses_full_source_name_not_a_truncated_one() -> None:
    prefix = "P" * 200
    first = parent_name_ordinal_component_key("parent", prefix + " fim A", 1)
    second = parent_name_ordinal_component_key("parent", prefix + " fim B", 1)
    assert first != second  # diferença depois do caractere 200 continua distinguindo
    assert first == parent_name_ordinal_component_key("parent", prefix + " fim A", 1)  # estável


def test_reconciliation_does_not_flag_field_not_written_for_length() -> None:
    from app.modules.monday_import.domain_reconciliation import _compare

    long_number = "/".join(f"SC{n:05d}" for n in range(30))  # sintético, > 80
    assert _compare(None, long_number, max_length=80) == "NOT_COMPARABLE"
    assert _compare("SC00001", "SC00002", max_length=80) == "MISMATCH"  # divergência real continua
    assert _compare("SC00001", "SC00001", max_length=80) == "MATCH"
