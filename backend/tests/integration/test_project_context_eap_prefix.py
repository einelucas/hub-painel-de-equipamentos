"""Configuração manual do prefixo EAP do ProjectContext (PATCH /project-contexts/{id})."""

from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.equipment import ProjectContext, Unit


async def _unit_with_contexts(client, admin) -> tuple[str, str, str]:
    unit = await client.post("/api/v1/units", json={"code": "RDN", "name": "Rondonópolis"}, headers=admin)
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]
    url = f"/api/v1/units/{unit_id}/project-contexts"
    f1 = await client.post(url, json={"code": "F1", "name": "Fase 1"}, headers=admin)
    f2 = await client.post(url, json={"code": "F2", "name": "Fase 2"}, headers=admin)
    assert (f1.status_code, f2.status_code) == (201, 201)
    return unit_id, f1.json()["id"], f2.json()["id"]


async def _prefix_in_db(db_session, context_id: str) -> str | None:
    db_session.expire_all()
    return (
        await db_session.execute(select(ProjectContext.eap_prefix).where(ProjectContext.id == context_id))
    ).scalar_one()


async def test_eap_prefix_is_read_set_changed_and_cleared(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    unit_id, f1, _ = await _unit_with_contexts(client, admin)
    listed = (await client.get(f"/api/v1/units/{unit_id}/project-contexts", headers=admin)).json()["items"]
    assert {item["code"]: item["eapPrefix"] for item in listed} == {"F1": None, "F2": None}

    url = f"/api/v1/project-contexts/{f1}"
    for value in ("23", "24", None):
        response = await client.patch(url, json={"eapPrefix": value}, headers=admin)
        assert response.status_code == 200, response.text
        assert response.json()["eapPrefix"] == value
        assert await _prefix_in_db(db_session, f1) == value  # None é NULL, nunca ""

    zero = await client.patch(url, json={"eapPrefix": "03"}, headers=admin)
    assert zero.json()["eapPrefix"] == "03" and await _prefix_in_db(db_session, f1) == "03"

    renamed = await client.patch(url, json={"name": "Fase 1 - Biomassa"}, headers=admin)
    assert renamed.status_code == 200
    assert (renamed.json()["name"], renamed.json()["eapPrefix"]) == ("Fase 1 - Biomassa", "03")


async def test_eap_prefix_change_is_audited(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    _, f1, _ = await _unit_with_contexts(client, admin)
    await client.patch(f"/api/v1/project-contexts/{f1}", json={"eapPrefix": "23"}, headers=admin)
    await client.patch(f"/api/v1/project-contexts/{f1}", json={"eapPrefix": None}, headers=admin)

    logs = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(AuditLog.entity == "ProjectContext", AuditLog.entityId == f1)
                .where(AuditLog.action == "catalog.update")
                .order_by(AuditLog.createdAt)
            )
        )
        .scalars()
        .all()
    )
    assert [(log.previousData, log.newData) for log in logs] == [
        ({"eap_prefix": None}, {"eap_prefix": "23"}),
        ({"eap_prefix": "23"}, {"eap_prefix": None}),
    ]
    assert all(log.userId is not None and log.createdAt is not None for log in logs)


async def test_same_prefix_is_allowed_in_different_contexts(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    _, f1, f2 = await _unit_with_contexts(client, admin)
    first = await client.patch(f"/api/v1/project-contexts/{f1}", json={"eapPrefix": "23"}, headers=admin)
    second = await client.patch(f"/api/v1/project-contexts/{f2}", json={"eapPrefix": "23"}, headers=admin)
    assert (first.status_code, second.status_code) == (200, 200)


async def test_invalid_prefix_is_rejected_without_change(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    _, f1, _ = await _unit_with_contexts(client, admin)
    await client.patch(f"/api/v1/project-contexts/{f1}", json={"eapPrefix": "21"}, headers=admin)
    for value in ("", "2A", "23.A", "RDN", "-1"):
        response = await client.patch(
            f"/api/v1/project-contexts/{f1}", json={"eapPrefix": value}, headers=admin
        )
        assert response.status_code == 422, (value, response.text)
    assert await _prefix_in_db(db_session, f1) == "21"


async def test_missing_context_and_forbidden_roles(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    _, f1, _ = await _unit_with_contexts(client, admin)
    missing = await client.patch(
        "/api/v1/project-contexts/nao-existe", json={"eapPrefix": "23"}, headers=admin
    )
    assert missing.status_code == 404

    for role in ("ANALYST", "VIEWER"):
        denied = await client.patch(
            f"/api/v1/project-contexts/{f1}", json={"eapPrefix": "23"}, headers=auth_header(role)
        )
        assert denied.status_code == 403, (role, denied.text)
    assert await _prefix_in_db(db_session, f1) is None


async def test_prefix_update_does_not_touch_unit(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    unit_id, f1, _ = await _unit_with_contexts(client, admin)
    before = (
        await db_session.execute(select(Unit.code, Unit.name, Unit.updated_at).where(Unit.id == unit_id))
    ).one()

    await client.patch(f"/api/v1/project-contexts/{f1}", json={"eapPrefix": "24"}, headers=admin)

    db_session.expire_all()
    after = (
        await db_session.execute(select(Unit.code, Unit.name, Unit.updated_at).where(Unit.id == unit_id))
    ).one()
    assert after == before
    unit_audits = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.entity == "Unit", AuditLog.action == "catalog.update")
        )
    ).all()
    assert unit_audits == []
