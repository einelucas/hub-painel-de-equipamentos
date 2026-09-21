"""GAP-014 (Etapa 6C): contrato da API para `calculated.negotiationStatus`."""

from __future__ import annotations

from datetime import date, timedelta

from tests.integration.test_equipment_routes import _catalogs, _equipment


async def test_negotiation_status_is_null_without_deadline_or_negotiated_at(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "NEG0")
    created = await _equipment(client, auth_header, catalogs, "Sem prazo")
    assert created.json()["calculated"]["negotiationStatus"] is None


async def test_negotiation_status_becomes_completed_once_negotiated(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "NEG1")
    created = await _equipment(client, auth_header, catalogs, "Negociado")
    equipment_id = created.json()["id"]

    # Cria um componente com prazo já vencido para provar a precedência:
    # negotiatedAt deve vencer mesmo com negotiationDeadline atrasado.
    await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={
            "name": "C",
            "startupAt": (date.today() - timedelta(days=200)).isoformat(),
            "preStartDays": 1,
            "freightDays": 0,
            "leadTimeDays": 0,
        },
        headers=auth_header("ANALYST"),
    )
    before = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert before.json()["equipment"]["calculated"]["negotiationStatus"] == "OVERDUE"

    negotiated = await client.patch(
        f"/api/v1/equipments/{equipment_id}/negotiation",
        json={"negotiatedAt": "2026-01-01"},
        headers=auth_header("ANALYST"),
    )
    assert negotiated.status_code == 200

    after = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert after.json()["equipment"]["calculated"]["negotiationStatus"] == "COMPLETED"


async def test_negotiation_status_classifies_by_days_remaining(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "NEG2")
    created = await _equipment(client, auth_header, catalogs, "Classificado")
    equipment_id = created.json()["id"]

    # negotiation_deadline = startup - preStart - freight - leadTime - 21.
    # Escolhido para cair exatamente em CRITICAL (5 dias restantes).
    target_days_remaining = 5
    startup = date.today() + timedelta(days=21 + target_days_remaining)
    await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={
            "name": "C",
            "startupAt": startup.isoformat(),
            "preStartDays": 0,
            "freightDays": 0,
            "leadTimeDays": 0,
        },
        headers=auth_header("ANALYST"),
    )
    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    calculated = detail.json()["equipment"]["calculated"]
    assert calculated["negotiationDaysRemaining"] == target_days_remaining
    assert calculated["negotiationStatus"] == "CRITICAL"


async def test_negotiation_status_field_cannot_be_set_directly(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header, "NEG3")
    rejected = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Forjando status",
            "negotiationStatus": "ON_TRACK",
        },
        headers=auth_header("ANALYST"),
    )
    assert rejected.status_code == 422
