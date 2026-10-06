"""P1.3.1 — `ProjectContext.eap_prefix` é LEGADO: a API não o expõe, não o grava e não o lê.

A coluna continua no banco (sem migration) só por compatibilidade de schema.
"""

from __future__ import annotations

from sqlalchemy import select, update

from app.models.equipment import ProjectContext


async def _context(client, admin, body: dict | None = None) -> tuple[str, str]:
    unit = await client.post("/api/v1/units", json={"code": "TST", "name": "Unidade Teste"}, headers=admin)
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]
    created = await client.post(
        f"/api/v1/units/{unit_id}/project-contexts",
        json=body or {"code": "PA", "name": "Projeto Sintético A"},
        headers=admin,
    )
    assert created.status_code == 201, created.text
    return unit_id, created.json()["id"]


async def _prefix_in_db(db_session, context_id: str) -> str | None:
    db_session.expire_all()
    return (
        await db_session.execute(select(ProjectContext.eap_prefix).where(ProjectContext.id == context_id))
    ).scalar_one()


async def test_project_context_api_has_no_eap_prefix(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    # cliente antigo que ainda envia o campo: ignorado, nada é gravado
    unit_id, context_id = await _context(
        client, admin, {"code": "PA", "name": "Projeto Sintético A", "eapPrefix": "23"}
    )
    assert await _prefix_in_db(db_session, context_id) is None
    listed = (await client.get(f"/api/v1/units/{unit_id}/project-contexts", headers=admin)).json()["items"]
    assert listed and all("eapPrefix" not in item for item in listed)


async def test_unit_and_project_context_can_be_created_without_codes(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit = await client.post("/api/v1/units", json={"name": "Unidade sem código"}, headers=admin)
    assert unit.status_code == 201, unit.text
    assert "code" not in unit.json()

    context = await client.post(
        f"/api/v1/units/{unit.json()['id']}/project-contexts",
        json={"name": "Obra sem código"},
        headers=admin,
    )
    assert context.status_code == 201, context.text
    assert context.json()["code"] is None


async def test_patch_ignores_legacy_prefix_and_keeps_existing_value(client, auth_header, db_session) -> None:
    admin = auth_header("ADMIN")
    _, context_id = await _context(client, admin)
    # valor legado já existente no banco (de antes da P1.3.1) não é tocado
    await db_session.execute(
        update(ProjectContext).where(ProjectContext.id == context_id).values(eap_prefix="03")
    )
    await db_session.commit()

    only_prefix = await client.patch(
        f"/api/v1/project-contexts/{context_id}", json={"eapPrefix": "24"}, headers=admin
    )
    assert only_prefix.status_code == 422  # nenhum campo atualizável informado

    renamed = await client.patch(
        f"/api/v1/project-contexts/{context_id}",
        json={"name": "Projeto Sintético A2", "eapPrefix": None},
        headers=admin,
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Projeto Sintético A2" and "eapPrefix" not in renamed.json()
    assert await _prefix_in_db(db_session, context_id) == "03"
