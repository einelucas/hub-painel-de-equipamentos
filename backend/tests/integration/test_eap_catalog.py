"""Fundação da EAP: Unit.numeric_code, catálogo eap_node e project_eap."""

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


async def test_unit_numeric_code_is_created_exposed_and_unique(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    created = await client.post(
        "/api/v1/units", json={"code": "RVD", "name": "Rio Verde", "numericCode": "21"}, headers=admin
    )
    assert created.status_code == 201, created.text
    assert created.json()["numericCode"] == "21"

    legacy = await client.post("/api/v1/units", json={"code": "LEG", "name": "Legado"}, headers=admin)
    assert legacy.status_code == 201, legacy.text
    assert legacy.json()["numericCode"] is None

    duplicated = await client.post(
        "/api/v1/units", json={"code": "OUT", "name": "Outra", "numericCode": "21"}, headers=admin
    )
    assert duplicated.status_code == 409, duplicated.text

    invalid = await client.post(
        "/api/v1/units", json={"code": "INV", "name": "Inválida", "numericCode": "2A"}, headers=admin
    )
    assert invalid.status_code == 422

    listed = (await client.get("/api/v1/units", headers=admin)).json()["items"]
    assert {item["code"]: item["numericCode"] for item in listed} == {"RVD": "21", "LEG": None}


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
    unit = Unit(code="RDN", name="Rondonópolis", numeric_code="23")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="F1", name="Fase 1")
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
