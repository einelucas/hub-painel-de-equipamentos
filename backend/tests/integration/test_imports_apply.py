"""P1.3 / P1.3.1 — apply + reconciliation pela API (somente dados sintéticos e PostgreSQL local)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.equipment import Equipment, EquipmentComponent
from app.models.monday_import import MondayMigrationRun
from tests.integration.test_imports_plan import mapping, plan, seed, stage, synthetic_board


async def apply(client, headers, batch_ids: str | list[str], body: dict, plan_sha: str):
    ids = [batch_ids] if isinstance(batch_ids, str) else batch_ids
    return await client.post(
        "/api/v1/imports/monday/apply",
        json={"batchIds": ids, "mapping": body, "planSha256": plan_sha},
        headers=headers,
    )


async def _count(db_session, model) -> int:
    db_session.expire_all()
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_apply_creates_audits_actor_reconciles_and_reimport_is_noop(
    client, auth_header, db_session
) -> None:
    ids = await seed(client, auth_header, db_session)
    analyst = auth_header("ANALYST")
    content = synthetic_board()
    batch = await stage(client, analyst, ids["context"], content)
    planned = (await plan(client, analyst, batch["batchId"], mapping(ids))).json()
    assert planned["canApply"] is True

    response = await apply(client, analyst, batch["batchId"], mapping(ids), planned["planSha256"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "APPLIED"
    assert (body["created"], body["updated"]) == (2, 0)  # 1 equipamento + 1 componente
    assert body["hasDivergences"] is False and body["reconciliation"]["mismatches"] == 0
    assert body["reconciliation"]["equipmentsCompared"] == 1

    equipment = (await db_session.execute(select(Equipment))).scalar_one()
    assert (equipment.name, equipment.eap_node_id, equipment.responsible_user_id) == (
        "Equipamento Sintético A",
        ids["eap"],
        ids["responsible"],
    )
    assert equipment.area_id is None  # Area legada não é mais destino da localização
    # ator vem da sessão autenticada (nunca informado pela UI)
    run = (await db_session.execute(select(MondayMigrationRun))).scalar_one()
    assert run.actor_id == ids["responsible"]  # o ANALYST autenticado
    audit_users = set(
        (await db_session.execute(select(AuditLog.userId).where(AuditLog.entityId == equipment.id))).scalars()
    )
    assert audit_users == {ids["responsible"]}

    # mesmo arquivo de novo: mesmo batch, plano todo NOOP, nada duplicado
    again = await stage(client, analyst, ids["context"], content)
    assert again["alreadyStaged"] is True and again["batchId"] == batch["batchId"]
    replanned = (await plan(client, analyst, again["batchId"], mapping(ids))).json()
    groups = {group["name"]: group for group in replanned["groups"]}
    assert (groups["Equipamentos"]["noop"], groups["Componentes"]["noop"]) == (1, 1)
    assert sum(group["create"] + group["update"] for group in replanned["groups"]) == 0
    second = await apply(client, analyst, again["batchId"], mapping(ids), replanned["planSha256"])
    assert second.status_code == 200 and (second.json()["created"], second.json()["unchanged"]) == (0, 2)
    assert await _count(db_session, Equipment) == 1
    assert await _count(db_session, EquipmentComponent) == 1


async def test_new_snapshot_updates_existing_equipment(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    first = await stage(client, admin, ids["context"], synthetic_board())
    planned = (await plan(client, admin, first["batchId"], mapping(ids))).json()
    assert (
        await apply(client, admin, first["batchId"], mapping(ids), planned["planSha256"])
    ).status_code == 200

    changed = synthetic_board(startup="2027/11/30")
    second = await stage(client, admin, ids["context"], changed)
    assert second["batchId"] != first["batchId"]
    replanned = (await plan(client, admin, second["batchId"], mapping(ids))).json()
    groups = {group["name"]: group for group in replanned["groups"]}
    assert groups["Equipamentos"]["update"] == 1 and replanned["canApply"] is True

    result = await apply(client, admin, second["batchId"], mapping(ids), replanned["planSha256"])
    assert result.status_code == 200 and result.json()["updated"] >= 1
    equipment = (await db_session.execute(select(Equipment))).scalar_one()
    await db_session.refresh(equipment)
    assert equipment.startup_at == date(2027, 11, 30)


async def test_stale_plan_hash_is_rejected_with_409(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    batch = await stage(client, admin, ids["context"], synthetic_board())
    planned = (await plan(client, admin, batch["batchId"], mapping(ids))).json()

    wrong = await apply(client, admin, batch["batchId"], mapping(ids), "0" * 64)
    assert wrong.status_code == 409 and "PLAN_STALE" in wrong.json()["error"]

    # o estado muda depois do plano: um equipamento homônimo aparece no Hub
    db_session.add(
        Equipment(project_context_id=ids["context"], name="Equipamento Sintético A", current_stage=0)
    )
    await db_session.commit()
    stale = await apply(client, admin, batch["batchId"], mapping(ids), planned["planSha256"])
    assert stale.status_code == 409
    assert await _count(db_session, Equipment) == 1  # nada importado
    assert await _count(db_session, EquipmentComponent) == 0


async def test_blocked_plan_or_invalid_mapping_never_applies(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    batch = await stage(client, admin, ids["context"], synthetic_board())

    blocked = (await plan(client, admin, batch["batchId"], {})).json()
    assert blocked["hasBlocked"] is True
    refused = await apply(client, admin, batch["batchId"], {}, blocked["planSha256"])
    assert refused.status_code == 422

    invalid = mapping(ids) | {
        "eapNodes": {"2303 - Sistema Sintético": "00000000-0000-0000-0000-000000000000"}
    }
    invalid_plan = (await plan(client, admin, batch["batchId"], invalid)).json()
    rejected = await apply(client, admin, batch["batchId"], invalid, invalid_plan["planSha256"])
    assert rejected.status_code == 422
    assert await _count(db_session, Equipment) == 0


async def test_apply_respects_unit_scope_and_permission(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    batch = await stage(client, admin, ids["context"], synthetic_board())
    planned = (await plan(client, admin, batch["batchId"], mapping(ids))).json()

    assert (
        await apply(client, auth_header("VIEWER"), batch["batchId"], mapping(ids), planned["planSha256"])
    ).status_code == 403
    analyst_id = (await client.get("/api/v1/auth/me", headers=auth_header("ANALYST"))).json()["id"]
    await client.put(f"/api/v1/usuarios/{analyst_id}/units", json={"unitIds": []}, headers=admin)
    out_of_scope = await apply(
        client, auth_header("ANALYST"), batch["batchId"], mapping(ids), planned["planSha256"]
    )
    assert out_of_scope.status_code == 404
    assert await _count(db_session, Equipment) == 0
