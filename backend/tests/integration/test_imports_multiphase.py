"""P1.3.1 — obra exportada em vários XLSX (um por fase ocupada), importada numa só operação.

Fases 0, 1, 3, 6, 7 e 8 têm arquivo; 2, 4 e 5 estão vazias e não têm arquivo nem
batch. Somente dados sintéticos e PostgreSQL local.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.equipment import Equipment, EquipmentComponent
from app.models.monday_import import MondayImportBatch
from app.models.workflow_extras import OperationalStatusEvent
from tests.integration.test_imports_apply import apply
from tests.integration.test_imports_plan import plan, seed, stage
from tests.unit.monday_multiphase_fixture import (
    PHASE_GROUPS,
    SynthEquipment,
    multiphase_boards,
    phase_board,
)


def _mapping(ids: dict[str, str]) -> dict:
    return {
        "responsibles": {"Responsável Sintético": ids["responsible"]},
        "disciplines": {"Disciplina Sintética": ids["discipline"]},
    }


async def _count(db_session, model) -> int:
    db_session.expire_all()
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


async def _stage_all(client, headers, context_id: str, boards: dict[int, bytes] | None = None) -> list[dict]:
    # o XLSX embute data no ZIP: "mesmo arquivo" = mesmos bytes, não um novo build
    return [
        await stage(client, headers, context_id, content, f"fase-{phase}.xlsx")
        for phase, content in (boards or multiphase_boards()).items()
    ]


async def _by_name(db_session, name: str) -> Equipment:
    db_session.expire_all()
    return (await db_session.execute(select(Equipment).where(Equipment.name == name))).scalar_one()


async def test_six_phase_files_one_plan_one_apply_and_noop_reimport(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    analyst = auth_header("ANALYST")

    boards = multiphase_boards()
    staged = await _stage_all(client, analyst, ids["context"], boards)
    assert len({batch["batchId"] for batch in staged}) == 6
    assert [batch["groups"] for batch in staged] == [[group] for group in PHASE_GROUPS.values()]
    assert all(batch["canProceed"] and batch["errors"] == 0 for batch in staged)
    assert staged[0]["operationalStatuses"] == {"STANDBY": 1}
    # nenhuma fase vazia vira batch artificial
    assert await _count(db_session, MondayImportBatch) == 6

    batch_ids = [batch["batchId"] for batch in staged]
    planned = (await plan(client, analyst, batch_ids, _mapping(ids))).json()
    assert planned["canApply"] is True, planned["blocked"]
    assert sorted(planned["batchIds"]) == sorted(batch_ids)
    groups = {group["name"]: group for group in planned["groups"]}
    assert (groups["Equipamentos"]["create"], groups["Componentes"]["create"]) == (7, 7)
    assert planned["eap"] == {
        "resolved": 7, "multiple": 0, "none": 0, "notFound": 0, "create": 0, "conflict": 0, "unresolved": 0
    }

    applied = await apply(client, analyst, batch_ids, _mapping(ids), planned["planSha256"])
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["status"] == "APPLIED" and result["created"] == 14
    assert result["hasDivergences"] is False, result["reconciliation"]["divergences"]
    assert result["reconciliation"]["equipmentsCompared"] == 7

    stages = {
        equipment.name: equipment.current_stage
        for equipment in (await db_session.execute(select(Equipment))).scalars()
    }
    assert stages == {
        **{f"Equipamento Sintético F{phase}": phase for phase in PHASE_GROUPS},
        "Equipamento Sintético Standby": 0,
    }
    assert {
        equipment.eap_node_id for equipment in (await db_session.execute(select(Equipment))).scalars()
    } == {ids["eap"]}

    # Standby: estado operacional pelo evento do domínio, fase estrutural 0 (nunca 9)
    standby = await _by_name(db_session, "Equipamento Sintético Standby")
    assert (standby.operational_status, standby.current_stage) == ("STANDBY", 0)
    [event] = (
        await db_session.execute(
            select(OperationalStatusEvent).where(OperationalStatusEvent.equipment_id == standby.id)
        )
    ).scalars()
    assert (event.kind, event.resulting_status, event.actor_id) == (
        "STANDBY_ENTERED",
        "STANDBY",
        ids["responsible"],
    )
    actions = set(
        (await db_session.execute(select(AuditLog.action).where(AuditLog.entityId == standby.id))).scalars()
    )
    assert actions == {"migration.import"}  # importador não se confunde com edição humana

    # mesmo conjunto de novo: mesmos batches, plano todo NOOP, nada duplicado
    again = await _stage_all(client, analyst, ids["context"], boards)
    assert [batch["batchId"] for batch in again] == batch_ids
    assert all(batch["alreadyStaged"] for batch in again)
    replanned = (await plan(client, analyst, batch_ids, _mapping(ids))).json()
    assert sum(group["create"] + group["update"] for group in replanned["groups"]) == 0
    second = await apply(client, analyst, batch_ids, _mapping(ids), replanned["planSha256"])
    assert second.status_code == 200 and (second.json()["created"], second.json()["updated"]) == (0, 0)
    assert (await _count(db_session, Equipment), await _count(db_session, EquipmentComponent)) == (7, 7)


async def test_later_phase_export_updates_and_creates(client, auth_header, db_session) -> None:
    ids = await seed(client, auth_header, db_session)
    admin = auth_header("ADMIN")
    first_ids = [batch["batchId"] for batch in await _stage_all(client, admin, ids["context"])]
    planned = (await plan(client, admin, first_ids, _mapping(ids))).json()
    assert (await apply(client, admin, first_ids, _mapping(ids), planned["planSha256"])).status_code == 200

    # export seguinte: F7 avançou para a Fase 8, Standby voltou ao fluxo e há um equipamento novo
    later = [
        await stage(
            client,
            admin,
            ids["context"],
            phase_board(
                8,
                [
                    SynthEquipment(name="Equipamento Sintético F7"),
                    SynthEquipment(name="Equipamento Sintético Novo"),
                ],
            ),
            "fase-8-nova.xlsx",
        ),
        await stage(
            client,
            admin,
            ids["context"],
            phase_board(1, [SynthEquipment(name="Equipamento Sintético Standby")]),
            "fase-1-nova.xlsx",
        ),
    ]
    later_ids = [batch["batchId"] for batch in later]
    replanned = (await plan(client, admin, later_ids, _mapping(ids))).json()
    assert replanned["canApply"] is True, replanned["blocked"]
    equipments = {group["name"]: group for group in replanned["groups"]}["Equipamentos"]
    assert (equipments["create"], equipments["update"]) == (1, 2)

    applied = await apply(client, admin, later_ids, _mapping(ids), replanned["planSha256"])
    assert applied.status_code == 200, applied.text
    moved = await _by_name(db_session, "Equipamento Sintético F7")
    assert moved.current_stage == 8
    lifted = await _by_name(db_session, "Equipamento Sintético Standby")
    assert (lifted.operational_status, lifted.current_stage) == ("ACTIVE", 1)
    kinds = [
        event.kind
        for event in (
            await db_session.execute(
                select(OperationalStatusEvent)
                .where(OperationalStatusEvent.equipment_id == lifted.id)
                .order_by(OperationalStatusEvent.occurred_at)
            )
        ).scalars()
    ]
    assert kinds == ["STANDBY_ENTERED", "STANDBY_LIFTED"]
    assert await _count(db_session, Equipment) == 8
