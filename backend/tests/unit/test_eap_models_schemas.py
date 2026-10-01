"""Estrutura dos modelos/schemas da EAP, inspecionada sem banco."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index

from app.models.equipment import EapNode, Equipment, ProjectEap, Unit
from app.modules.catalogs.schemas import CatalogUpdateIn, EapNodeCreateIn, UnitCreateIn, UnitOut


def _indexes(model) -> dict[str, Index]:
    return {index.name: index for index in model.__table__.indexes}


def _checks(model) -> set[str]:
    return {c.name for c in model.__table__.constraints if isinstance(c, CheckConstraint)}


def test_unit_numeric_code_is_optional_unique_when_filled_and_keeps_code() -> None:
    table = Unit.__table__
    assert table.c.numeric_code.nullable is True
    assert table.c.code.nullable is False
    index = _indexes(Unit)["unit_numeric_code_key"]
    assert index.unique is True
    assert index.dialect_options["postgresql"]["where"] is not None
    assert "unit_numeric_code_check" in _checks(Unit)


def test_eap_node_shape_hierarchy_and_unique_code() -> None:
    table = EapNode.__table__
    assert {"id", "code", "name", "level", "parent_id", "active", "created_at", "updated_at"} <= set(
        table.c.keys()
    )
    assert table.c.parent_id.nullable is True
    [fk] = table.c.parent_id.foreign_keys
    assert fk.column.table.name == "eap_node"
    assert _indexes(EapNode)["eap_node_code_key"].unique is True
    assert {"eap_node_level_check", "eap_node_code_check", "eap_node_not_self_parent_check"} <= _checks(
        EapNode
    )


def test_project_eap_is_unique_per_context_and_node() -> None:
    index = _indexes(ProjectEap)["project_eap_context_node_key"]
    assert index.unique is True
    assert [c.name for c in index.columns] == ["project_context_id", "eap_node_id"]


def test_equipment_keeps_area_id_and_gains_optional_eap_node_id() -> None:
    table = Equipment.__table__
    assert table.c.area_id.nullable is True
    assert table.c.eap_node_id.nullable is True
    [fk] = table.c.eap_node_id.foreign_keys
    assert fk.column.table.name == "eap_node"
    assert fk.ondelete == "SET NULL"
    assert "equipment_eap_node_id_idx" in _indexes(Equipment)


def test_unit_schemas_expose_and_validate_numeric_code() -> None:
    assert "numeric_code" in UnitOut.model_fields
    assert UnitCreateIn(code="RVD", name="Rio Verde", numeric_code="21").numeric_code == "21"
    assert UnitCreateIn(code="LEM", name="LEM").numeric_code is None
    assert UnitCreateIn(code="XYZ", name="Futura", numeric_code="123").numeric_code == "123"
    with pytest.raises(ValidationError):
        UnitCreateIn(code="RVD", name="Rio Verde", numeric_code="")
    with pytest.raises(ValidationError):
        UnitCreateIn(code="RVD", name="Rio Verde", numeric_code="2A")


def test_generic_catalog_update_does_not_change_numeric_code() -> None:
    """Alteração futura será uma operação administrativa específica e auditada."""
    assert "numeric_code" not in CatalogUpdateIn.model_fields


def test_eap_node_create_accepts_corporate_codes() -> None:
    assert EapNodeCreateIn(code="01", name="Geração de Vapor", level="PROCESS").parent_id is None
    area = EapNodeCreateIn(code="01.A", name="Caldeira", level="AREA", parent_id="p-1")
    assert area.level.value == "AREA"


@pytest.mark.parametrize(
    "payload",
    [
        {"code": "2101.A", "name": "Caldeira", "level": "AREA", "parent_id": "p-1"},
        {"code": "2108", "name": "Destilaria", "level": "PROCESS"},
        {"code": "01.A", "name": "Caldeira", "level": "AREA"},
        {"code": "I1", "name": "Ilha", "level": "ISLAND", "parent_id": "x"},
        {"code": "01", "name": "Algo", "level": "SUBAREA"},
    ],
)
def test_eap_node_create_rejects_invalid_payloads(payload: dict) -> None:
    with pytest.raises(ValidationError):
        EapNodeCreateIn(**payload)
