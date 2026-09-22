"""Testes de integração HTTP de `/auditoria`."""

from __future__ import annotations

from datetime import date, timedelta

from tests.helpers import grant_unit


async def _new_equipment(client, auth_header, suffix: str) -> str:
    admin = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units", json={"code": f"U-{suffix}", "name": f"Unidade {suffix}"}, headers=admin
        )
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"code": f"CTX-{suffix}", "name": f"Contexto {suffix}"},
            headers=admin,
        )
    ).json()
    await grant_unit(client, auth_header, unit["id"])
    created = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": context["id"], "name": f"Equipamento {suffix}"},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def test_audit_requires_admin(client, auth_header) -> None:
    forbidden = await client.get("/api/v1/auditoria", headers=auth_header("ANALYST"))
    assert forbidden.status_code == 403


async def test_audit_lists_entries_produced_by_user_changes(client, auth_header) -> None:
    created = await client.post(
        "/api/v1/usuarios",
        json={"name": "Ana Souza", "email": "ana.audit@example.com", "role": "VIEWER"},
        headers=auth_header("ADMIN"),
    )
    assert created.status_code == 201

    response = await client.get("/api/v1/auditoria", headers=auth_header("ADMIN"))
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] >= 1
    actions = {item["action"] for item in body["items"]}
    assert "user.create" in actions


async def test_audit_pagination_page_size_capped(client, auth_header) -> None:
    response = await client.get(
        "/api/v1/auditoria?pageSize=1000", headers=auth_header("ADMIN")
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["pageSize"] <= 100


async def test_audit_filters_by_equipment_id_includes_sub_entities(client, auth_header) -> None:
    """GAP-019 (Etapa 6D): mesma resolução por relacionamento do GAP-002 —
    inclui sub-entidades (negociação, etc.), sem vazar auditoria de outro
    equipamento."""
    equipment_id = await _new_equipment(client, auth_header, "AUDEQ")
    other_id = await _new_equipment(client, auth_header, "AUDEQ2")
    patched = await client.patch(
        f"/api/v1/equipments/{equipment_id}/negotiation",
        json={"equalized": True},
        headers=auth_header("ANALYST"),
    )
    assert patched.status_code == 200

    response = await client.get(
        f"/api/v1/auditoria?equipment_id={equipment_id}", headers=auth_header("ADMIN")
    )
    assert response.status_code == 200
    items = response.json()["items"]
    actions = {item["action"] for item in items}
    assert "equipment.create" in actions
    assert "negotiation.update" in actions
    assert other_id not in {item["entityId"] for item in items if item["entityId"]}


async def test_audit_filters_by_user_id(client, auth_header) -> None:
    await _new_equipment(client, auth_header, "AUDUSR")
    analyst_id = (await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))).json()["id"]

    response = await client.get(
        f"/api/v1/auditoria?user_id={analyst_id}", headers=auth_header("ADMIN")
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(item["userId"] == analyst_id for item in items)


async def test_audit_filters_by_date_range(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "AUDDATE")
    today = date.today()

    only_today = await client.get(
        f"/api/v1/auditoria?equipment_id={equipment_id}&date_from={today}&date_to={today}",
        headers=auth_header("ADMIN"),
    )
    assert only_today.status_code == 200
    assert any(item["action"] == "equipment.create" for item in only_today.json()["items"])

    future_only = await client.get(
        "/api/v1/auditoria?equipment_id="
        f"{equipment_id}&date_from={today + timedelta(days=1)}",
        headers=auth_header("ADMIN"),
    )
    assert future_only.status_code == 200
    assert future_only.json()["items"] == []


async def test_audit_combines_equipment_and_action_filters(client, auth_header) -> None:
    equipment_id = await _new_equipment(client, auth_header, "AUDCOMB")
    await client.patch(
        f"/api/v1/equipments/{equipment_id}/negotiation",
        json={"equalized": True},
        headers=auth_header("ANALYST"),
    )

    response = await client.get(
        f"/api/v1/auditoria?equipment_id={equipment_id}&action=negotiation.update",
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert all(item["action"] == "negotiation.update" for item in items)
