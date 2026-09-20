from __future__ import annotations

from sqlalchemy import func, select

from app.models.equipment import Equipment, ProjectContext, Unit
from app.models.monday_import import MondayImportBatch, MondayImportRecord
from app.modules.monday_import.service import stage_import
from tests.unit.monday_xlsx_fixture import representative_xlsx


async def test_staging_is_idempotent_and_does_not_create_domain_records(db_session) -> None:
    unit = Unit(code="U-MIG", name="Unidade Migração")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="C2", name="Caldeira 2")
    db_session.add(context)
    await db_session.flush()

    fixture = representative_xlsx()
    first = await stage_import(
        db_session,
        project_context_id=context.id,
        source=fixture,
        source_name="fixture.xlsx",
    )
    second = await stage_import(
        db_session,
        project_context_id=context.id,
        source=fixture,
        source_name="outro-nome.xlsx",
    )

    assert first.created is True
    assert first.records == 2
    assert second.created is False
    assert second.batch_id == first.batch_id
    assert second.records == 2
    assert (await db_session.scalar(select(func.count(MondayImportBatch.id)))) == 1
    assert (await db_session.scalar(select(func.count(MondayImportRecord.id)))) == 2
    assert (await db_session.scalar(select(func.count(Equipment.id)))) == 0
