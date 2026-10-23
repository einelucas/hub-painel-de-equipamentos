"""Invariantes do catálogo mestre sem acessar banco real."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.models.master_catalog import (
    MasterArea,
    MasterComponentOption,
    MasterEquipment,
    MasterEquipmentArea,
    MasterProjectCreation,
)
from app.modules.master_catalog.schemas import MasterCatalogSeedIn, MasterProjectCreateIn
from app.modules.master_catalog.services import _check_seed, key_for


def _seed() -> MasterCatalogSeedIn:
    return MasterCatalogSeedIn(
        schema_version="2.1",
        areas=[{"id": "area-a", "name": "Sem área definida", "is_unassigned_category": True}],
        equipments=[{
            "id": "eq-a", "name": "Equipamento Alfa", "area_ids": ["area-a"],
            "component_option_ids": ["co-a"], "review_flags": [],
        }],
        component_options=[{"id": "co-a", "equipment_id": "eq-a", "name": "Motor A"}],
    )


def test_catalog_models_do_not_expose_operational_metadata() -> None:
    forbidden = {"tag", "source_project", "project_context_id", "supplier_id", "eap_node_id"}
    for model in (MasterArea, MasterEquipment, MasterComponentOption):
        assert not forbidden.intersection(model.__table__.columns.keys())
    assert {c.name for c in MasterEquipmentArea.__table__.primary_key.columns} == {
        "equipment_id", "area_id",
    }
    assert "request_id" in MasterProjectCreation.__table__.columns


def test_name_normalization() -> None:
    assert key_for("  BÓMBAS   de Alimentação ") == "bombas de alimentacao"


def test_seed_rejects_unknown_references() -> None:
    seed = _seed()
    _check_seed(seed)
    seed.equipments[0]["area_ids"] = ["unknown"]
    with pytest.raises(DomainError):
        _check_seed(seed)


def test_seed_rejects_tag_fields() -> None:
    seed = _seed()
    seed.component_options[0]["tag"] = "A-123"
    with pytest.raises(DomainError):
        _check_seed(seed)


def test_duplicate_selections_rejected() -> None:
    data = {
        "requestId": "123456789",
        "unitId": "u-1",
        "name": "Obra nova",
        "selections": [
            {"equipmentId": "eq-a", "componentIds": ["co-a"]},
            {"equipmentId": "eq-a", "componentIds": []},
        ],
    }
    with pytest.raises(ValidationError):
        MasterProjectCreateIn.model_validate(data)


def test_components_can_be_empty_and_no_eap_copied() -> None:
    payload = MasterProjectCreateIn.model_validate({
        "requestId": "123456789",
        "unitId": "u-1",
        "name": "Obra nova",
        "selections": [{"equipmentId": "eq-a", "componentIds": []}],
    })
    assert payload.selections[0].component_ids == []
    assert "eap_node_id" not in payload.model_fields
