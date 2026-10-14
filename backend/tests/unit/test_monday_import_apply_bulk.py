"""Apply Monday em duas fases (memória → escrita em lote), sem banco.

A fase em memória precisa produzir exatamente as linhas que o apply linha a linha
gravava (entidades, vínculos, mapeamentos, eventos de estado operacional e uma
auditoria por entidade, na mesma ordem); a fase de escrita precisa gravar com um
número de statements que não cresce com as linhas e falhar como plano velho se
um ExternalMapping já existir.
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects.postgresql import asyncpg as pg_asyncpg

from app.core.auth import CurrentUser
from app.core.permissions import Role
from app.models.common import utcnow
from app.models.equipment import Equipment, EquipmentComponent, EquipmentWorkPackage
from app.models.monday_import import ExternalMapping
from app.models.process import Contract
from app.models.supplier import EquipmentSupplier
from app.modules.monday_import import apply as apply_module
from app.modules.monday_import.apply import (
    PlanStaleError,
    _apply_component,
    _apply_equipment,
    _apply_sub_entity,
    _ApplyContext,
    _new_row,
    _stamp_final_entities,
    _write,
    _WriteSet,
)
from app.modules.monday_import.plan import MigrationPlan, PlanItem, equipment_identity_strategy
from app.modules.workflow.operational_status import build_operational_status_change_rows

ACTOR = CurrentUser(id="U1", email="a@example.com", name="A", role=Role.ADMIN, active=True)
_DIALECT = pg_asyncpg.dialect()


def _ctx(plan: MigrationPlan) -> _ApplyContext:
    return _ApplyContext(plan=plan, run_id="RUN", actor=ACTOR)


def _plan() -> MigrationPlan:
    return MigrationPlan(project_context_id="CTX", batch_ids=["B2", "B1"], mapping_sha256="m")


async def test_create_builds_same_rows_as_row_by_row_apply() -> None:
    plan = _plan()
    ctx = _ctx(plan)
    item = PlanItem(
        kind="equipment",
        source_key="monday-item-id:1",
        action="CREATE",
        payload={
            "name": "Bomba",
            "current_stage": 3,
            "work_package_ids": ["W1", "W2"],
            "supplier_id": "S1",
            "operational_status": "STANDBY",
        },
    )
    equipment_id = await _apply_equipment(ctx, item)
    await _apply_sub_entity(
        ctx,
        item=PlanItem(
            kind="contract", source_key="monday-item-id:1", action="CREATE", payload={"contract_number": "K"}
        ),
        model=Contract,
        equipment_id=equipment_id,
    )
    await _apply_component(
        ctx,
        item=PlanItem(
            kind="component", source_key="comp-1", action="CREATE", parent_source_key="monday-item-id:1",
            payload={"name": "Motor"},
        ),
        equipment_id=equipment_id,
    )
    writes = ctx.writes

    [equipment] = writes.inserts[Equipment]
    assert equipment["id"] == equipment_id
    assert equipment["project_context_id"] == "CTX"
    # Estado final no próprio INSERT; o INSERT antigo gravava ACTIVE e depois STANDBY.
    assert equipment["operational_status"] == "STANDBY"
    assert equipment["current_stage"] == 3
    # Mais de um WP: nenhum primário, como antes.
    assert "work_package_id" not in equipment
    assert sorted(link["work_package_id"] for link in writes.inserts[EquipmentWorkPackage]) == ["W1", "W2"]
    [supplier] = writes.inserts[EquipmentSupplier]
    assert supplier["start_stage"] == 3 and supplier["is_primary"] is True
    assert supplier["source"] == "MONDAY_CONFIRMED" and supplier["changed_by_user_id"] == "U1"
    assert [(m["source_entity_type"], m["target_entity_type"]) for m in writes.mappings] == [
        ("equipment", "Equipment"),
        ("component", "EquipmentComponent"),
    ]
    assert all(m["source_system"] == "monday" and m["raw_identity"] is None for m in writes.mappings)

    [event] = writes.status_events
    assert event["kind"] == "STANDBY_ENTERED" and event["resulting_status"] == "STANDBY"
    assert event["stage_at_event"] == 3 and event["equipment_id"] == equipment_id

    # Uma auditoria por entidade + a do estado operacional, na ordem do apply antigo.
    assert [(a["entity"], a["action"]) for a in writes.audits] == [
        ("Equipment", "migration.import"),
        ("Equipment", "migration.import"),
        ("Contract", "migration.import"),
        ("EquipmentComponent", "migration.import"),
    ]
    creation, status = writes.audits[0], writes.audits[1]
    assert creation["newData"] == {
        "name": "Bomba", "current_stage": 3, "workPackageIds": ["W1", "W2"], "supplierId": "S1",
    }
    assert creation["previousData"] is None
    assert creation["metadata"] == {
        "sourceSystem": "monday",
        "migrationRunId": "RUN",
        "batchIds": ["B1", "B2"],
        "sourceKey": "monday-item-id:1",
        "identityStrategy": equipment_identity_strategy("monday-item-id:1"),
    }
    assert status["previousData"] == {"operationalStatus": "ACTIVE"}
    assert status["newData"]["operationalStatus"] == "STANDBY"
    assert status["metadata"]["equipmentId"] == equipment_id
    assert status["metadata"]["stageAtEvent"] == 3
    assert status["metadata"]["migrationRunId"] == "RUN"
    assert writes.audits[2]["entityId"] == writes.inserts[Contract][0]["id"]


async def test_update_only_writes_changed_columns_and_swaps_supplier() -> None:
    plan = _plan()
    ctx = _ctx(plan)
    existing = SimpleNamespace(
        id="E1", name="Bomba", origin="X", current_stage=2, operational_status="ACTIVE", work_package_id="W1"
    )
    ctx.equipments["E1"] = existing  # type: ignore[assignment]
    ctx.work_package_links["E1"] = [
        SimpleNamespace(id="L1", work_package_id="W1"),  # type: ignore[list-item]
        SimpleNamespace(id="L2", work_package_id="W2"),  # type: ignore[list-item]
    ]
    ctx.active_supplier["E1"] = ("ES1", "S-old")
    item = PlanItem(
        kind="equipment",
        source_key="k1",
        action="UPDATE",
        target_entity_id="E1",
        payload={
            "name": "Bomba",  # igual: não entra no UPDATE
            "origin": "Y",
            "current_stage": 4,
            "work_package_ids": ["W2", "W3"],
            "supplier_id": "S-new",
            "operational_status": "CANCELLED",
        },
    )
    assert await _apply_equipment(ctx, item) == "E1"
    writes = ctx.writes

    [(equipment_id, changes)] = writes.updates[Equipment]
    assert equipment_id == "E1"
    assert set(changes) == {"origin", "current_stage", "work_package_id", "operational_status", "updated_at"}
    assert changes["work_package_id"] is None and changes["operational_status"] == "CANCELLED"
    assert writes.deletes[EquipmentWorkPackage] == ["L1"]
    assert [link["work_package_id"] for link in writes.inserts[EquipmentWorkPackage]] == ["W3"]
    [(ended_id, ended)] = writes.updates[EquipmentSupplier]
    assert ended_id == "ES1" and ended["end_stage"] == 4 and ended["is_primary"] is False
    [new_supplier] = writes.inserts[EquipmentSupplier]
    assert new_supplier["supplier_id"] == "S-new" and new_supplier["start_stage"] == 4

    audit, status = writes.audits
    assert audit["previousData"] == {
        "name": "Bomba", "origin": "X", "current_stage": 2, "work_package_ids": ["W1", "W2"],
        "supplier_id": "S-old",
    }
    assert status["previousData"] == {"operationalStatus": "ACTIVE"}
    [event] = writes.status_events
    assert event["kind"] == "CANCELLED" and event["stage_at_event"] == 4
    # Objeto da sessão recebe o estado gravado.
    assert (existing, changes) in writes.synced


async def test_update_without_effective_change_emits_no_update() -> None:
    ctx = _ctx(_plan())
    ctx.equipments["E1"] = SimpleNamespace(  # type: ignore[assignment]
        id="E1", name="Bomba", operational_status="ACTIVE", current_stage=0
    )
    item = PlanItem(
        kind="equipment", source_key="k", action="UPDATE", target_entity_id="E1", payload={"name": "Bomba"}
    )
    await _apply_equipment(ctx, item)
    assert Equipment not in ctx.writes.updates
    assert len(ctx.writes.audits) == 1


def test_pure_operational_status_builder_matches_record_audit_shape() -> None:
    rows = build_operational_status_change_rows(
        equipment_id="E1", previous_status="ACTIVE", kind="STANDBY_ENTERED", resulting_status="STANDBY",
        stage_at_event=2, justification=None, actor_id="U1",
    )
    assert rows.event_row["justification"] == ""
    assert rows.audit_row["action"] == "equipment.standby_entered"
    assert rows.audit_row["newData"] == {"operationalStatus": "STANDBY", "justification": None}
    assert rows.audit_row["metadata"] == {"equipmentId": "E1", "stageAtEvent": 2}


class _Result:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[str]:
        return self._ids


def _values_rows(statement: Any) -> list[Any]:
    """Linhas do `VALUES` usado no `UPDATE ... FROM` (vazio se o UPDATE não usa)."""
    for criterion in statement._where_criteria:
        data = getattr(getattr(getattr(criterion, "right", None), "table", None), "_data", None)
        if data is not None:
            return [row for chunk in data for row in chunk]  # `.data()` guarda uma lista por chamada
    return []


class _RecordingSession:
    def __init__(self, *, drop_mappings: int = 0, drop_updates: int = 0) -> None:
        self.statements: list[tuple[Any, Any]] = []
        self._drop = drop_mappings
        self._drop_updates = drop_updates

    async def execute(self, statement: Any, params: Any = None) -> _Result:
        statement.compile(dialect=_DIALECT)  # o SQL precisa compilar para Postgres/asyncpg
        self.statements.append((statement, params))
        if getattr(statement, "table", None) is ExternalMapping.__table__ and statement._returning:
            rows = statement._multi_values[0]
            return _Result([str(index) for index in range(max(0, len(rows) - self._drop))])
        if getattr(statement, "is_update", False):
            # UPDATE ... FROM (VALUES ...) RETURNING id: devolve o id de cada linha do VALUES.
            ids = [str(row[0]) for row in _values_rows(statement)]
            return _Result(ids[: max(0, len(ids) - self._drop_updates)])
        return _Result([])


async def test_write_statement_count_does_not_grow_with_rows() -> None:
    writes = _WriteSet()
    for index in range(2500):
        writes.insert(Equipment, {"project_context_id": "CTX", "name": f"E{index}"})
        writes.mappings.append(
            _new_row(
                ExternalMapping,
                {
                    "project_context_id": "CTX", "source_system": "monday", "source_entity_type": "equipment",
                    "external_id": f"k{index}", "identity_strategy": "s", "target_entity_type": "Equipment",
                    "target_entity_id": f"id{index}", "raw_identity": None,
                },
            )
        )
        writes.audit(user_id="U1", entity="Equipment", entity_id=f"id{index}", new_data={"i": index})
    for index in range(1500):
        changes = {"name": f"N{index}", "updated_at": None}
        writes.updates.setdefault(Equipment, []).append((f"U{index}", changes))
    session = _RecordingSession()
    statements = await _write(session, writes)  # type: ignore[arg-type]
    # Equipment: 3 INSERT (1000/1000/500) + 2 UPDATE FROM VALUES; mapping: 5 x 500; auditoria: 5 x 500.
    assert statements == 3 + 2 + 5 + 5
    assert statements == len(session.statements)
    update_sizes = [
        len(_values_rows(statement))
        for statement, _ in session.statements
        if getattr(statement, "is_update", False)
    ]
    assert update_sizes == [1000, 500]


async def test_existing_external_mapping_makes_plan_stale() -> None:
    writes = _WriteSet()
    writes.mapping(
        project_context_id="CTX", source_entity_type="equipment", external_id="k", identity_strategy="s",
        target_entity_type="Equipment", target_entity_id="E1",
    )
    with pytest.raises(PlanStaleError):
        await _write(_RecordingSession(drop_mappings=1), writes)  # type: ignore[arg-type]


def test_rollback_hook_still_patchable() -> None:
    # O teste de integração de rollback substitui `_apply_component` via monkeypatch.
    assert callable(apply_module._apply_component)


async def test_update_of_missing_row_makes_plan_stale() -> None:
    writes = _WriteSet()
    writes.updates[Equipment] = [("E1", {"name": "A"}), ("E2", {"name": "B"})]
    with pytest.raises(PlanStaleError):
        await _write(_RecordingSession(drop_updates=1), writes)  # type: ignore[arg-type]


async def test_supplier_end_update_requires_active_link() -> None:
    writes = _WriteSet()
    writes.updates[EquipmentSupplier] = [("ES1", {"ended_at": utcnow(), "is_primary": False})]
    session = _RecordingSession()
    await _write(session, writes)  # type: ignore[arg-type]
    [(statement, _)] = [item for item in session.statements if getattr(item[0], "is_update", False)]
    assert "ended_at IS NULL" in str(statement.compile(dialect=_DIALECT))
    # Vínculo já encerrado por outra transação: nenhuma linha atualizada -> plano velho.
    with pytest.raises(PlanStaleError):
        await _write(_RecordingSession(drop_updates=1), writes)  # type: ignore[arg-type]


async def test_audit_created_at_is_strictly_increasing_in_generation_order() -> None:
    writes = _WriteSet()
    for index in range(50):
        writes.audit(user_id="U1", entity="Equipment", entity_id=f"id{index}", new_data={"i": index})
    ids = [row["entityId"] for row in writes.audits]
    await _write(_RecordingSession(), writes)  # type: ignore[arg-type]
    created = [row["createdAt"] for row in writes.audits]
    assert [row["entityId"] for row in writes.audits] == ids
    steps = {later - earlier for earlier, later in zip(created, created[1:], strict=False)}
    assert steps == {timedelta(milliseconds=1)}


async def test_created_component_returns_its_row_id() -> None:
    ctx = _ctx(_plan())
    item = PlanItem(
        kind="component", source_key="comp-1", action="CREATE", parent_source_key="k",
        payload={"name": "Motor"},
    )
    component_id = await _apply_component(ctx, item=item, equipment_id="E1")
    assert component_id == ctx.writes.inserts[EquipmentComponent][0]["id"]
    assert component_id == ctx.writes.mappings[0]["target_entity_id"]


async def test_duplicate_source_key_in_plan_fails_before_insert() -> None:
    writes = _WriteSet()
    for _ in range(2):
        writes.mapping(
            project_context_id="CTX", source_entity_type="equipment", external_id="dup",
            identity_strategy="s", target_entity_type="Equipment", target_entity_id="E1",
        )
    session = _RecordingSession()
    with pytest.raises(RuntimeError, match="duplicada") as excinfo:
        await _write(session, writes)  # type: ignore[arg-type]
    assert not isinstance(excinfo.value, PlanStaleError)
    assert session.statements == []


async def test_stamp_final_entities_uses_one_param_set_per_resolution() -> None:
    session = _RecordingSession()
    session.sync_session = SimpleNamespace(identity_map={})  # type: ignore[attr-defined]
    plan = MigrationPlan(project_context_id="CTX", batch_ids=["B1", "B2", "B1"], mapping_sha256="m")
    await _stamp_final_entities(
        session,  # type: ignore[arg-type]
        plan=plan,
        resolutions={"k1": ("Equipment", "E1"), "k2": ("EquipmentComponent", "C1")},
    )
    [(statement, params)] = session.statements
    assert "= ANY" in str(statement.compile(dialect=_DIALECT))
    assert params == [
        {"b_batch_ids": ["B1", "B2"], "b_source_key": "k1", "b_type": "Equipment", "b_id": "E1"},
        {"b_batch_ids": ["B1", "B2"], "b_source_key": "k2", "b_type": "EquipmentComponent", "b_id": "C1"},
    ]
