"""Identidade do equipamento pelo "ID do elemento" do Monday (somente dados sintéticos).

- ID presente → `monday-item-id:<id>` prevalece sobre o nome;
- renomear no Monday com o mesmo ID → mesmo Equipment (UPDATE, nunca um novo);
- ID ausente → fallback por nome normalizado;
- mesmo ID com dados incompatíveis em batches diferentes → MONDAY_ITEM_ID_CONFLICT;
- reimportação idêntica → NOOP.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.auth import CurrentUser
from app.core.permissions import Role as PermissionRole
from app.models.equipment import Equipment, ProjectContext, Unit
from app.models.monday_import import ExternalMapping
from app.models.user import Role as UserRole
from app.models.user import User
from app.modules.monday_import.apply import apply_plan
from app.modules.monday_import.mapping_file import MappingFileSchema, validate_mapping
from app.modules.monday_import.plan import build_plan
from app.modules.monday_import.service import stage_import
from tests.unit.monday_xlsx_fixture import build_xlsx

HEADER = ["Name", "Subelementos", "A.Status", "ID do elemento"]


def _board(rows: list[tuple[str, str | None]], *, status: str = "0.Nova demanda") -> bytes:
    return build_xlsx(
        [
            ["Equipamentos - Projeto Sintético"],
            ["Fase 0 - Nova Demanda"],
            HEADER,
            *[[name, None, status, item_id] for name, item_id in rows],
        ]
    )


async def _seed(db_session) -> dict[str, str]:
    unit = Unit(code="U-IDT", name="Unidade Identidade")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="C-IDT", name="Contexto Identidade")
    actor = User(name="Admin Identidade", email="admin-idt@example.com", role=UserRole.ADMIN)
    db_session.add_all([context, actor])
    await db_session.flush()
    return {"context_id": context.id, "actor_id": actor.id}


def _actor(actor_id: str) -> CurrentUser:
    return CurrentUser(
        id=actor_id, email="a@example.com", name="Actor", role=PermissionRole.ADMIN, active=True
    )


async def _plan(db_session, ids: dict[str, str], batch_ids: list[str]):
    mapping = await validate_mapping(db_session, MappingFileSchema(), project_context_id=ids["context_id"])
    return await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=batch_ids, mapping=mapping
    )


async def _stage(db_session, ids: dict[str, str], content: bytes, name: str) -> str:
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=content, source_name=name
    )
    return staged.batch_id


async def _apply(db_session, ids: dict[str, str], plan) -> None:
    await apply_plan(
        db_session, plan=plan, expected_plan_sha256=plan.plan_sha256, actor=_actor(ids["actor_id"])
    )


async def test_item_id_is_identity_and_name_is_fallback(db_session) -> None:
    ids = await _seed(db_session)
    batch = await _stage(
        db_session, ids, _board([("Bomba Com ID", "5550001"), ("Bomba Sem ID", None)]), "a.xlsx"
    )
    plan = await _plan(db_session, ids, [batch])
    assert sorted(item.source_key.split(":")[0] for item in plan.equipments) == [
        "monday-item-id",
        "normalized-name",
    ]
    await _apply(db_session, ids, plan)
    strategies = (await db_session.execute(select(ExternalMapping.identity_strategy))).scalars().all()
    assert sorted(strategies) == ["monday-item-id-v1", "normalized-name-v1"]


async def test_rename_with_same_item_id_updates_same_equipment(db_session) -> None:
    ids = await _seed(db_session)
    first = await _stage(db_session, ids, _board([("Bomba Original", "5550002")]), "a.xlsx")
    plan = await _plan(db_session, ids, [first])
    await _apply(db_session, ids, plan)
    original_id = (await db_session.execute(select(Equipment.id))).scalar_one()

    renamed = await _stage(db_session, ids, _board([("Bomba Renomeada", "5550002")]), "b.xlsx")
    plan = await _plan(db_session, ids, [renamed])
    [item] = plan.equipments
    assert (item.action, item.target_entity_id) == ("UPDATE", original_id)
    await _apply(db_session, ids, plan)

    equipment = (await db_session.execute(select(Equipment))).scalar_one()
    assert (equipment.id, equipment.name) == (original_id, "Bomba Renomeada")
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 1


async def test_same_item_id_with_incompatible_data_is_conflict(db_session) -> None:
    ids = await _seed(db_session)
    a = await _stage(db_session, ids, _board([("Bomba Um", "5550003")]), "a.xlsx")
    b = await _stage(db_session, ids, _board([("Compressor Dois", "5550003")]), "b.xlsx")
    plan = await _plan(db_session, ids, [a, b])
    [item] = plan.equipments
    assert item.action == "BLOCKED"
    assert [issue.code for issue in item.issues] == ["MONDAY_ITEM_ID_CONFLICT"]
    assert plan.has_blocked is True


async def test_reimport_same_item_ids_is_noop(db_session) -> None:
    ids = await _seed(db_session)
    content = _board([("Bomba Estável", "5550004"), ("Válvula Estável", "5550005")])
    batch = await _stage(db_session, ids, content, "a.xlsx")
    plan = await _plan(db_session, ids, [batch])
    await _apply(db_session, ids, plan)

    again = await _plan(db_session, ids, [batch])
    assert all(item.action == "NOOP" for item in again.equipments)
    await _apply(db_session, ids, again)
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 2
