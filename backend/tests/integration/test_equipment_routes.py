"""Fluxo vertical de catálogos, equipamentos, componentes e resumo."""

from __future__ import annotations

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.equipment import WorkflowTransition
from tests.helpers import grant_unit


async def _catalogs(client, auth_header, suffix: str = "A") -> dict[str, str]:
    headers = auth_header("ADMIN")
    unit = (
        await client.post(
            "/api/v1/units",
            json={"code": f"U-{suffix}", "name": f"Unidade {suffix}"},
            headers=headers,
        )
    ).json()
    context = (
        await client.post(
            f"/api/v1/units/{unit['id']}/project-contexts",
            json={"code": f"CTX-{suffix}", "name": f"Contexto {suffix}"},
            headers=headers,
        )
    ).json()
    await grant_unit(client, auth_header, unit["id"])
    area = (
        await client.post(
            "/api/v1/areas",
            json={"unitId": unit["id"], "name": f"Área {suffix}"},
            headers=headers,
        )
    ).json()
    discipline = (
        await client.post(
            "/api/v1/disciplines",
            json={"code": f"D-{suffix}", "name": f"Disciplina {suffix}"},
            headers=headers,
        )
    ).json()
    work_package = (
        await client.post(
            "/api/v1/work-packages",
            json={
                "projectContextId": context["id"],
                "code": f"WP-{suffix}",
                "name": f"Pacote {suffix}",
            },
            headers=headers,
        )
    ).json()
    work_package_2 = (
        await client.post(
            "/api/v1/work-packages",
            json={
                "projectContextId": context["id"],
                "code": f"WP-{suffix}-2",
                "name": f"Pacote {suffix} 2",
            },
            headers=headers,
        )
    ).json()
    return {
        "unit": unit["id"],
        "context": context["id"],
        "area": area["id"],
        "discipline": discipline["id"],
        "work_package": work_package["id"],
        "work_package_2": work_package_2["id"],
    }


async def _equipment(client, auth_header, catalogs: dict[str, str], name: str = "Bomba principal"):
    return await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": name,
            "areaId": catalogs["area"],
            "disciplineId": catalogs["discipline"],
            "workPackageIds": [catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )


async def test_catalog_creation_and_read_permissions(client, auth_header) -> None:
    forbidden = await client.post(
        "/api/v1/units",
        json={"code": "NO", "name": "Sem permissão"},
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    ids = await _catalogs(client, auth_header)
    units = await client.get("/api/v1/units", headers=auth_header("VIEWER"))
    contexts = await client.get(
        f"/api/v1/units/{ids['unit']}/project-contexts", headers=auth_header("VIEWER")
    )
    assert units.status_code == 200
    assert units.json()["items"][0]["id"] == ids["unit"]
    assert contexts.json()["items"][0]["id"] == ids["context"]


async def test_equipment_defaults_filters_search_and_pagination(client, auth_header) -> None:
    first = await _catalogs(client, auth_header, "A")
    second = await _catalogs(client, auth_header, "B")
    created = await _equipment(client, auth_header, first)
    await _equipment(client, auth_header, first, "Ventilador auxiliar")
    await _equipment(client, auth_header, second, "Equipamento externo")
    assert created.status_code == 201
    assert created.json()["currentStage"] == 0

    by_unit = await client.get(
        f"/api/v1/equipments?unit_id={first['unit']}&pageSize=1", headers=auth_header("VIEWER")
    )
    assert by_unit.json()["pagination"] == {
        "page": 1,
        "pageSize": 1,
        "total": 2,
        "totalPages": 2,
    }
    equipment_id = created.json()["id"]
    specific = await client.get(
        f"/api/v1/equipments?equipment_id={equipment_id}", headers=auth_header("VIEWER")
    )
    searched = await client.get(
        "/api/v1/equipments?search=ventilador", headers=auth_header("VIEWER")
    )
    assert [item["id"] for item in specific.json()["items"]] == [equipment_id]
    assert searched.json()["items"][0]["name"] == "Ventilador auxiliar"


async def test_cross_catalog_relations_are_validated(client, auth_header) -> None:
    first = await _catalogs(client, auth_header, "A")
    second = await _catalogs(client, auth_header, "B")
    wrong_area = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": first["context"],
            "name": "Área incompatível",
            "areaId": second["area"],
        },
        headers=auth_header("ANALYST"),
    )
    wrong_package = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": first["context"],
            "name": "Pacote incompatível",
            "workPackageIds": [second["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert wrong_area.status_code == 422
    assert wrong_package.status_code == 422


async def test_component_summary_audit_and_stage_history(client, auth_header, db_session) -> None:
    catalogs = await _catalogs(client, auth_header)
    created = await _equipment(client, auth_header, catalogs)
    equipment_id = created.json()["id"]
    component = await client.post(
        f"/api/v1/equipments/{equipment_id}/components",
        json={"name": "Motor", "leadTimeDays": 30},
        headers=auth_header("ANALYST"),
    )
    assert component.status_code == 201
    listed = await client.get(
        f"/api/v1/equipments/{equipment_id}/components", headers=auth_header("VIEWER")
    )
    assert [item["name"] for item in listed.json()["items"]] == ["Motor"]

    changed = await client.post(
        f"/api/v1/equipments/{equipment_id}/transitions",
        json={"targetStage": 1},
        headers=auth_header("ANALYST"),
    )
    assert changed.status_code == 200
    assert changed.json()["currentStage"] == 1

    detail = await client.get(
        f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER")
    )
    assert detail.json()["history"][0]["fromStage"] == 0
    assert detail.json()["history"][0]["toStage"] == 1
    summary = await client.get(
        f"/api/v1/dashboard/summary?unit_id={catalogs['unit']}&equipment_id={equipment_id}",
        headers=auth_header("VIEWER"),
    )
    assert summary.json()["totals"]["equipments"] == 1
    assert summary.json()["totals"]["components"] == 1

    transitions = (
        await db_session.execute(
            select(WorkflowTransition).where(WorkflowTransition.equipment_id == equipment_id)
        )
    ).scalars().all()
    audits = (
        await db_session.execute(select(AuditLog).where(AuditLog.entityId == equipment_id))
    ).scalars().all()
    assert len(transitions) == 1
    assert {audit.action for audit in audits} >= {
        "equipment.create",
        "equipment.stage_changed",
    }


async def test_viewer_cannot_write_equipment(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    response = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": catalogs["context"], "name": "Bloqueado"},
        headers=auth_header("VIEWER"),
    )
    assert response.status_code == 403


# --- N:N Work Packages -------------------------------------------------


async def test_equipment_create_with_zero_work_packages(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    response = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": catalogs["context"], "name": "Sem pacote", "workPackageIds": []},
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["workPackages"] == []
    assert body["workPackage"] is None


async def test_equipment_create_with_one_work_package(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    response = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Um pacote",
            "workPackageIds": [catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 201
    body = response.json()
    assert [item["id"] for item in body["workPackages"]] == [catalogs["work_package"]]
    # Contrato legado nunca é escolhido automaticamente pelo create/update.
    assert body["workPackage"] is None


async def test_equipment_create_with_multiple_work_packages(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    response = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Vários pacotes",
            "workPackageIds": [catalogs["work_package_2"], catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 201
    body = response.json()
    # Ordenação determinística por code, independente da ordem enviada.
    codes = [item["code"] for item in body["workPackages"]]
    assert codes == sorted(codes)
    assert {item["id"] for item in body["workPackages"]} == {
        catalogs["work_package"],
        catalogs["work_package_2"],
    }


async def test_equipment_create_rejects_duplicate_work_package_ids(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    response = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Duplicado",
            "workPackageIds": [catalogs["work_package"], catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 422


async def test_equipment_create_rejects_unknown_work_package(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    response = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Inexistente",
            "workPackageIds": ["00000000-0000-0000-0000-000000000000"],
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 422


async def test_equipment_create_rejects_inactive_work_package(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    deactivated = await client.patch(
        f"/api/v1/work-packages/{catalogs['work_package']}",
        json={"active": False},
        headers=auth_header("ADMIN"),
    )
    assert deactivated.status_code == 200
    response = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Pacote inativo",
            "workPackageIds": [catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 422


async def test_equipment_create_rejects_work_package_from_other_context(client, auth_header) -> None:
    first = await _catalogs(client, auth_header, "A")
    second = await _catalogs(client, auth_header, "B")
    response = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": first["context"],
            "name": "Contexto errado",
            "workPackageIds": [second["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    assert response.status_code == 422


async def test_equipment_update_adds_and_removes_and_replaces_work_packages(
    client, auth_header, db_session
) -> None:
    """Cenário do enunciado: [A, B] -> [A, C] mantém A, remove B, adiciona C."""
    catalogs = await _catalogs(client, auth_header)
    third = (
        await client.post(
            "/api/v1/work-packages",
            json={"projectContextId": catalogs["context"], "code": "WP-A-3", "name": "Pacote A 3"},
            headers=auth_header("ADMIN"),
        )
    ).json()["id"]

    created = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Equipamento sincronizado",
            "workPackageIds": [catalogs["work_package"], catalogs["work_package_2"]],
        },
        headers=auth_header("ANALYST"),
    )
    equipment_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"workPackageIds": [catalogs["work_package"], third]},
        headers=auth_header("ANALYST"),
    )
    assert updated.status_code == 200
    ids = {item["id"] for item in updated.json()["workPackages"]}
    assert ids == {catalogs["work_package"], third}
    assert catalogs["work_package_2"] not in ids

    # O WorkPackage removido do vínculo continua existindo no catálogo.
    still_exists = await client.get(
        f"/api/v1/work-packages?project_context_id={catalogs['context']}",
        headers=auth_header("VIEWER"),
    )
    assert catalogs["work_package_2"] in {item["id"] for item in still_exists.json()["items"]}


async def test_equipment_update_empty_list_removes_all_work_packages(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    created = await _equipment(client, auth_header, catalogs)
    equipment_id = created.json()["id"]
    assert created.json()["workPackages"] != []

    updated = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"workPackageIds": []},
        headers=auth_header("ANALYST"),
    )
    assert updated.status_code == 200
    assert updated.json()["workPackages"] == []


async def test_equipment_patch_without_work_package_ids_preserves_links(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    created = await _equipment(client, auth_header, catalogs)
    equipment_id = created.json()["id"]
    original_ids = {item["id"] for item in created.json()["workPackages"]}
    assert original_ids

    updated = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"criticality": "Curto <90"},
        headers=auth_header("ANALYST"),
    )
    assert updated.status_code == 200
    assert {item["id"] for item in updated.json()["workPackages"]} == original_ids


async def test_equipment_update_rejects_duplicate_and_wrong_context_work_packages(
    client, auth_header
) -> None:
    first = await _catalogs(client, auth_header, "A")
    second = await _catalogs(client, auth_header, "B")
    created = await _equipment(client, auth_header, first)
    equipment_id = created.json()["id"]

    duplicate = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"workPackageIds": [first["work_package"], first["work_package"]]},
        headers=auth_header("ANALYST"),
    )
    assert duplicate.status_code == 422

    wrong_context = await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"workPackageIds": [second["work_package"]]},
        headers=auth_header("ANALYST"),
    )
    assert wrong_context.status_code == 422


async def test_get_equipment_detail_returns_all_linked_work_packages(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    created = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Detalhe completo",
            "workPackageIds": [catalogs["work_package_2"], catalogs["work_package"]],
        },
        headers=auth_header("ANALYST"),
    )
    equipment_id = created.json()["id"]

    detail = await client.get(f"/api/v1/equipments/{equipment_id}", headers=auth_header("VIEWER"))
    assert detail.status_code == 200
    ids = {item["id"] for item in detail.json()["equipment"]["workPackages"]}
    assert ids == {catalogs["work_package"], catalogs["work_package_2"]}

    listed = await client.get(
        f"/api/v1/equipments?equipment_id={equipment_id}", headers=auth_header("VIEWER")
    )
    assert {item["id"] for item in listed.json()["items"][0]["workPackages"]} == ids


async def test_work_package_changes_are_audited(client, auth_header, db_session) -> None:
    catalogs = await _catalogs(client, auth_header)
    created = await _equipment(client, auth_header, catalogs)
    equipment_id = created.json()["id"]

    await client.patch(
        f"/api/v1/equipments/{equipment_id}",
        json={"workPackageIds": [catalogs["work_package_2"]]},
        headers=auth_header("ANALYST"),
    )

    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.entityId == equipment_id, AuditLog.action == "equipment.update"
            )
        )
    ).scalars().all()
    matching = [
        audit
        for audit in audits
        if audit.previousData and "work_package_ids" in audit.previousData
    ]
    assert matching, "esperava um AuditLog de equipment.update com work_package_ids"
    entry = matching[0]
    assert entry.previousData["work_package_ids"] == [catalogs["work_package"]]
    assert entry.newData["work_package_ids"] == [catalogs["work_package_2"]]


async def test_engineering_queue_returns_all_work_packages(client, auth_header) -> None:
    catalogs = await _catalogs(client, auth_header)
    await grant_unit(client, auth_header, catalogs["unit"])
    await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": "Fila engenharia",
            "workPackageIds": [catalogs["work_package"], catalogs["work_package_2"]],
        },
        headers=auth_header("ANALYST"),
    )
    response = await client.get(
        f"/api/v1/queues/engineering?unit_id={catalogs['unit']}", headers=auth_header("VIEWER")
    )
    assert response.status_code == 200
    row = response.json()["items"][0]
    assert {item["id"] for item in row["workPackages"]} == {
        catalogs["work_package"],
        catalogs["work_package_2"],
    }
