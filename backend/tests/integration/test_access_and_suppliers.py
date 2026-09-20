"""Autorização por unidade, responsáveis, fornecedores e catálogos administráveis."""

from __future__ import annotations

from sqlalchemy import select

from app.models.access import UserUnitAccess
from app.models.audit import AuditLog
from app.models.supplier import EquipmentSupplier, Supplier
from tests.helpers import grant_unit


async def _unit(client, auth_header, suffix: str) -> dict[str, str]:
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
    return {"unit": unit["id"], "context": context["id"]}


async def _equipment(client, auth_header, context_id: str, name: str) -> str:
    response = await client.post(
        "/api/v1/equipments",
        json={"projectContextId": context_id, "name": name},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _user_id(client, auth_header, role: str) -> str:
    """Id do usuário de desenvolvimento correspondente ao perfil."""
    me = await client.get("/api/v1/auth/me", headers=auth_header(role))
    assert me.status_code == 200
    return str(me.json()["id"])


async def _grant(client, auth_header, role: str, unit_ids: list[str]) -> None:
    user_id = await _user_id(client, auth_header, role)
    response = await client.put(
        f"/api/v1/usuarios/{user_id}/units",
        json={"unitIds": unit_ids},
        headers=auth_header("ADMIN"),
    )
    assert response.status_code == 200, response.text


async def test_admin_sees_every_unit_and_analyst_only_assigned(client, auth_header) -> None:
    first = await _unit(client, auth_header, "AC1")
    second = await _unit(client, auth_header, "AC2")
    await _grant(client, auth_header, "ANALYST", [first["unit"]])

    admin_units = (await client.get("/api/v1/units", headers=auth_header("ADMIN"))).json()["items"]
    analyst_units = (
        await client.get("/api/v1/units", headers=auth_header("ANALYST"))
    ).json()["items"]

    admin_ids = {item["id"] for item in admin_units}
    analyst_ids = {item["id"] for item in analyst_units}
    assert {first["unit"], second["unit"]} <= admin_ids
    assert analyst_ids == {first["unit"]}


async def test_equipment_of_other_unit_is_blocked_even_with_uuid(client, auth_header) -> None:
    allowed = await _unit(client, auth_header, "OK1")
    denied = await _unit(client, auth_header, "NO1")
    await _grant(client, auth_header, "ANALYST", [allowed["unit"]])
    hidden = await _equipment(client, auth_header, denied["context"], "Equipamento oculto")

    headers = auth_header("ANALYST")
    for path in (
        f"/api/v1/equipments/{hidden}",
        f"/api/v1/equipments/{hidden}/components",
        f"/api/v1/equipments/{hidden}/processes",
        f"/api/v1/equipments/{hidden}/negotiation",
        f"/api/v1/equipments/{hidden}/available-transitions",
        f"/api/v1/equipments/{hidden}/history",
        f"/api/v1/equipments/{hidden}/suppliers",
    ):
        assert (await client.get(path, headers=headers)).status_code == 404, path

    blocked_write = await client.patch(
        f"/api/v1/equipments/{hidden}", json={"name": "Renomeado"}, headers=headers
    )
    blocked_transition = await client.post(
        f"/api/v1/equipments/{hidden}/transitions", json={"targetStage": 1}, headers=headers
    )
    assert blocked_write.status_code == 404
    assert blocked_transition.status_code == 404


async def test_listing_dashboard_and_queues_respect_scope(client, auth_header) -> None:
    allowed = await _unit(client, auth_header, "SC1")
    denied = await _unit(client, auth_header, "SC2")
    await _grant(client, auth_header, "ANALYST", [allowed["unit"]])
    visible = await _equipment(client, auth_header, allowed["context"], "Visivel escopo")
    await _equipment(client, auth_header, denied["context"], "Invisivel escopo")

    headers = auth_header("ANALYST")
    listed = (await client.get("/api/v1/equipments", headers=headers)).json()
    summary = (await client.get("/api/v1/dashboard/summary", headers=headers)).json()
    queue = (await client.get("/api/v1/queues/engineering", headers=headers)).json()

    assert [item["id"] for item in listed["items"]] == [visible]
    assert summary["totals"]["equipments"] == 1
    assert [row["equipmentId"] for row in queue["items"]] == [visible]

    forced = await client.get(
        f"/api/v1/dashboard/summary?unit_id={denied['unit']}", headers=headers
    )
    assert forced.status_code == 404


async def test_user_without_units_sees_nothing(client, auth_header) -> None:
    ids = await _unit(client, auth_header, "EMPTY")
    await _equipment(client, auth_header, ids["context"], "Fora de alcance")
    await _grant(client, auth_header, "VIEWER", [])

    headers = auth_header("VIEWER")
    assert (await client.get("/api/v1/units", headers=headers)).json()["items"] == []
    assert (await client.get("/api/v1/equipments", headers=headers)).json()["items"] == []


async def test_user_units_endpoints_are_admin_only_and_audited(
    client, auth_header, db_session
) -> None:
    ids = await _unit(client, auth_header, "ADM")
    analyst_id = await _user_id(client, auth_header, "ANALYST")

    forbidden = await client.put(
        f"/api/v1/usuarios/{analyst_id}/units",
        json={"unitIds": [ids["unit"]]},
        headers=auth_header("ANALYST"),
    )
    assert forbidden.status_code == 403

    await _grant(client, auth_header, "ANALYST", [ids["unit"]])
    current = (
        await client.get(f"/api/v1/usuarios/{analyst_id}/units", headers=auth_header("ADMIN"))
    ).json()
    assert current["allUnits"] is False
    assert [unit["id"] for unit in current["units"]] == [ids["unit"]]

    rows = (
        await db_session.execute(
            select(UserUnitAccess).where(UserUnitAccess.user_id == analyst_id)
        )
    ).scalars().all()
    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.entityId == analyst_id, AuditLog.action == "user.units_changed"
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert audits


async def test_admin_units_are_global_by_role(client, auth_header) -> None:
    ids = await _unit(client, auth_header, "GLOB")
    admin_id = await _user_id(client, auth_header, "ADMIN")
    view = (
        await client.get(f"/api/v1/usuarios/{admin_id}/units", headers=auth_header("ADMIN"))
    ).json()
    assert view["allUnits"] is True
    assert ids["unit"] in {unit["id"] for unit in view["units"]}

    rejected = await client.put(
        f"/api/v1/usuarios/{admin_id}/units",
        json={"unitIds": [ids["unit"]]},
        headers=auth_header("ADMIN"),
    )
    assert rejected.status_code == 422


async def test_responsibles_are_scoped_and_assignable(client, auth_header) -> None:
    allowed = await _unit(client, auth_header, "RESP")
    other = await _unit(client, auth_header, "RESP2")
    analyst_id = await _user_id(client, auth_header, "ANALYST")
    await _grant(client, auth_header, "ANALYST", [allowed["unit"]])

    listed = (
        await client.get(
            f"/api/v1/responsibles?unit_id={allowed['unit']}", headers=auth_header("ANALYST")
        )
    ).json()["items"]
    assert analyst_id in {item["id"] for item in listed}

    accepted = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": allowed["context"],
            "name": "Com responsavel",
            "responsibleUserId": analyst_id,
        },
        headers=auth_header("ADMIN"),
    )
    assert accepted.status_code == 201
    assert accepted.json()["responsibleUser"]["id"] == analyst_id

    # O analista não tem acesso à outra unidade, então não pode ser responsável lá.
    rejected = await client.post(
        "/api/v1/equipments",
        json={
            "projectContextId": other["context"],
            "name": "Responsavel invalido",
            "responsibleUserId": analyst_id,
        },
        headers=auth_header("ADMIN"),
    )
    assert rejected.status_code == 422
    assert "acesso" in rejected.json()["error"].lower()


async def test_equipments_filter_by_responsible(client, auth_header) -> None:
    ids = await _unit(client, auth_header, "FRESP")
    analyst_id = await _user_id(client, auth_header, "ANALYST")
    await _grant(client, auth_header, "ANALYST", [ids["unit"]])
    target = (
        await client.post(
            "/api/v1/equipments",
            json={
                "projectContextId": ids["context"],
                "name": "Do analista",
                "responsibleUserId": analyst_id,
            },
            headers=auth_header("ADMIN"),
        )
    ).json()["id"]
    await _equipment(client, auth_header, ids["context"], "Sem responsavel")

    filtered = (
        await client.get(
            f"/api/v1/equipments?responsible_user_id={analyst_id}", headers=auth_header("ADMIN")
        )
    ).json()
    assert [item["id"] for item in filtered["items"]] == [target]


async def test_supplier_crud_and_tax_id_uniqueness(client, auth_header, db_session) -> None:
    created = await client.post(
        "/api/v1/suppliers",
        json={"legalName": "Fornecedora Teste LTDA", "taxId": "11222333000199"},
        headers=auth_header("ANALYST"),
    )
    assert created.status_code == 201
    supplier_id = created.json()["id"]

    duplicated = await client.post(
        "/api/v1/suppliers",
        json={"legalName": "Outra Razao", "taxId": "11222333000199"},
        headers=auth_header("ANALYST"),
    )
    assert duplicated.status_code == 409

    # Sem documento informado não há restrição de duplicidade.
    for name in ("Sem doc A", "Sem doc B"):
        response = await client.post(
            "/api/v1/suppliers", json={"legalName": name}, headers=auth_header("ANALYST")
        )
        assert response.status_code == 201

    deactivated = await client.patch(
        f"/api/v1/suppliers/{supplier_id}",
        json={"active": False, "tradeName": "Apelido"},
        headers=auth_header("ANALYST"),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False

    # Desativar não apaga o registro mestre.
    assert await db_session.get(Supplier, supplier_id) is not None
    listed = (await client.get("/api/v1/suppliers", headers=auth_header("VIEWER"))).json()
    assert supplier_id not in {item["id"] for item in listed["items"]}
    with_inactive = (
        await client.get("/api/v1/suppliers?includeInactive=true", headers=auth_header("VIEWER"))
    ).json()
    assert supplier_id in {item["id"] for item in with_inactive["items"]}

    audits = (
        await db_session.execute(select(AuditLog).where(AuditLog.entityId == supplier_id))
    ).scalars().all()
    assert {audit.action for audit in audits} >= {"supplier.create", "supplier.update"}


async def test_viewer_cannot_write_supplier(client, auth_header) -> None:
    response = await client.post(
        "/api/v1/suppliers", json={"legalName": "Bloqueada"}, headers=auth_header("VIEWER")
    )
    assert response.status_code == 403


async def test_equipment_supplier_link_keeps_single_primary(client, auth_header, db_session) -> None:
    ids = await _unit(client, auth_header, "SUP")
    await grant_unit(client, auth_header, ids["unit"])
    equipment_id = await _equipment(client, auth_header, ids["context"], "Com fornecedores")
    first = (
        await client.post(
            "/api/v1/suppliers", json={"legalName": "Primeira SA"}, headers=auth_header("ANALYST")
        )
    ).json()["id"]
    second = (
        await client.post(
            "/api/v1/suppliers", json={"legalName": "Segunda SA"}, headers=auth_header("ANALYST")
        )
    ).json()["id"]

    linked = await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": first, "role": "Fabricante", "isPrimary": True},
        headers=auth_header("ANALYST"),
    )
    assert linked.status_code == 201
    assert linked.json()["isPrimary"] is True

    repeated = await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": first},
        headers=auth_header("ANALYST"),
    )
    assert repeated.status_code == 409

    await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": second},
        headers=auth_header("ANALYST"),
    )
    promoted = await client.patch(
        f"/api/v1/equipments/{equipment_id}/suppliers/{second}",
        json={"isPrimary": True},
        headers=auth_header("ANALYST"),
    )
    assert promoted.status_code == 200

    links = (
        await db_session.execute(
            select(EquipmentSupplier).where(EquipmentSupplier.equipment_id == equipment_id)
        )
    ).scalars().all()
    primaries = [link.supplier_id for link in links if link.is_primary]
    assert primaries == [second]


async def test_unlink_supplier_keeps_master_record(client, auth_header, db_session) -> None:
    ids = await _unit(client, auth_header, "UNL")
    await grant_unit(client, auth_header, ids["unit"])
    equipment_id = await _equipment(client, auth_header, ids["context"], "Desvincular")
    supplier_id = (
        await client.post(
            "/api/v1/suppliers", json={"legalName": "Permanece SA"}, headers=auth_header("ANALYST")
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": supplier_id},
        headers=auth_header("ANALYST"),
    )

    removed = await client.delete(
        f"/api/v1/equipments/{equipment_id}/suppliers/{supplier_id}",
        headers=auth_header("ANALYST"),
    )
    assert removed.status_code == 204

    remaining = (
        await client.get(
            f"/api/v1/equipments/{equipment_id}/suppliers", headers=auth_header("VIEWER")
        )
    ).json()
    assert remaining["items"] == []
    assert await db_session.get(Supplier, supplier_id) is not None


async def test_procurement_queue_exposes_primary_supplier(client, auth_header) -> None:
    ids = await _unit(client, auth_header, "QSUP")
    await grant_unit(client, auth_header, ids["unit"])
    equipment_id = await _equipment(client, auth_header, ids["context"], "Fila com fornecedor")
    supplier_id = (
        await client.post(
            "/api/v1/suppliers",
            json={"legalName": "Principal SA", "tradeName": "Principal"},
            headers=auth_header("ANALYST"),
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/equipments/{equipment_id}/suppliers",
        json={"supplierId": supplier_id, "isPrimary": True},
        headers=auth_header("ANALYST"),
    )

    steps = {
        2: ("negotiation", {"equalized": True}),
        3: ("negotiation", {"negotiatedAt": "2026-02-10"}),
        4: ("legal", {"openedAt": "2026-02-12", "ticketNumber": "TK-QSUP"}),
        5: ("legal", {"draftPrepared": True, "draftApproved": True}),
        6: ("contract", {"contractNumber": "CT-QSUP", "executedAt": "2026-03-01"}),
    }
    for stage in range(1, 7):
        payload = steps.get(stage)
        if payload:
            resource, body = payload
            await client.patch(
                f"/api/v1/equipments/{equipment_id}/{resource}",
                json=body,
                headers=auth_header("ANALYST"),
            )
        moved = await client.post(
            f"/api/v1/equipments/{equipment_id}/transitions",
            json={"targetStage": stage},
            headers=auth_header("ANALYST"),
        )
        assert moved.status_code == 200, moved.text

    row = (
        await client.get(
            f"/api/v1/queues/procurement?unit_id={ids['unit']}", headers=auth_header("ADMIN")
        )
    ).json()["items"][0]
    assert row["primarySupplier"]["legalName"] == "Principal SA"


async def test_catalog_patch_deactivates_and_audits(client, auth_header, db_session) -> None:
    ids = await _unit(client, auth_header, "CAT")
    area = (
        await client.post(
            "/api/v1/areas",
            json={"unitId": ids["unit"], "name": "Área original"},
            headers=auth_header("ADMIN"),
        )
    ).json()

    forbidden = await client.patch(
        f"/api/v1/areas/{area['id']}", json={"name": "X"}, headers=auth_header("ANALYST")
    )
    assert forbidden.status_code == 403

    renamed = await client.patch(
        f"/api/v1/areas/{area['id']}",
        json={"name": "Área renomeada"},
        headers=auth_header("ADMIN"),
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Área renomeada"

    disabled = await client.patch(
        f"/api/v1/areas/{area['id']}", json={"active": False}, headers=auth_header("ADMIN")
    )
    assert disabled.status_code == 200
    listed = (
        await client.get(f"/api/v1/areas?unit_id={ids['unit']}", headers=auth_header("ADMIN"))
    ).json()
    assert area["id"] not in {item["id"] for item in listed["items"]}

    audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.entityId == area["id"], AuditLog.action == "catalog.update"
            )
        )
    ).scalars().all()
    assert len(audits) >= 2


async def test_catalog_patch_rejects_duplicate_code(client, auth_header) -> None:
    headers = auth_header("ADMIN")
    first = (
        await client.post(
            "/api/v1/disciplines", json={"code": "D-DUP1", "name": "Uma"}, headers=headers
        )
    ).json()
    await client.post(
        "/api/v1/disciplines", json={"code": "D-DUP2", "name": "Outra"}, headers=headers
    )
    clash = await client.patch(
        f"/api/v1/disciplines/{first['id']}", json={"code": "D-DUP2"}, headers=headers
    )
    assert clash.status_code == 409
