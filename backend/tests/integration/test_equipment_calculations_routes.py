"""FUN-001: contrato da API para os campos `calculated` de Equipment/Component."""

from __future__ import annotations

from datetime import date, timedelta

from tests.integration.test_equipment_routes import _catalogs, _equipment


async def test_equipment_without_components_has_all_calculated_fields_null(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "CALC0")
    created = await _equipment(client, auth_header, catalogs, "Sem componentes")
    body = created.json()["calculated"]
    assert body == {
        "maxLeadTimeDays": None,
        "maxPreStartDays": None,
        "maxFreightDays": None,
        "deliveryDeadline": None,
        "contractOrderDeadline": None,
        "negotiationDeadline": None,
        "negotiationDaysRemaining": None,
    }


async def test_component_calculated_fields_are_correct_and_independent_of_equipment_startup(
    client, auth_header
) -> None:
    catalogs = await _catalogs(client, auth_header, "CALC1")
    created = await _equipment(client, auth_header, catalogs, "Com componente")
    equipment_id = created.json()["id"]
    assert created.json()["startupAt"] is None

    component = await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={
            "name": "Motor",
            "startupAt": "2027-10-27",
            "preStartDays": 75,
            "freightDays": 5,
            "leadTimeDays": 145,
        },
        headers=auth_header("ANALYST"),
    )
    assert component.status_code == 201, component.text
    calculated = component.json()["calculated"]
    assert calculated["deliveryDeadline"] == "2027-08-13"
    assert calculated["availableForCollection"] == "2027-08-08"
    assert calculated["contractOrderDeadline"] == "2027-03-16"
    assert calculated["negotiationDeadline"] == "2027-02-23"


async def test_equipment_calculated_aggregates_use_max_and_min_across_components(
    client, auth_header
) -> None:
    catalogs = await _catalogs(client, auth_header, "CALC2")
    created = await _equipment(client, auth_header, catalogs, "Agregados")
    equipment_id = created.json()["id"]

    await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={"name": "A", "startupAt": "2027-10-27", "preStartDays": 75, "freightDays": 5, "leadTimeDays": 145},
        headers=auth_header("ANALYST"),
    )
    await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={"name": "B", "startupAt": "2027-06-01", "preStartDays": 30, "leadTimeDays": 200},
        headers=auth_header("ANALYST"),
    )

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    calculated = detail.json()["equipment"]["calculated"]
    assert calculated["maxLeadTimeDays"] == 200
    assert calculated["maxPreStartDays"] == 75
    assert calculated["maxFreightDays"] == 5
    # A e B têm delivery_deadline diferentes; o agregado deve ser o menor (MIN).
    a_delivery = date(2027, 8, 13)
    b_delivery = date(2027, 5, 2)  # 2027-06-01 - 30 dias
    assert calculated["deliveryDeadline"] == min(a_delivery, b_delivery).isoformat()


async def test_recalculates_after_editing_component_base_fields(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "CALC3")
    created = await _equipment(client, auth_header, catalogs, "Recalculo")
    equipment_id = created.json()["id"]
    component = (
        await client.post(
            f"/api/v1/equipments/{equipment_id}/components",
            json={"name": "C", "startupAt": "2027-10-27", "preStartDays": 75, "freightDays": 5, "leadTimeDays": 145},
            headers=auth_header("ANALYST"),
        )
    ).json()
    before = component["calculated"]["deliveryDeadline"]

    updated = await client.patch(
        f"/api/v1/components/{component['id']}",
        json={"preStartDays": 100},
        headers=auth_header("ANALYST"),
    )
    assert updated.status_code == 200
    after = updated.json()["calculated"]["deliveryDeadline"]
    assert after != before
    assert after == "2027-07-19"


async def test_calculated_fields_cannot_be_set_directly(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "CALC4")
    rejected_equipment = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Tentando forjar prazo",
            "deliveryDeadline": "2020-01-01",
        },
        headers=auth_header("ANALYST"),
    )
    assert rejected_equipment.status_code == 422

    created = await _equipment(client, auth_header, catalogs, "Base para componente")
    equipment_id = created.json()["id"]
    rejected_component = await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={"name": "Forjado", "negotiationDeadline": "2020-01-01"},
        headers=auth_header("ANALYST"),
    )
    assert rejected_component.status_code == 422


async def test_negotiation_days_remaining_is_dynamic_relative_to_today(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "CALC5")
    created = await _equipment(client, auth_header, catalogs, "Dinamico")
    equipment_id = created.json()["id"]
    future_startup = (date.today() + timedelta(days=400)).isoformat()
    component = (
        await client.post(
            f"/api/v1/equipments/{equipment_id}/components",
            json={
                "name": "D",
                "startupAt": future_startup,
                "preStartDays": 10,
                "freightDays": 0,
                "leadTimeDays": 0,
            },
            headers=auth_header("ANALYST"),
        )
    ).json()
    remaining = component["calculated"]["negotiationDaysRemaining"]
    assert remaining is not None
    assert remaining > 0
