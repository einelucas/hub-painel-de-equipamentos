"""Etapa 01 — validações puras do contrato; sem acesso a banco."""

import pytest  # noqa: I001

from app.modules.equipments import bulk_edit_contracts


STAMP = "2026-11-12T13:00:00"


def _payload(field="disciplineId", operation="SET", value="disc-01"):
    return {
        "projectContextId": "project-01",
        "items": [{
            "equipmentId": "eq-01",
            "expectedUpdatedAt": STAMP,
            "changes": [{"field": field, "operation": operation, "value": value}],
        }],
    }


@pytest.mark.parametrize(
    "forbidden",
    ["name", "currentStage", "operationalStatus", "deliveryDeadline", "capexEstimated", "projectContextId"],
)
def test_forbidden_fields_are_rejected(forbidden):
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkPreviewIn.model_validate(_payload(field=forbidden))


def test_unknown_extra_properties_rejected():
    payload = _payload()
    payload["items"][0]["changes"][0]["transition"] = "go"
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkPreviewIn.model_validate(payload)


def test_expected_version_is_required():
    payload = _payload()
    del payload["items"][0]["expectedUpdatedAt"]
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkPreviewIn.model_validate(payload)


def test_duplicate_records_and_fields_rejected():
    payload = _payload()
    payload["items"].append(payload["items"][0].copy())
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkPreviewIn.model_validate(payload)
    payload = _payload()
    payload["items"][0]["changes"].append(payload["items"][0]["changes"][0].copy())
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkPreviewIn.model_validate(payload)


def test_wp_operation_is_explicit_and_preserves_multi_relation():
    change = bulk_edit_contracts.EquipmentCellChange.model_validate({
        "field": "workPackageIds", "operation": "ADD", "value": ["wp1", "wp2"]
    })
    assert change.value == ["wp1", "wp2"]
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentCellChange.model_validate({
            "field": "workPackageIds", "operation": "SET", "value": ["wp1"]
        })
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentCellChange.model_validate({
            "field": "workPackageIds", "operation": "ADD", "value": ["wp1", "wp1"]
        })


def test_clear_distinct_from_absent_and_fill_empty():
    cleared = bulk_edit_contracts.EquipmentCellChange(field="origin", operation="CLEAR")
    assert cleared.value is None
    filled = bulk_edit_contracts.EquipmentCellChange(
        field="origin", operation="FILL_EMPTY", value="Importado"
    )
    assert filled.value == "Importado"
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentCellChange(field="origin", operation="SET", value=None)


def test_startup_must_be_date_only():
    change = bulk_edit_contracts.EquipmentCellChange.model_validate({
        "field": "startupAt", "operation": "SET", "value": "2027-10-27"
    })
    assert change.value.isoformat() == "2027-10-27"
    for invalid in ("2027-10-27T18:00:00", "27/10/2027", "n/a"):
        with pytest.raises(ValueError):
            bulk_edit_contracts.EquipmentCellChange(field="startup_at", operation="SET", value=invalid)


def test_apply_requires_preview_and_idempotency_tokens():
    payload = _payload()
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkApplyIn.model_validate(payload)
    payload.update(previewToken="p" * 16, idempotencyKey="i" * 16)
    parsed = bulk_edit_contracts.EquipmentBulkApplyIn.model_validate(payload)
    assert parsed.items[0].expected_updated_at.isoformat() == STAMP


def test_max_batch_size_is_100():
    payload = _payload()
    original = payload["items"][0]
    payload["items"] = [dict(original, equipmentId=f"eq-{i}") for i in range(101)]
    with pytest.raises(ValueError):
        bulk_edit_contracts.EquipmentBulkPreviewIn.model_validate(payload)
