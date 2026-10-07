"""Fundação da EAP: catálogo eap_node e project_eap (o código é só EapNode.code)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.audit import AuditLog
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


async def test_project_context_needs_no_eap_prefix(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit = await client.post("/api/v1/units", json={"code": "TST", "name": "Unidade Teste"}, headers=admin)
    assert unit.status_code == 201, unit.text
    assert "numericCode" not in unit.json()
    contexts_url = f"/api/v1/units/{unit.json()['id']}/project-contexts"

    created = await client.post(
        contexts_url, json={"code": "PA", "name": "Projeto Sintético A"}, headers=admin
    )
    assert created.status_code == 201, created.text
    assert "eapPrefix" not in created.json()


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


async def test_admin_creates_eap_tree_with_valid_parent_and_audit(
    client, auth_header, db_session
) -> None:
    admin = auth_header("ADMIN")
    island = await client.post(
        "/api/v1/eap-nodes",
        json={"code": "D", "name": "Ilha Sintética", "level": "ISLAND", "parentId": None},
        headers=admin,
    )
    assert island.status_code == 201, island.text
    process = await client.post(
        "/api/v1/eap-nodes",
        json={
            "code": "01",
            "name": "Processo Sintético",
            "level": "PROCESS",
            "parentId": island.json()["id"],
        },
        headers=admin,
    )
    assert process.status_code == 201, process.text
    area = await client.post(
        "/api/v1/eap-nodes",
        json={
            "code": "01.A",
            "name": "Área Sintética",
            "level": "AREA",
            "parentId": process.json()["id"],
        },
        headers=admin,
    )
    assert area.status_code == 201, area.text
    assert (area.json()["level"], area.json()["parentId"]) == ("AREA", process.json()["id"])

    nodes = (await client.get("/api/v1/eap-nodes", headers=admin)).json()["items"]
    assert [(item["code"], item["level"]) for item in nodes] == [
        ("01", "PROCESS"),
        ("01.A", "AREA"),
        ("D", "ISLAND"),
    ]
    audits = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.entity == "EapNode").order_by(AuditLog.createdAt)
        )
    ).scalars().all()
    assert [item.action for item in audits] == ["catalog.create"] * 3
    assert audits[-1].newData["parentId"] == process.json()["id"]


async def test_eap_creation_rejects_invalid_hierarchy_duplicate_and_permission(
    client, auth_header
) -> None:
    admin = auth_header("ADMIN")
    process = await client.post(
        "/api/v1/eap-nodes",
        json={"code": "01", "name": "Processo Sintético", "level": "PROCESS"},
        headers=admin,
    )
    assert process.status_code == 201

    wrong_parent = await client.post(
        "/api/v1/eap-nodes",
        json={
            "code": "02.A",
            "name": "Área com pai errado",
            "level": "AREA",
            "parentId": process.json()["id"],
        },
        headers=admin,
    )
    assert wrong_parent.status_code == 422
    assert "não pertence ao PROCESS 01" in wrong_parent.json()["error"]

    duplicate = await client.post(
        "/api/v1/eap-nodes",
        json={"code": "01", "name": "Duplicado", "level": "PROCESS"},
        headers=admin,
    )
    assert duplicate.status_code == 409

    forbidden = await client.post(
        "/api/v1/eap-nodes",
        json={"code": "02", "name": "Outro", "level": "PROCESS"},
        headers=auth_header("VIEWER"),
    )
    assert forbidden.status_code == 403


async def test_project_eap_nodes_respect_context_scope(client, auth_header, db_session) -> None:
    ids = await _seed_catalog(db_session)
    unit = Unit(code="TST", name="Unidade Teste")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="PA", name="Projeto Sintético A")
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
