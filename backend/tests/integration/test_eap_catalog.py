"""Fundação da EAP: ProjectContext.eap_prefix, catálogo eap_node e project_eap."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.equipment import EapNode, Equipment, ProjectContext, ProjectEap, Unit
from tests.helpers import grant_unit


async def _seed_catalog(db_session) -> dict[str, str]:
    process = EapNode(code="01", name="Geração de Vapor", level="PROCESS")
    destilaria = EapNode(code="08", name="Destilaria", level="PROCESS", active=False)
    db_session.add_all([process, destilaria])
    await db_session.flush()
    area = EapNode(code="01.A", name="Caldeira", level="AREA", parent_id=process.id)
    db_session.add(area)
    await db_session.commit()
    return {"process": process.id, "area": area.id, "destilaria": destilaria.id}


async def test_project_context_eap_prefix_is_created_exposed_and_not_unique(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit = await client.post("/api/v1/units", json={"code": "RDN", "name": "Rondonópolis"}, headers=admin)
    assert unit.status_code == 201, unit.text
    assert "numericCode" not in unit.json()
    unit_id = unit.json()["id"]
    contexts_url = f"/api/v1/units/{unit_id}/project-contexts"

    f1 = await client.post(
        contexts_url, json={"code": "F1", "name": "Fase 1", "eapPrefix": "23"}, headers=admin
    )
    f2 = await client.post(
        contexts_url, json={"code": "F2", "name": "Fase 2", "eapPrefix": "24"}, headers=admin
    )
    legacy = await client.post(contexts_url, json={"code": "C2", "name": "Caldeira 2"}, headers=admin)
    assert (f1.status_code, f2.status_code, legacy.status_code) == (201, 201, 201)
    assert (f1.json()["eapPrefix"], f2.json()["eapPrefix"], legacy.json()["eapPrefix"]) == ("23", "24", None)

    invalid = await client.post(
        contexts_url, json={"code": "F3", "name": "Fase 3", "eapPrefix": "23A"}, headers=admin
    )
    assert invalid.status_code == 422

    other_unit = await client.post("/api/v1/units", json={"code": "XYZ", "name": "Outra"}, headers=admin)
    reused = await client.post(
        f"/api/v1/units/{other_unit.json()['id']}/project-contexts",
        json={"code": "F1", "name": "Fase 1", "eapPrefix": "23"},
        headers=admin,
    )
    assert reused.status_code == 201, reused.text

    listed = (await client.get(contexts_url, headers=admin)).json()["items"]
    assert {item["code"]: item["eapPrefix"] for item in listed} == {"F1": "23", "F2": "24", "C2": None}


async def test_list_eap_nodes_with_filters(client, auth_header, db_session) -> None:
    ids = await _seed_catalog(db_session)
    viewer = auth_header("VIEWER")

    every = (await client.get("/api/v1/eap-nodes", headers=viewer)).json()["items"]
    assert [item["code"] for item in every] == ["01", "01.A", "08"]
    area = next(item for item in every if item["code"] == "01.A")
    assert (area["level"], area["parentId"]) == ("AREA", ids["process"])

    areas = (await client.get("/api/v1/eap-nodes?level=AREA", headers=viewer)).json()["items"]
    assert [item["code"] for item in areas] == ["01.A"]
    children = (await client.get(f"/api/v1/eap-nodes?parent_id={ids['process']}", headers=viewer)).json()
    assert [item["code"] for item in children["items"]] == ["01.A"]
    inactive = (await client.get("/api/v1/eap-nodes?active=false", headers=viewer)).json()["items"]
    assert [item["code"] for item in inactive] == ["08"]

    assert (await client.get("/api/v1/eap-nodes?level=SUBAREA", headers=viewer)).status_code == 422


async def test_project_eap_nodes_respect_context_scope(client, auth_header, db_session) -> None:
    ids = await _seed_catalog(db_session)
    unit = Unit(code="RDN", name="Rondonópolis")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="F1", name="Fase 1", eap_prefix="23")
    db_session.add(context)
    await db_session.flush()
    db_session.add(ProjectEap(project_context_id=context.id, eap_node_id=ids["area"]))
    await db_session.commit()

    url = f"/api/v1/project-contexts/{context.id}/eap-nodes"
    denied = await client.get(url, headers=auth_header("VIEWER"))
    assert denied.status_code in (403, 404)

    await grant_unit(client, auth_header, unit.id)
    allowed = (await client.get(url, headers=auth_header("VIEWER"))).json()["items"]
    assert [(item["eapNode"]["code"], item["eapNode"]["level"]) for item in allowed] == [("01.A", "AREA")]

    missing = await client.get("/api/v1/project-contexts/nao-existe/eap-nodes", headers=auth_header("ADMIN"))
    assert missing.status_code == 404


async def test_database_enforces_eap_identity_rules(db_session) -> None:
    ids = await _seed_catalog(db_session)

    db_session.add(EapNode(code="01", name="Duplicado", level="PROCESS"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    db_session.add(EapNode(code="2101.A", name="Prefixo", level="ILHA"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    unit = Unit(code="LEM", name="LEM")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="C2", name="Caldeira 2")
    db_session.add(context)
    await db_session.flush()
    db_session.add_all(
        [
            ProjectEap(project_context_id=context.id, eap_node_id=ids["area"]),
            ProjectEap(project_context_id=context.id, eap_node_id=ids["area"]),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_equipment_keeps_area_and_eap_node_is_optional(db_session) -> None:
    ids = await _seed_catalog(db_session)
    unit = Unit(code="NMT", name="Nova Mutum")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="CAL4", name="Caldeira 4")
    db_session.add(context)
    await db_session.flush()
    legacy = Equipment(project_context_id=context.id, name="Sem EAP", current_stage=0)
    with_eap = Equipment(
        project_context_id=context.id, name="Com EAP", current_stage=0, eap_node_id=ids["area"]
    )
    db_session.add_all([legacy, with_eap])
    await db_session.commit()

    rows = {
        name: (area_id, eap_node_id)
        for name, area_id, eap_node_id in (
            await db_session.execute(select(Equipment.name, Equipment.area_id, Equipment.eap_node_id))
        ).all()
    }
    assert rows == {"Sem EAP": (None, None), "Com EAP": (None, ids["area"])}
