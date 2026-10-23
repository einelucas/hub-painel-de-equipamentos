"""Fluxo real de cadastro mestre → seleção de componentes → nova obra.

Os dados são sintéticos; este teste usa somente o PostgreSQL descartável do CI.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.equipment import Equipment, EquipmentComponent, ProjectContext

SEED = {
    "schema_version": "2.1",
    "areas": [
        {"id": "ar-test-1", "name": "Sem área definida", "is_unassigned_category": True},
        {"id": "ar-test-2", "name": "Área Sintética"},
    ],
    "equipments": [
        {
            "id": "eqm-test-1", "name": "Bomba Sintética", "area_ids": ["ar-test-1"],
            "component_option_ids": ["cmp-test-1", "cmp-test-2"], "review_flags": [],
        },
    ],
    "component_options": [
        {"id": "cmp-test-1", "equipment_id": "eqm-test-1", "name": "Motor sintético"},
        {"id": "cmp-test-2", "equipment_id": "eqm-test-1", "name": "Base sintética"},
    ],
}


async def test_create_project_with_only_selected_components(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    unit = await client.post("/api/v1/units", headers=admin, json={"name": "Unidade Sintética"})
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]

    preview = await client.post("/api/v1/master-catalog/seed?dry_run=true", headers=admin, json=SEED)
    assert preview.status_code == 200, preview.text
    assert preview.json()["equipmentsNew"] == 1
    empty = await client.get("/api/v1/master-catalog", headers=admin)
    assert empty.json()["equipments"] == []

    applied = await client.post("/api/v1/master-catalog/seed?dry_run=false", headers=admin, json=SEED)
    assert applied.status_code == 200, applied.text
    repeated = await client.post("/api/v1/master-catalog/seed?dry_run=false", headers=admin, json=SEED)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["existing"] == 5

    catalog = (await client.get("/api/v1/master-catalog", headers=admin)).json()
    assert len(catalog["areas"]) == 2
    assert len(catalog["equipments"]) == 1
    assert len(catalog["equipments"][0]["components"]) == 2

    project = {
        "requestId": "req-integration-project-1",
        "unitId": unit_id,
        "name": "Obra Sintética",
        "selections": [{"equipmentId": "eqm-test-1", "componentIds": ["cmp-test-2"]}],
    }
    created = await client.post("/api/v1/master-catalog/projects", headers=admin, json=project)
    assert created.status_code == 201, created.text
    assert created.json()["equipmentsCreated"] == 1
    assert created.json()["componentsCreated"] == 1

    again = await client.post("/api/v1/master-catalog/projects", headers=admin, json=project)
    assert again.status_code == 201, again.text
    assert again.json()["alreadyCreated"] is True
    assert again.json()["projectContextId"] == created.json()["projectContextId"]

    context_id = created.json()["projectContextId"]
    context = await db_session.get(ProjectContext, context_id)
    assert context is not None
    equipments = (
        await db_session.scalars(select(Equipment).where(Equipment.project_context_id == context_id))
    ).all()
    assert len(equipments) == 1
    assert equipments[0].name == "Bomba Sintética"
    assert equipments[0].current_stage == 0
    assert equipments[0].eap_node_id is None
    components = (
        await db_session.scalars(select(EquipmentComponent).where(
            EquipmentComponent.equipment_id == equipments[0].id
        ))
    ).all()
    assert len(components) == 1
    assert components[0].name == "Base sintética"
    assert components[0].tag is None
    assert components[0].lead_time_days is None

    assigned = await client.put(
        "/api/v1/master-catalog/equipments/eqm-test-1/areas",
        headers=admin, json={"areaIds": ["ar-test-2"]},
    )
    assert assigned.status_code == 204, assigned.text
    edited_catalog = (await client.get("/api/v1/master-catalog", headers=admin)).json()
    assert edited_catalog["equipments"][0]["areaIds"] == ["ar-test-2"]
    assert equipments[0].eap_node_id is None  # classificação não altera EAP da obra


async def test_invalid_selection_rolls_back_project(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    unit = await client.post("/api/v1/units", headers=admin, json={"name": "Outra Unidade Sintética"})
    assert unit.status_code == 201
    seed = await client.post("/api/v1/master-catalog/seed?dry_run=false", headers=admin, json=SEED)
    assert seed.status_code == 200

    bad = await client.post("/api/v1/master-catalog/projects", headers=admin, json={
        "requestId": "req-integration-project-2",
        "unitId": unit.json()["id"], "name": "Não deve existir",
        "selections": [{"equipmentId": "eqm-test-1", "componentIds": ["cmp-invalido"]}],
    })
    assert bad.status_code in (404, 422), bad.text
    assert not (
        await db_session.scalars(select(ProjectContext).where(
            ProjectContext.name == "Não deve existir"
        ))
    ).all()


async def test_viewer_cannot_import_or_create_project(client, auth_header) -> None:
    viewer = auth_header("VIEWER")
    assert (
        await client.post("/api/v1/master-catalog/seed", headers=viewer, json=SEED)
    ).status_code == 403
    assert (
        await client.post("/api/v1/master-catalog/projects", headers=viewer, json={
            "requestId": "req-test-viewer", "unitId": "x", "name": "Negado", "selections": [],
        })
    ).status_code == 403
