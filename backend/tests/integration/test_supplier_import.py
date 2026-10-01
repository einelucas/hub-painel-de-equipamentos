"""Carga de fornecedores LEM F2 contra o Postgres dedicado de testes."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.auth import CurrentUser
from app.core.permissions import Role as PermissionRole
from app.models.audit import AuditLog
from app.models.equipment import Equipment, ProjectContext, Unit
from app.models.monday_import import ExternalMapping
from app.models.supplier import EquipmentSupplier, Supplier, SupplierAlias
from app.models.user import Role as UserRole
from app.models.user import User
from app.modules.monday_import.mappings import SOURCE_SYSTEM, provisional_equipment_key
from app.modules.supplier_import.database import (
    SupplierImportBlockedError,
    apply_supplier_import,
    reconcile_with_database,
    resolve_project_context,
)
from app.modules.supplier_import.plan import build_supplier_import_plan
from app.modules.supplier_import.workbook import load_supplier_workbook
from tests.unit.supplier_workbook_fixture import representative_supplier_workbook

_IMPORTED = ("Secador de grãos", "Elevador de canecas", "Decanter")


async def _seed(db_session) -> dict[str, object]:
    unit = Unit(code="LEM", name="Luís Eduardo Magalhães")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="F2", name="Fase 2")
    actor = User(name="Admin carga", email="admin-carga@example.com", role=UserRole.ADMIN)
    db_session.add_all([context, actor])
    await db_session.flush()
    equipments: dict[str, str] = {}
    for name in _IMPORTED:
        item = Equipment(project_context_id=context.id, name=name, current_stage=0)
        db_session.add(item)
        await db_session.flush()
        db_session.add(
            ExternalMapping(
                project_context_id=context.id,
                source_system=SOURCE_SYSTEM,
                source_entity_type="equipment",
                external_id=provisional_equipment_key(name),
                identity_strategy="normalized-name-v1",
                target_entity_type="Equipment",
                target_entity_id=item.id,
            )
        )
        equipments[name] = item.id
    await db_session.commit()
    actor_user = CurrentUser(
        id=actor.id, email=actor.email, name=actor.name, role=PermissionRole.ADMIN, active=True
    )
    return {"context_id": context.id, "actor": actor_user, "equipments": equipments}


def _plan():
    workbook = load_supplier_workbook(representative_supplier_workbook(), source_name="t.xlsx")
    return build_supplier_import_plan(workbook, alias_context="LEM_F2", expected=None)


async def _count(db_session, column) -> int:
    return (await db_session.execute(select(func.count(column)))).scalar_one()


async def test_dry_run_writes_nothing_and_apply_is_idempotent(db_session) -> None:
    ids = await _seed(db_session)
    context_id = await resolve_project_context(db_session, unit_code="LEM", context_code="F2")
    assert context_id == ids["context_id"]
    plan = _plan()

    preview = await reconcile_with_database(db_session, plan, project_context_id=context_id)
    assert preview.count("suppliers", "CREATE") == 2
    assert preview.count("aliases", "CREATE") == 3
    assert preview.count("links", "CREATE") == 3
    assert await _count(db_session, Supplier.id) == 0
    assert await _count(db_session, SupplierAlias.id) == 0

    first = await apply_supplier_import(db_session, plan, project_context_id=context_id, actor=ids["actor"])
    assert first.count("suppliers", "CREATE") == 2

    suppliers = {s.corporate_code: s for s in (await db_session.scalars(select(Supplier))).all()}
    assert sorted(suppliers) == ["13974", "3026"]
    assert suppliers["13974"].legal_name == "AGI BRASIL INDUSTRIA LTDA"
    assert suppliers["3026"].tax_id is None
    aliases = (await db_session.scalars(select(SupplierAlias).order_by(SupplierAlias.alias))).all()
    assert [(a.alias, a.supplier_id, a.source, a.context) for a in aliases] == [
        ("AGI BRASIL (Grãos)", suppliers["13974"].id, "MONDAY", "LEM_F2"),
        ("AGI BRASIL (MM)", suppliers["13974"].id, "MONDAY", "LEM_F2"),
        ("FLOTTWEG", suppliers["3026"].id, "MONDAY", "LEM_F2"),
    ]
    equipments: dict[str, str] = ids["equipments"]  # type: ignore[assignment]
    links = {
        link.equipment_id: link.supplier_id
        for link in (await db_session.scalars(select(EquipmentSupplier))).all()
    }
    assert links == {
        equipments["Secador de grãos"]: suppliers["13974"].id,
        equipments["Elevador de canecas"]: suppliers["13974"].id,
        equipments["Decanter"]: suppliers["3026"].id,
    }
    audit_actions = {row.action for row in (await db_session.scalars(select(AuditLog))).all()}
    assert {"supplier.import_create", "equipment_supplier.import_link"} <= audit_actions

    second = await apply_supplier_import(
        db_session, _plan(), project_context_id=context_id, actor=ids["actor"]
    )
    assert second.count("suppliers", "NOOP") == 2
    assert second.count("aliases", "NOOP") == 3
    assert second.count("links", "NOOP") == 3
    assert await _count(db_session, Supplier.id) == 2
    assert await _count(db_session, SupplierAlias.id) == 3
    assert await _count(db_session, EquipmentSupplier.id) == 3


async def test_existing_supplier_is_updated_by_corporate_code_not_duplicated(db_session) -> None:
    ids = await _seed(db_session)
    db_session.add(Supplier(corporate_code="13974", legal_name="AGI (nome antigo)", tax_id=None))
    await db_session.commit()

    result = await apply_supplier_import(
        db_session, _plan(), project_context_id=ids["context_id"], actor=ids["actor"]
    )

    update = next(a for a in result.suppliers if a.corporate_code == "13974")
    assert update.action == "UPDATE"
    assert update.changes == {"legal_name": "AGI BRASIL INDUSTRIA LTDA", "tax_id": "11111111000111"}
    rows = (await db_session.scalars(select(Supplier).where(Supplier.corporate_code == "13974"))).all()
    assert len(rows) == 1
    assert rows[0].legal_name == "AGI BRASIL INDUSTRIA LTDA"


async def test_conflicts_block_the_whole_load_and_missing_equipment_is_reported(db_session) -> None:
    ids = await _seed(db_session)
    other = Supplier(legal_name="Fornecedor manual", tax_id=None)
    db_session.add(other)
    await db_session.flush()
    equipments: dict[str, str] = ids["equipments"]  # type: ignore[assignment]
    db_session.add(
        EquipmentSupplier(equipment_id=equipments["Decanter"], supplier_id=other.id, is_primary=True)
    )
    await db_session.commit()

    preview = await reconcile_with_database(db_session, _plan(), project_context_id=ids["context_id"])
    assert [c for c in preview.conflicts if "Decanter" in c]
    with pytest.raises(SupplierImportBlockedError):
        await apply_supplier_import(
            db_session, _plan(), project_context_id=ids["context_id"], actor=ids["actor"]
        )
    await db_session.rollback()
    assert await _count(db_session, SupplierAlias.id) == 0
    assert await _count(db_session, Supplier.id) == 1

    no_context = await reconcile_with_database(db_session, _plan(), project_context_id=None)
    assert no_context.count("links", "EQUIPMENT_NOT_FOUND") == 3
    assert no_context.conflicts == []
