"""Integração de cadastros exclusivos, prazos, permissão e exclusão do simulador."""
from __future__ import annotations


async def test_simulation_scope_and_scenarios_crud(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    # Os cadastros do simulador NÃO são unidades ou obras operacionais.
    empty = await client.get("/api/v1/startup-simulation-units", headers=admin)
    assert empty.status_code == 200, empty.text
    unit = await client.post(
        "/api/v1/startup-simulation-units", json={"name": "LEM Simulada"}, headers=admin,
    )
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]
    duplicate = await client.post(
        "/api/v1/startup-simulation-units", json={"name": "lem simulada"}, headers=admin,
    )
    assert duplicate.status_code == 409, duplicate.text

    project = await client.post(
        "/api/v1/startup-simulation-projects",
        params={"unit_id": unit_id}, json={"name": "LEM F2"},
        headers=admin,
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    assert project.json()["unitId"] == unit_id
    projects = await client.get(
        "/api/v1/startup-simulation-projects",
        params={"unit_id": unit_id}, headers=admin,
    )
    assert [p["name"] for p in projects.json()["items"]] == ["LEM F2"]

    other_unit = await client.post(
        "/api/v1/startup-simulation-units", json={"name": "Outra unidade SIM"}, headers=admin,
    )
    other_project = await client.post(
        "/api/v1/startup-simulation-projects",
        params={"unit_id": other_unit.json()["id"]}, json={"name": "LEM F2"},
        headers=admin,
    )
    assert other_project.status_code == 201

    created = await client.post(
        "/api/v1/startup-scenarios",
        json={
            "simulationProjectId": project_id,
            "name": "Startup 2027",
            "startupAt": "2027-12-02",
            "source": "EXCEL",
            "items": [{
                "name": "Estruturas Metálicas Indústria",
                "origin": "Importado",
                "discipline": "Metal Mecânica",
                "supplier": "METASA",
                "area": "Caldeira",
                "responsible": "Responsável teste",
                "suppliesDays": 20,
                "legalDays": 20,
                "manufactureDays": 180,
                "preStartDays": 279,
            }],
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    scenario = created.json()
    assert scenario["simulationProjectId"] == project_id
    assert scenario["items"][0]["origin"] == "Importado"
    assert scenario["items"][0]["discipline"] == "Metal Mecânica"
    assert scenario["items"][0]["supplier"] == "METASA"
    assert scenario["items"][0]["area"] == "Caldeira"
    assert scenario["items"][0]["responsible"] == "Responsável teste"
    assert scenario["items"][0]["deliveryDeadline"] == "2027-02-26"
    assert scenario["items"][0]["contractDeadline"] == "2026-08-30"
    assert scenario["items"][0]["negotiationDeadline"] == "2026-08-10"

    listing = await client.get(
        "/api/v1/startup-scenarios", params={"simulation_project_id": project_id},
        headers=admin,
    )
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["items"]) == 1
    other_listing = await client.get(
        "/api/v1/startup-scenarios",
        params={"simulation_project_id": other_project.json()["id"]}, headers=admin,
    )
    assert other_listing.json()["items"] == []

    missing = await client.get(
        "/api/v1/startup-scenarios",
        params={"simulation_project_id": "inexistente"}, headers=admin,
    )
    assert missing.status_code == 404

    viewer_write = await client.post(
        "/api/v1/startup-simulation-units", json={"name": "Proibida"},
        headers=auth_header("VIEWER"),
    )
    assert viewer_write.status_code == 403

    # Só se pode excluir obras/unidades sem simulações.
    occupied_project = await client.delete(
        f"/api/v1/startup-simulation-projects/{project_id}", headers=admin,
    )
    assert occupied_project.status_code == 409, occupied_project.text
    occupied_unit = await client.delete(
        f"/api/v1/startup-simulation-units/{unit_id}", headers=admin,
    )
    assert occupied_unit.status_code == 409

    updated = await client.put(
        f"/api/v1/startup-scenarios/{scenario['id']}",
        json={
            "name": "Startup 2028", "startupAt": "2028-03-31",
            "items": [{
                "name": "Estruturas Metálicas Indústria (revisada)",
                "origin": "Nacional",
                "discipline": "Elétrica",
                "supplier": "Novo fornecedor",
                "area": "Moagem",
                "responsible": "Outro responsável",
                "suppliesDays": 20,
                "legalDays": 20,
                "manufactureDays": 180,
                "preStartDays": 279,
            }],
        }, headers=admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["items"][0]["negotiationDeadline"] == "2026-12-08"
    assert updated.json()["items"][0]["name"] == "Estruturas Metálicas Indústria (revisada)"
    assert updated.json()["items"][0]["origin"] == "Nacional"
    assert updated.json()["items"][0]["discipline"] == "Elétrica"
    assert updated.json()["items"][0]["supplier"] == "Novo fornecedor"
    assert updated.json()["items"][0]["area"] == "Moagem"
    assert updated.json()["items"][0]["responsible"] == "Outro responsável"

    clone = await client.post(
        f"/api/v1/startup-scenarios/{scenario['id']}/clone",
        json={"name": "Comparativo", "startupAt": "2027-12-02"},
        headers=admin,
    )
    assert clone.status_code == 201, clone.text
    assert clone.json()["items"][0]["negotiationDeadline"] == "2026-08-10"

    deleted = await client.delete(f"/api/v1/startup-scenarios/{scenario['id']}", headers=admin)
    assert deleted.status_code == 204, deleted.text
    remaining = await client.get(
        "/api/v1/startup-scenarios", params={"simulation_project_id": project_id},
        headers=admin,
    )
    assert [s["id"] for s in remaining.json()["items"]] == [clone.json()["id"]]

    del_clone = await client.delete(
        f"/api/v1/startup-scenarios/{clone.json()['id']}", headers=admin,
    )
    assert del_clone.status_code == 204
    del_project = await client.delete(
        f"/api/v1/startup-simulation-projects/{project_id}", headers=admin,
    )
    assert del_project.status_code == 204
    del_unit = await client.delete(
        f"/api/v1/startup-simulation-units/{unit_id}", headers=admin,
    )
    assert del_unit.status_code == 204


async def test_manual_scenario_starts_empty(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit = (await client.post(
        "/api/v1/startup-simulation-units", json={"name": "Unidade Vazia SIM"}, headers=admin
    )).json()
    project = (await client.post(
        "/api/v1/startup-simulation-projects",
        params={"unit_id": unit["id"]}, json={"name": "Obra sem equipamentos"},
        headers=admin,
    )).json()
    created = await client.post(
        "/api/v1/startup-scenarios",
        json={
            "simulationProjectId": project["id"],
            "name": "Planejamento manual", "startupAt": "2028-03-31",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    assert created.json()["items"] == []
    assert created.json()["summary"]["equipments"] == 0
