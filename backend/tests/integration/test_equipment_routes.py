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
    return {
        "unit": unit["id"],
        "context": context["id"],
        "area": area["id"],
        "discipline": discipline["id"],
        "work_package": work_package["id"],
    }


async def _equipment(client, auth_header, catalogs: dict[str, str], name: str = "Bomba principal"):
    return await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": catalogs["context"],
            "name": name,
            "areaId": catalogs["area"],
            "disciplineId": catalogs["discipline"],
            "workPackageId": catalogs["work_package"],
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
            "workPackageId": second["work_package"],
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
