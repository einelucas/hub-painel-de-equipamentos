"""Estrutura dos modelos/schemas da EAP, inspecionada sem banco."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index

from app.models.equipment import EapNode, Equipment, ProjectContext, ProjectEap, Unit
from app.modules.catalogs.schemas import (
    CatalogUpdateIn,
    EapNodeCreateIn,
    ProjectContextCreateIn,
    ProjectContextOut,
    ProjectContextUpdateIn,
    UnitCreateIn,
    UnitOut,
)


def _indexes(model) -> dict[str, Index]:
    return {index.name: index for index in model.__table__.indexes}


def _checks(model) -> set[str]:
    return {c.name for c in model.__table__.constraints if isinstance(c, CheckConstraint)}


def test_unit_has_no_numeric_code_and_keeps_code_as_acronym() -> None:
    table = Unit.__table__
    assert "numeric_code" not in table.c
    assert table.c.code.nullable is False
    assert not any("numeric_code" in (index.name or "") for index in table.indexes)
    assert "numeric_code" not in UnitOut.model_fields
    assert "numeric_code" not in UnitCreateIn.model_fields


def test_project_context_eap_prefix_is_optional_digits_only_and_not_globally_unique() -> None:
    table = ProjectContext.__table__
    assert table.c.eap_prefix.nullable is True
    assert "project_context_eap_prefix_check" in _checks(ProjectContext)
    assert not any(
        index.unique and [c.name for c in index.columns] == ["eap_prefix"] for index in table.indexes
    )
    assert "eap_prefix" in ProjectContextOut.model_fields


@pytest.mark.parametrize("prefix", ["23", "24", "03", "123"])
def test_project_context_create_accepts_numeric_prefixes(prefix: str) -> None:
    assert ProjectContextCreateIn(code="F1", name="Fase 1", eap_prefix=prefix).eap_prefix == prefix


def test_project_context_create_keeps_prefix_optional() -> None:
    assert ProjectContextCreateIn(code="C2", name="Caldeira 2").eap_prefix is None


@pytest.mark.parametrize("prefix", ["", "ABC", "23A", "23.A", "RDN", "-1", "2A"])
def test_project_context_create_rejects_non_numeric_prefixes(prefix: str) -> None:
    with pytest.raises(ValidationError):
        ProjectContextCreateIn(code="F1", name="Fase 1", eap_prefix=prefix)


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


def test_generic_catalog_update_does_not_change_eap_prefix() -> None:
    """Alteração futura será uma operação administrativa específica e auditada."""
    assert "eap_prefix" not in CatalogUpdateIn.model_fields


def test_eap_node_create_accepts_corporate_codes() -> None:
    assert EapNodeCreateIn(code="01", name="Geração de Vapor", level="PROCESS").parent_id is None
    area = EapNodeCreateIn(code="01.A", name="Caldeira", level="AREA", parent_id="p-1")
    assert area.level.value == "AREA"


@pytest.mark.parametrize(
    "payload",
    [
        {"code": "2301.A", "name": "Caldeira", "level": "AREA", "parent_id": "p-1"},
        {"code": "2408", "name": "Destilaria", "level": "PROCESS"},
        {"code": "01.A", "name": "Caldeira", "level": "AREA"},
        {"code": "I1", "name": "Ilha", "level": "ISLAND", "parent_id": "x"},
        {"code": "01", "name": "Algo", "level": "SUBAREA"},
    ],
)
def test_eap_node_create_rejects_invalid_payloads(payload: dict) -> None:
    with pytest.raises(ValidationError):
        EapNodeCreateIn(**payload)


@pytest.mark.parametrize("prefix", ["03", "21", "23", "24", "123"])
def test_project_context_update_accepts_digit_prefixes_as_text(prefix: str) -> None:
    body = ProjectContextUpdateIn(eap_prefix=prefix)
    assert body.model_dump(exclude_unset=True) == {"eap_prefix": prefix}


def test_project_context_update_preserves_leading_zero() -> None:
    assert ProjectContextUpdateIn.model_validate({"eapPrefix": "03"}).eap_prefix == "03"


def test_project_context_update_explicit_null_clears_and_omitted_keeps() -> None:
    cleared = ProjectContextUpdateIn.model_validate({"eapPrefix": None})
    assert cleared.model_dump(exclude_unset=True) == {"eap_prefix": None}
    renamed = ProjectContextUpdateIn.model_validate({"name": "Fase 2"})
    assert "eap_prefix" not in renamed.model_dump(exclude_unset=True)


@pytest.mark.parametrize("prefix", ["", "ABC", "23A", "23.A", "RDN", "-1", "2A", " 23", 23])
def test_project_context_update_rejects_invalid_prefixes(prefix: object) -> None:
    with pytest.raises(ValidationError):
        ProjectContextUpdateIn.model_validate({"eapPrefix": prefix})


def test_project_context_update_requires_some_field() -> None:
    with pytest.raises(ValidationError):
        ProjectContextUpdateIn.model_validate({})
