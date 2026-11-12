"""Cenários integrados do modo de edição: transações no PostgreSQL de TEST.

A fixture de integração bloqueia alvos que não sejam um banco local *_test.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.equipment import EapNode
from tests.helpers import grant_unit


async def _context(client, auth_header, code: str) -> dict[str, str]:
    headers = auth_header("ADMIN")
    unit_resp = await client.post(
        "/api/v1/units", json={"code": f"B-{code}", "name": f"Unidade {code}"},
        headers=headers,
    )
    assert unit_resp.status_code == 201, unit_resp.text
    unit = unit_resp.json()
    context_resp = await client.post(
        f"/api/v1/units/{unit['id']}/project-contexts",
        json={"code": code, "name": f"Obra {code}"}, headers=headers,
    )
    assert context_resp.status_code == 201, context_resp.text
    await grant_unit(client, auth_header, unit["id"])
    return {"unit": unit["id"], "context": context_resp.json()["id"]}


async def _equipment(client, auth_header, context_id: str, name: str = "Bomba") -> dict:
    r = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": context_id, "name": name},
        headers=auth_header("ANALYST"),
    )
    assert r.status_code == 201, r.text
    return r.json()


def _body(context_id: str, equipment: dict, field="origin", value="Manual") -> dict:
    return {
        "projectContextId": context_id,
        "items": [{
            "equipmentId": equipment["id"],
            "expectedUpdatedAt": equipment["updatedAt"],
            "changes": [{"field": field, "operation": "SET", "value": value}],
        }],
    }


def _apply_body(preview_request: dict, preview: dict) -> dict:
    return {
        **preview_request,
        "previewToken": preview["previewToken"],
        "idempotencyKey": str(uuid4()),
    }


async def test_preview_and_apply_are_scoped_audited_and_idempotent(
    client, auth_header, db_session
) -> None:
    ctx = await _context(client, auth_header, "B01")
    equipment = await _equipment(client, auth_header, ctx["context"])
    request = _body(ctx["context"], equipment)
    preview = await client.post(
        "/api/v1/equipments/bulk/preview", json=request,
        headers=auth_header("ANALYST"),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["changedCount"] == 1
    assert preview.json()["diffs"][0]["previousValue"] is None
    before = await client.get(
        f"/api/v1/equipments/{equipment['id']}", headers=auth_header("ANALYST")
    )
    assert before.json()["equipment"]["origin"] is None

    body = _apply_body(request, preview.json())
    first = await client.post(
        "/api/v1/equipments/bulk/apply", json=body,
        headers=auth_header("ANALYST"),
    )
    assert first.status_code == 200, first.text
    assert first.json()["updatedCount"] == 1
    repeated = await client.post(
        "/api/v1/equipments/bulk/apply", json=body,
        headers=auth_header("ANALYST"),
    )
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == first.json()
    saved = await client.get(
        f"/api/v1/equipments/{equipment['id']}", headers=auth_header("ANALYST")
    )
    assert saved.json()["equipment"]["origin"] == "Manual"
    logs = (await db_session.execute(
        select(AuditLog).where(AuditLog.action == "equipment.bulk_update")
    )).scalars().all()
    assert len(logs) == 1
    assert logs[0].metadata_["batchId"] == first.json()["batchId"]


async def test_viewer_and_wrong_context_are_blocked(client, auth_header) -> None:
    ctx = await _context(client, auth_header, "B02")
    other = await _context(client, auth_header, "B03")
    eq = await _equipment(client, auth_header, ctx["context"])
    request = _body(ctx["context"], eq)
    viewer = await client.post(
        "/api/v1/equipments/bulk/preview", json=request,
        headers=auth_header("VIEWER"),
    )
    assert viewer.status_code == 403
    request["projectContextId"] = other["context"]
    forbidden = await client.post(
        "/api/v1/equipments/bulk/preview", json=request,
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 404


async def test_protected_fields_never_enter_bulk_endpoint(client, auth_header) -> None:
    ctx = await _context(client, auth_header, "B04")
    eq = await _equipment(client, auth_header, ctx["context"])
    for field in ("name", "currentStage", "operationalStatus", "deliveryDeadline"):
        request = _body(ctx["context"], eq, field, "alterar")
        r = await client.post(
            "/api/v1/equipments/bulk/preview", json=request,
            headers=auth_header("ANALYST"),
        )
        assert r.status_code == 422, (field, r.text)


async def test_preview_rejects_invalid_island_eap(client, auth_header, db_session) -> None:
    ctx = await _context(client, auth_header, "B05")
    eq = await _equipment(client, auth_header, ctx["context"])
    node = EapNode(code="B05", name="Ilha", level="ISLAND")
    db_session.add(node)
    await db_session.commit()
    r = await client.post(
        "/api/v1/equipments/bulk/preview",
        json=_body(ctx["context"], eq, "eapNodeId", node.id),
        headers=auth_header("ANALYST"),
    )
    assert r.status_code == 422, r.text


async def test_conflict_aborts_every_row_without_partial_commit(client, auth_header) -> None:
    ctx = await _context(client, auth_header, "B06")
    eq1 = await _equipment(client, auth_header, ctx["context"], "Primeiro")
    eq2 = await _equipment(client, auth_header, ctx["context"], "Segundo")
    request = _body(ctx["context"], eq1)
    request["items"].append(_body(ctx["context"], eq2)["items"][0])
    preview = await client.post(
        "/api/v1/equipments/bulk/preview", json=request,
        headers=auth_header("ANALYST"),
    )
    assert preview.status_code == 200, preview.text
    await asyncio.sleep(0.02)
    changed = await client.patch(
        f"/api/v1/equipments/{eq2['id']}",
        json={"origin": "Concorrente", "expectedUpdatedAt": eq2["updatedAt"]},
        headers=auth_header("ANALYST"),
    )
    assert changed.status_code == 200, changed.text
    applying = await client.post(
        "/api/v1/equipments/bulk/apply", json=_apply_body(request, preview.json()),
        headers=auth_header("ANALYST"),
    )
    assert applying.status_code == 409, applying.text
    check = await client.get(
        f"/api/v1/equipments/{eq1['id']}", headers=auth_header("ANALYST")
    )
    assert check.json()["equipment"]["origin"] is None


async def test_wp_add_preserves_current_links(client, auth_header) -> None:
    ctx = await _context(client, auth_header, "B07")
    headers = auth_header("ADMIN")
    packages = []
    for suffix in ("A", "B"):
        resp = await client.post(
            "/api/v1/work-packages",
            json={
                "projectContextId": ctx["context"],
                "code": f"B07{suffix}", "name": f"Pacote {suffix}",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        packages.append(resp.json()["id"])
    eq = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": ctx["context"],
            "name": "Com WP", "workPackageIds": [packages[0]],
        },
        headers=auth_header("ANALYST"),
    )
    assert eq.status_code == 201, eq.text
    request = _body(ctx["context"], eq.json(), "workPackageIds", [packages[1]])
    request["items"][0]["changes"][0]["operation"] = "ADD"
    preview = await client.post(
        "/api/v1/equipments/bulk/preview", json=request,
        headers=auth_header("ANALYST"),
    )
    assert preview.status_code == 200, preview.text
    saved = await client.post(
        "/api/v1/equipments/bulk/apply", json=_apply_body(request, preview.json()),
        headers=auth_header("ANALYST"),
    )
    assert saved.status_code == 200, saved.text
    result = await client.get(
        f"/api/v1/equipments/{eq.json()['id']}", headers=auth_header("ANALYST")
    )
    assert {item["id"] for item in result.json()["equipment"]["workPackages"]} == set(packages)


async def test_components_multiple_changes_and_cross_equipment_protection(
    client, auth_header
) -> None:
    ctx = await _context(client, auth_header, "B08")
    eq1 = await _equipment(client, auth_header, ctx["context"])
    eq2 = await _equipment(client, auth_header, ctx["context"], "Outra Bomba")
    components = []
    for i in range(3):
        parent = eq1 if i < 2 else eq2
        response = await client.post(
            f"/api/v1/equipments/{parent['id']}/components",
            json={"name": f"Componente {i}"},
            headers=auth_header("ANALYST"),
        )
        assert response.status_code == 201, response.text
        components.append(response.json())
    request = {"items": [
        {
            "componentId": components[0]["id"],
            "expectedUpdatedAt": components[0]["updatedAt"],
            "changes": [{"field": "startupAt", "operation": "SET", "value": "2027-11-12"}],
        },
        {
            "componentId": components[1]["id"],
            "expectedUpdatedAt": components[1]["updatedAt"],
            "changes": [{"field": "leadTimeDays", "operation": "SET", "value": 120}],
        },
    ]}
    preview = await client.post(
        f"/api/v1/equipments/{eq1['id']}/components/bulk/preview",
        json=request, headers=auth_header("ANALYST"),
    )
    assert preview.status_code == 200, preview.text
    result = await client.post(
        f"/api/v1/equipments/{eq1['id']}/components/bulk/apply",
        json=_apply_body(request, preview.json()),
        headers=auth_header("ANALYST"),
    )
    assert result.status_code == 200, result.text
    assert result.json()["updatedCount"] == 2
    detail = await client.get(
        f"/api/v1/equipments/{eq1['id']}", headers=auth_header("ANALYST")
    )
    values = {c["id"]: c for c in detail.json()["components"]}
    assert values[components[0]["id"]]["startupAt"] == "2027-11-12"
    assert values[components[1]["id"]]["leadTimeDays"] == 120

    invalid = dict(request)
    invalid["items"] = [dict(request["items"][0], componentId=components[2]["id"])]
    wrong = await client.post(
        f"/api/v1/equipments/{eq1['id']}/components/bulk/preview",
        json=invalid, headers=auth_header("ANALYST"),
    )
    assert wrong.status_code == 404


async def test_selection_uses_server_and_not_browser_page(client, auth_header) -> None:
    ctx = await _context(client, auth_header, "B09")
    for i in range(27):
        await _equipment(client, auth_header, ctx["context"], f"Equipamento {i:02}")
    r = await client.get(
        "/api/v1/equipments/bulk/selection",
        params={"projectContextId": ctx["context"], "stage": 0},
        headers=auth_header("ANALYST"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 27
    assert len({item["equipmentId"] for item in r.json()["items"]}) == 27
