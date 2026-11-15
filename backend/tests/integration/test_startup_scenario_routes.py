"""Smoke REST do simulador: importação, recálculo, clone e isolamento do cadastro."""
from __future__ import annotations


async def test_startup_scenario_crud_and_formula(client, auth_header) -> None:
    headers = auth_header("ADMIN")
    unit_response = await client.post(
        "/api/v1/units", json={"code": "SIM-F2", "name": "Simulação F2"}, headers=headers,
    )
    assert unit_response.status_code == 201, unit_response.text
    unit = unit_response.json()
    context_response = await client.post(
        f"/api/v1/units/{unit['id']}/project-contexts",
        json={"code": "SIM-F2-OBRA", "name": "Obra teste startup"},
        headers=headers,
    )
    assert context_response.status_code == 201, context_response.text
    context = context_response.json()

    created = await client.post(
        "/api/v1/startup-scenarios",
        json={
            "projectContextId": context["id"],
            "name": "Startup 2027",
            "startupAt": "2027-12-02",
            "source": "EXCEL",
            "items": [{
                "name": "Estruturas Metálicas Indústria",
                "supplier": "METASA",
                "suppliesDays": 20,
                "legalDays": 20,
                "manufactureDays": 180,
                "preStartDays": 279,
            }],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    assert scenario["summary"]["equipments"] == 1
    assert scenario["items"][0]["deliveryDeadline"] == "2027-02-26"
    assert scenario["items"][0]["contractDeadline"] == "2026-08-30"
    assert scenario["items"][0]["negotiationDeadline"] == "2026-08-10"

    listing = await client.get(
        "/api/v1/startup-scenarios", params={"project_context_id": context["id"]},
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["items"]) == 1

    updated = await client.put(
        f"/api/v1/startup-scenarios/{scenario['id']}",
        json={
            "name": "Startup 2028", "startupAt": "2028-03-31",
            "items": [{
                "name": "Estruturas Metálicas Indústria",
                "suppliesDays": 20,
                "legalDays": 20,
                "manufactureDays": 180,
                "preStartDays": 279,
            }],
        }, headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["items"][0]["negotiationDeadline"] == "2026-12-08"

    clone = await client.post(
        f"/api/v1/startup-scenarios/{scenario['id']}/clone",
        json={"name": "Comparativo", "startupAt": "2027-12-02"},
        headers=headers,
    )
    assert clone.status_code == 201, clone.text
    assert clone.json()["items"][0]["negotiationDeadline"] == "2026-08-10"

    deleted = await client.delete(f"/api/v1/startup-scenarios/{scenario['id']}", headers=headers)
    assert deleted.status_code == 204, deleted.text
