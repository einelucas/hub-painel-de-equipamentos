"""Exclusão física de catálogos: permitida só sem vínculos operacionais.

Dados 100% sintéticos. A rota DELETE é administrativa (catalogs:manage).
"""

from __future__ import annotations

from sqlalchemy import select

from app.models.equipment import ProjectEap
from app.models.master_catalog import MasterArea, MasterProjectCreation


async def _catalogs(client, auth_header, suffix: str = "DEL") -> dict[str, str]:
    admin = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units", json={"code": f"U-{suffix}", "name": f"Unidade {suffix}"}, headers=admin
        )
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"code": f"P-{suffix}", "name": f"Obra {suffix}"},
            headers=admin,
        )
    ).json()
    area = (
        await client.post(
            "/api/v1/areas", json={"unitId": unit["id"], "name": f"Área {suffix}"}, headers=admin
        )
    ).json()
    discipline = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": f"D-{suffix}", "name": f"Disciplina {suffix}"},
            headers=admin,
        )
    ).json()
    label = (
        await client.post(
            "/api/v1/criticality-labels",
            json={"name": f"Criticidade {suffix}", "color": "#cc3344"},
            headers=admin,
        )
    ).json()
    work_package = (
        await client.post(
            "/api/v1/work-packages",
            json={"code": f"WP-{suffix}", "name": f"Pacote {suffix}"},
            headers=admin,
        )
    ).json()
    return {
        "unit": unit["id"],
        "context": context["id"],
        "area": area["id"],
        "discipline": discipline["id"],
        "label": label["id"],
        "work_package": work_package["id"],
    }


async def _eap(client, auth_header, process_code: str = "90") -> dict[str, str]:
    admin = auth_header("ADMIN")
    island = (
        await client.post(
            "/api/v1/eap-nodes",
            json={"code": f"I{process_code}", "name": f"Ilha {process_code}", "level": "ISLAND"},
            headers=admin,
        )
    ).json()
    process = (
        await client.post(
            "/api/v1/eap-nodes",
            json={
                "code": process_code,
                "name": f"Processo {process_code}",
                "level": "PROCESS",
                "parentId": island["id"],
            },
            headers=admin,
        )
    ).json()
    area = (
        await client.post(
            "/api/v1/eap-nodes",
            json={
                "code": f"{process_code}.A",
                "name": f"Área EAP {process_code}",
                "level": "AREA",
                "parentId": process["id"],
            },
            headers=admin,
        )
    ).json()
    return {"island": island["id"], "process": process["id"], "area": area["id"]}


async def test_admin_deletes_unused_catalog_items(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    ids = await _catalogs(client, auth_header, "UNUSED")
    eap = await _eap(client, auth_header, "90")

    # Vínculos que pertencem à própria obra (EAP e idempotência do Catálogo
    # Mestre) não devem impedir a exclusão.
    db_session.add_all(
        [
            ProjectEap(project_context_id=ids["context"], eap_node_id=eap["process"]),
            MasterProjectCreation(
                request_id="del-unused", project_context_id=ids["context"], actor_id="test"
            ),
        ]
    )
    await db_session.commit()

    for path in (
        f"/project-contexts/{ids['context']}",
        f"/areas/{ids['area']}",
        f"/disciplines/{ids['discipline']}",
        f"/criticality-labels/{ids['label']}",
        f"/work-packages/{ids['work_package']}",
        f"/eap-nodes/{eap['area']}",
        f"/eap-nodes/{eap['process']}",
        f"/eap-nodes/{eap['island']}",
        f"/units/{ids['unit']}",
    ):
        response = await client.delete(f"/api/v1{path}", headers=admin)
        assert response.status_code == 204, (path, response.text)

    remaining_links = (
        (await db_session.execute(select(ProjectEap).where(ProjectEap.project_context_id == ids["context"])))
        .scalars()
        .all()
    )
    assert remaining_links == []
    remaining_idempotency = (
        await db_session.execute(
            select(MasterProjectCreation).where(MasterProjectCreation.request_id == "del-unused")
        )
    ).scalar_one_or_none()
    assert remaining_idempotency is None

    disciplines = await client.get("/api/v1/disciplines?include_inactive=true", headers=admin)
    assert all(item["id"] != ids["discipline"] for item in disciplines.json()["items"])


async def test_delete_blocks_catalogs_with_operational_links(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    ids = await _catalogs(client, auth_header, "USED")
    eap = await _eap(client, auth_header, "91")
    equipment = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": ids["context"],
            "name": "Equipamento Sintético",
            "areaId": ids["area"],
            "disciplineId": ids["discipline"],
            "workPackageIds": [ids["work_package"]],
            "criticalityLabelId": ids["label"],
            "eapNodeId": eap["process"],
        },
        headers=admin,
    )
    assert equipment.status_code == 201, equipment.text

    blocked = {
        "unit": f"/units/{ids['unit']}",
        "context": f"/project-contexts/{ids['context']}",
        "area": f"/areas/{ids['area']}",
        "discipline": f"/disciplines/{ids['discipline']}",
        "label": f"/criticality-labels/{ids['label']}",
        "work_package": f"/work-packages/{ids['work_package']}",
        "eap_process": f"/eap-nodes/{eap['process']}",
        "eap_island": f"/eap-nodes/{eap['island']}",
    }
    for key, path in blocked.items():
        response = await client.delete(f"/api/v1{path}", headers=admin)
        assert response.status_code == 409, (key, response.text)
        assert "Desative o registro" in response.json()["error"]

    # O nó de área não é usado: continua excluível.
    response = await client.delete(f"/api/v1/eap-nodes/{eap['area']}", headers=admin)
    assert response.status_code == 204, response.text


async def test_delete_requires_manage_permission_and_reports_missing(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    ids = await _catalogs(client, auth_header, "PERM")

    forbidden = await client.delete(
        f"/api/v1/disciplines/{ids['discipline']}", headers=auth_header("ANALYST")
    )
    assert forbidden.status_code == 403

    missing = await client.delete("/api/v1/disciplines/nao-existe", headers=admin)
    assert missing.status_code == 404


async def test_master_catalog_deletes_components_equipment_and_area(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    area = (
        await client.post("/api/v1/master-catalog/areas", json={"name": "Área Mestre DEL"}, headers=admin)
    ).json()
    equipment = (
        await client.post(
            "/api/v1/master-catalog/equipments",
            json={"name": "Equipamento Mestre DEL", "areaIds": [area["id"]]},
            headers=admin,
        )
    ).json()
    component = (
        await client.post(
            f"/api/v1/master-catalog/equipments/{equipment['id']}/components",
            json={"name": "Componente Mestre DEL"},
            headers=admin,
        )
    ).json()

    assert (
        await client.delete(f"/api/v1/master-catalog/components/{component['id']}", headers=admin)
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/master-catalog/equipments/{equipment['id']}", headers=admin)
    ).status_code == 204
    assert (
        await client.delete(f"/api/v1/master-catalog/areas/{area['id']}", headers=admin)
    ).status_code == 204

    catalog = await client.get("/api/v1/master-catalog?include_inactive=true", headers=admin)
    assert catalog.status_code == 200, catalog.text
    assert catalog.json() == {"areas": [], "equipments": []}

    virtual = MasterArea(name="Sem área definida", normalized_name="sem area definida", is_unassigned=True)
    db_session.add(virtual)
    await db_session.commit()
    guarded = await client.delete(f"/api/v1/master-catalog/areas/{virtual.id}", headers=admin)
    assert guarded.status_code == 422
    assert "não pode ser excluída" in guarded.json()["error"]
