"""Visão administrativa de catálogos com inativos (`include_inactive=true`).

Padrão segue só com ativos (telas operacionais); inativos só para catalogs:manage.
Somente dados sintéticos.
"""

from __future__ import annotations


async def _unit_and_contexts(client, admin) -> tuple[str, str, str]:
    unit = await client.post("/api/v1/units", json={"code": "TST", "name": "Unidade Teste"}, headers=admin)
    assert unit.status_code == 201, unit.text
    unit_id = unit.json()["id"]
    url = f"/api/v1/units/{unit_id}/project-contexts"
    first = await client.post(url, json={"code": "PA", "name": "Projeto Sintético A"}, headers=admin)
    second = await client.post(url, json={"code": "PB", "name": "Projeto Sintético B"}, headers=admin)
    assert (first.status_code, second.status_code) == (201, 201)
    return unit_id, first.json()["id"], second.json()["id"]


async def _grant(client, auth_header, role: str, unit_id: str) -> None:
    """Escopo por unidade: perfis não-ADMIN só enxergam unidades vinculadas."""
    me = await client.get("/api/v1/auth/me", headers=auth_header(role))
    assert me.status_code == 200
    response = await client.put(
        f"/api/v1/usuarios/{me.json()['id']}/units", json={"unitIds": [unit_id]}, headers=auth_header("ADMIN")
    )
    assert response.status_code == 200, response.text


def _codes(response) -> dict[str, bool]:
    assert response.status_code == 200, response.text
    return {item["code"]: item["active"] for item in response.json()["items"]}


async def test_project_context_deactivate_stays_visible_to_admin_and_reactivates(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit_id, context_a, _ = await _unit_and_contexts(client, admin)
    url = f"/api/v1/units/{unit_id}/project-contexts"

    # 4. desativar
    deactivated = await client.patch(
        f"/api/v1/project-contexts/{context_a}", json={"active": False}, headers=admin
    )
    assert deactivated.status_code == 200 and deactivated.json()["active"] is False

    # 1/8. listagem padrão (telas operacionais) não retorna inativos
    await _grant(client, auth_header, "ANALYST", unit_id)
    assert _codes(await client.get(url, headers=admin)) == {"PB": True}
    assert _codes(await client.get(url, headers=auth_header("ANALYST"))) == {"PB": True}

    # 2/5. administração vê ativo + inativo, identificado como inativo
    assert _codes(await client.get(url, params={"include_inactive": "true"}, headers=admin)) == {
        "PA": False,
        "PB": True,
    }

    # 6/7. reativar: volta a Ativo e reaparece na listagem padrão
    reactivated = await client.patch(
        f"/api/v1/project-contexts/{context_a}", json={"active": True}, headers=admin
    )
    assert reactivated.status_code == 200
    assert (reactivated.json()["active"], reactivated.json()["name"]) == (True, "Projeto Sintético A")
    assert _codes(await client.get(url, headers=admin)) == {"PA": True, "PB": True}


async def test_include_inactive_requires_catalogs_manage(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit_id, _, _ = await _unit_and_contexts(client, admin)

    # 3. sem catalogs:manage a visão administrativa é negada; a listagem padrão segue liberada
    for role in ("ANALYST", "VIEWER"):
        await _grant(client, auth_header, role, unit_id)
        headers = auth_header(role)
        denied = await client.get(
            f"/api/v1/units/{unit_id}/project-contexts", params={"include_inactive": "true"}, headers=headers
        )
        assert denied.status_code == 403, (role, denied.text)
        allowed = await client.get(f"/api/v1/units/{unit_id}/project-contexts", headers=headers)
        assert allowed.status_code == 200

    # include_inactive=false explícito é idêntico ao padrão e não exige gerenciamento
    explicit = await client.get(
        f"/api/v1/units/{unit_id}/project-contexts",
        params={"include_inactive": "false"},
        headers=auth_header("ANALYST"),
    )
    assert explicit.status_code == 200


async def test_other_catalogs_follow_the_same_rule(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    analyst = auth_header("ANALYST")
    unit_id, context_a, _ = await _unit_and_contexts(client, admin)

    area = await client.post(
        "/api/v1/areas", json={"unitId": unit_id, "name": "Área Sintética"}, headers=admin
    )
    discipline = await client.post(
        "/api/v1/disciplines", json={"code": "DS", "name": "Disciplina Sintética"}, headers=admin
    )
    work_package = await client.post(
        "/api/v1/work-packages",
        json={
            "projectContextId": context_a,
            "code": "WP-S1",
            "name": "Pacote Sintético",
            "description": "Descrição sintética da WP",
        },
        headers=admin,
    )
    spare_unit = await client.post(
        "/api/v1/units", json={"code": "TS2", "name": "Unidade Teste 2"}, headers=admin
    )
    assert {r.status_code for r in (area, discipline, work_package, spare_unit)} == {201}
    assert work_package.json()["description"] == "Descrição sintética da WP"

    await _grant(client, auth_header, "ANALYST", unit_id)
    cases = [
        ("/api/v1/areas", {"unit_id": unit_id}, f"/api/v1/areas/{area.json()['id']}"),
        ("/api/v1/disciplines", {}, f"/api/v1/disciplines/{discipline.json()['id']}"),
        (
            "/api/v1/work-packages",
            {"project_context_id": context_a},
            f"/api/v1/work-packages/{work_package.json()['id']}",
        ),
        ("/api/v1/units", {}, f"/api/v1/units/{spare_unit.json()['id']}"),
    ]
    for list_url, params, item_url in cases:
        assert (await client.patch(item_url, json={"active": False}, headers=admin)).status_code == 200
        default_ids = {
            i["id"] for i in (await client.get(list_url, params=params, headers=admin)).json()["items"]
        }
        admin_view = await client.get(list_url, params={**params, "include_inactive": "true"}, headers=admin)
        admin_ids = {i["id"]: i["active"] for i in admin_view.json()["items"]}
        target = item_url.rsplit("/", 1)[1]
        assert target not in default_ids, list_url
        assert admin_ids.get(target) is False, list_url
        denied = await client.get(list_url, params={**params, "include_inactive": "true"}, headers=analyst)
        assert denied.status_code == 403, list_url


async def test_work_package_description_can_be_edited_and_cleared(client, auth_header) -> None:
    admin = auth_header("ADMIN")
    unit_id, context_id, _ = await _unit_and_contexts(client, admin)
    created = await client.post(
        "/api/v1/work-packages",
        json={
            "projectContextId": context_id,
            "code": "CAL003",
            "name": "CAL003",
            "description": "Aeração e termometria",
        },
        headers=admin,
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/work-packages/{item_id}",
        json={"description": "Descrição revisada"},
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Descrição revisada"

    listed = await client.get(
        "/api/v1/work-packages",
        params={"project_context_id": context_id},
        headers=admin,
    )
    assert listed.json()["items"][0]["description"] == "Descrição revisada"

    cleared = await client.patch(
        f"/api/v1/work-packages/{item_id}", json={"description": None}, headers=admin
    )
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
