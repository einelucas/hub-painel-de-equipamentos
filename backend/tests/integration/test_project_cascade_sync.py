from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.access import UserUnitAccess
from app.models.equipment import Equipment, EquipmentComponent, ProjectContext
from app.models.process import Contract, Negotiation
from app.models.sync import SyncEvent


async def _project(client, auth_header, suffix: str) -> tuple[dict, dict, dict]:
    admin = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units", json={"name": f"Unidade Sync {suffix}"}, headers=admin
        )
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"name": f"Obra Sync {suffix}"},
            headers=admin,
        )
    ).json()
    equipment = (
        await client.post(
            "/api/v1/equipments",
            json={"projectContextId": context["id"], "name": f"Equipamento {suffix}"},
            headers=admin,
        )
    ).json()
    return unit, context, equipment


async def test_equipment_optimistic_concurrency_and_persistent_events(
    client, auth_header
) -> None:
    admin = auth_header("ADMIN")
    unit, context, equipment = await _project(client, auth_header, "CONFLICT")
    version = equipment["updatedAt"]

    first = await client.patch(
        f"/api/v1/equipments/{equipment['id']}",
        json={"name": "Primeira edição", "expectedUpdatedAt": version},
        headers=admin,
    )
    assert first.status_code == 200, first.text

    stale = await client.patch(
        f"/api/v1/equipments/{equipment['id']}",
        json={"name": "Edição concorrente", "expectedUpdatedAt": version},
        headers=admin,
    )
    assert stale.status_code == 409
    assert "outra pessoa" in stale.json()["error"]

    events = await client.get("/api/v1/sync/events?after=0", headers=admin)
    assert events.status_code == 200, events.text
    items = events.json()["items"]
    assert any(
        item["eventType"] == "created"
        and item["entityType"] == "project_context"
        and item["entityId"] == context["id"]
        for item in items
    )
    assert any(
        item["eventType"] == "updated"
        and item["equipmentId"] == equipment["id"]
        and item["unitId"] == unit["id"]
        for item in items
    )


async def test_project_cascade_deletes_owned_tree_and_preserves_audit_event(
    client, auth_header, db_session
) -> None:
    admin = auth_header("ADMIN")
    unit, context, equipment = await _project(client, auth_header, "CASCADE")
    db_session.add_all(
        [
            EquipmentComponent(equipment_id=equipment["id"], name="Componente exclusivo"),
            Negotiation(equipment_id=equipment["id"]),
            Contract(equipment_id=equipment["id"], contract_number="CT-001"),
        ]
    )
    await db_session.commit()

    impact = await client.get(
        f"/api/v1/project-contexts/{context['id']}/deletion-impact", headers=admin
    )
    assert impact.status_code == 200, impact.text
    counts = impact.json()["records"]
    assert counts["equipments"] == 1
    assert counts["components"] == 1
    assert counts["negotiations"] == 1
    assert counts["contracts"] == 1

    wrong = await client.request(
        "DELETE",
        f"/api/v1/project-contexts/{context['id']}",
        json={"confirmationName": "nome incorreto"},
        headers=admin,
    )
    assert wrong.status_code == 409
    assert await db_session.get(ProjectContext, context["id"]) is not None
    assert await db_session.get(Equipment, equipment["id"]) is not None

    deleted = await client.request(
        "DELETE",
        f"/api/v1/project-contexts/{context['id']}",
        json={"confirmationName": context["name"]},
        headers=admin,
    )
    assert deleted.status_code == 204, deleted.text
    db_session.expire_all()
    assert await db_session.get(ProjectContext, context["id"]) is None
    assert await db_session.get(Equipment, equipment["id"]) is None
    assert (
        await db_session.scalar(
            select(SyncEvent).where(
                SyncEvent.entity_type == "project_context",
                SyncEvent.entity_id == context["id"],
                SyncEvent.event_type == "deleted",
            )
        )
    ) is not None
    # A unidade é cadastro corporativo compartilhado e nunca acompanha a obra.
    assert (await client.get("/api/v1/units", headers=admin)).json()["items"][0]["id"] == unit["id"]


async def test_project_delete_rolls_back_and_requires_manage_permission(
    client, auth_header, db_session, monkeypatch
) -> None:
    admin = auth_header("ADMIN")
    _, context, equipment = await _project(client, auth_header, "ROLLBACK")
    forbidden = await client.get(
        f"/api/v1/project-contexts/{context['id']}/deletion-impact",
        headers=auth_header("VIEWER"),
    )
    assert forbidden.status_code == 403

    async def fail_event(*args, **kwargs):
        raise RuntimeError("falha sintética antes do commit")

    monkeypatch.setattr("app.modules.catalogs.services.record_sync_event", fail_event)
    with pytest.raises(RuntimeError, match="falha sintética"):
        await client.request(
            "DELETE",
            f"/api/v1/project-contexts/{context['id']}",
            json={"confirmationName": context["name"]},
            headers=admin,
        )
    db_session.expire_all()
    assert await db_session.get(ProjectContext, context["id"]) is not None
    assert await db_session.get(Equipment, equipment["id"]) is not None


async def test_sync_events_are_filtered_by_unit_scope(client, auth_header, db_session) -> None:
    allowed_unit, allowed_context, _ = await _project(client, auth_header, "ALLOWED")
    _, hidden_context, _ = await _project(client, auth_header, "HIDDEN")
    analyst = (
        await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))
    ).json()
    db_session.add(UserUnitAccess(user_id=analyst["id"], unit_id=allowed_unit["id"]))
    await db_session.commit()

    response = await client.get("/api/v1/sync/events?after=0", headers=auth_header("ANALYST"))
    assert response.status_code == 200, response.text
    project_ids = {
        item["projectContextId"]
        for item in response.json()["items"]
        if item["projectContextId"] is not None
    }
    assert allowed_context["id"] in project_ids
    assert hidden_context["id"] not in project_ids
