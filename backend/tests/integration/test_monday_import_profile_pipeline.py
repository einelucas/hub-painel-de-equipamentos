"""Motor genérico: XLSX sintético → parser(profile) → stage → mapping → plan → apply → reconcile.

Somente dados sintéticos e o PostgreSQL local de testes.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.auth import CurrentUser
from app.core.permissions import Role as PermissionRole
from app.models.access import UserUnitAccess
from app.models.equipment import (
    Area,
    Discipline,
    Equipment,
    EquipmentComponent,
    ProjectContext,
    Unit,
    WorkPackage,
)
from app.models.monday_import import ExternalMapping, MondayImportBatch
from app.models.user import Role as UserRole
from app.models.user import User
from app.modules.monday_import.apply import apply_plan
from app.modules.monday_import.domain_reconciliation import reconcile_domain
from app.modules.monday_import.mapping_file import MappingFileSchema, validate_mapping
from app.modules.monday_import.plan import build_plan
from app.modules.monday_import.service import StagedWithDifferentProfileError, stage_import
from tests.unit.monday_profile_fixture import layout_a_xlsx, layout_b_xlsx, profile_a, profile_b


async def _seed(db_session) -> dict[str, str]:
    unit = Unit(code="U-SINT", name="Unidade Sintética")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="CTX-SINT", name="Projeto Sintético B")
    db_session.add(context)
    await db_session.flush()
    area = Area(unit_id=unit.id, name="Área Sintética")
    discipline = Discipline(code="D-SINT", name="Disciplina Sintética")
    wp1 = WorkPackage(code="WP-S1", name="Pacote Sintético 1")
    wp2 = WorkPackage(code="WP-S2", name="Pacote Sintético 2")
    db_session.add_all([area, discipline, wp1, wp2])
    await db_session.flush()
    responsible = User(name="Usuário A", email="usuario.a@example.test", role=UserRole.ANALYST)
    actor = User(name="Administrador Sintético", email="admin.sintetico@example.test", role=UserRole.ADMIN)
    db_session.add_all([responsible, actor])
    await db_session.flush()
    db_session.add(UserUnitAccess(user_id=responsible.id, unit_id=unit.id))
    await db_session.flush()
    return {
        "context_id": context.id,
        "area_id": area.id,
        "discipline_id": discipline.id,
        "wp1": wp1.id,
        "wp2": wp2.id,
        "responsible_id": responsible.id,
        "actor_id": actor.id,
    }


def _mapping(ids: dict[str, str]) -> MappingFileSchema:
    # O profile não carrega IDs: valores da origem -> entidades do Hub ficam só no MappingFile.
    return MappingFileSchema(
        responsibles={"Usuário A": ids["responsible_id"]},
        areas={"Área Sintética": ids["area_id"]},
        disciplines={"Disciplina Sintética": ids["discipline_id"]},
        workPackages={"WP-S1": ids["wp1"], "WP-S2": ids["wp2"]},
    )


async def test_profile_b_pipeline_stage_plan_apply_reconcile(db_session) -> None:
    ids = await _seed(db_session)
    staged = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=layout_b_xlsx(),
        source_name="board-b.xlsx",
        profile=profile_b(),
    )
    assert staged.created is True and staged.records == 5  # 2 equipamentos + 3 componentes

    batch = await db_session.get(MondayImportBatch, staged.batch_id)
    assert batch is not None
    assert batch.parser_version == "monday-xlsx-v5"
    assert batch.summary["import_profiles"] == [profile_b().identity()]

    mapping = await validate_mapping(db_session, _mapping(ids), project_context_id=ids["context_id"])
    assert not mapping.has_errors
    partial = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    # Regra pré-existente: componente sem ID estável nunca é aplicado (fallback não é definitivo).
    blocked = [
        (name, [issue.code for issue in item.issues])
        for name, items in partial.all_groups.items()
        for item in items
        if item.action == "BLOCKED"
    ]
    assert blocked == [("components", ["missing_component_identity"])]

    # Snapshot sintético seguinte, com todos os subitens identificados.
    staged = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=layout_b_xlsx(all_component_ids=True),
        source_name="board-b-v2.xlsx",
        profile=profile_b(),
    )
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    assert plan.has_blocked is False, [
        (name, i.source_key, [x.code for x in i.issues])
        for name, items in plan.all_groups.items()
        for i in items
        if i.action == "BLOCKED"
    ]
    keys = sorted(item.source_key for item in plan.equipments)
    assert keys == ["monday-item-id:7001", "normalized-name:equipamento sintetico b"]
    assert {item.payload["current_stage"] for item in plan.equipments} == {2, 5}

    result = await apply_plan(
        db_session,
        plan=plan,
        expected_plan_sha256=plan.plan_sha256,
        actor=CurrentUser(
            id=ids["actor_id"],
            email="admin.sintetico@example.test",
            name="Admin",
            role=PermissionRole.ADMIN,
            active=True,
        ),
    )
    assert result.status == "APPLIED"

    equipments = {
        e.name: e
        for e in (
            await db_session.execute(
                select(Equipment).where(Equipment.project_context_id == ids["context_id"])
            )
        )
        .scalars()
        .all()
    }
    assert set(equipments) == {"Equipamento Sintético A", "Equipamento Sintético B"}
    assert equipments["Equipamento Sintético A"].current_stage == 2
    # P1.3.1: Area legada não é mais destino da localização
    assert equipments["Equipamento Sintético A"].area_id is None
    assert equipments["Equipamento Sintético A"].responsible_user_id == ids["responsible_id"]
    components = (await db_session.execute(select(EquipmentComponent))).scalars().all()
    assert len(components) == 3

    strategies = {
        m.external_id: m.identity_strategy
        for m in (
            await db_session.execute(
                select(ExternalMapping).where(ExternalMapping.source_entity_type == "equipment")
            )
        )
        .scalars()
        .all()
    }
    assert strategies == {
        "monday-item-id:7001": "monday-item-id-v1",
        "normalized-name:equipamento sintetico b": "normalized-name-v1",
    }

    report = await reconcile_domain(db_session, project_context_id=ids["context_id"], mapping=mapping)
    assert report.field_totals["MISMATCH"] == 0

    # idempotência: replanejar após o apply não cria nada
    again = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    assert {item.action for item in again.equipments} == {"NOOP"}


async def test_same_file_cannot_be_restaged_with_another_profile(db_session) -> None:
    ids = await _seed(db_session)
    source = layout_b_xlsx()
    await stage_import(db_session, project_context_id=ids["context_id"], source=source, profile=profile_b())
    again = await stage_import(
        db_session, project_context_id=ids["context_id"], source=source, profile=profile_b()
    )
    assert again.created is False
    with pytest.raises(StagedWithDifferentProfileError):
        await stage_import(
            db_session, project_context_id=ids["context_id"], source=source, profile=profile_a()
        )


async def test_unknown_status_blocks_and_group_is_not_stage_authority(db_session) -> None:
    ids = await _seed(db_session)
    mapping = await validate_mapping(db_session, _mapping(ids), project_context_id=ids["context_id"])

    unknown = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=layout_a_xlsx(status_override="Status Inventado"),
        profile=profile_a(),
    )
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[unknown.batch_id], mapping=mapping
    )
    codes = {issue.code for item in plan.equipments for issue in item.issues}
    assert "UNKNOWN_STAGE_VALUE" in codes
    assert all(item.action == "BLOCKED" for item in plan.equipments)
    # o grupo ("Stage 2 ...") NÃO foi usado como fase no lugar do status desconhecido
    assert "STAGE_CONFLICT" not in codes


async def test_new_version_of_same_profile_restages_unapplied_batch(db_session) -> None:
    """P1.3.1: profile versionado evoluiu → batch nunca aplicado é reanalisado no mesmo batch."""
    ids = await _seed(db_session)
    source = layout_b_xlsx()
    first = await stage_import(
        db_session, project_context_id=ids["context_id"], source=source, profile=profile_b()
    )
    newer = profile_b().model_copy(update={"version": 2, "description": "versão sintética 2"})
    again = await stage_import(db_session, project_context_id=ids["context_id"], source=source, profile=newer)
    assert (again.batch_id, again.created, again.restaged) == (first.batch_id, False, True)
    assert again.records == first.records
    batch = await db_session.get(MondayImportBatch, first.batch_id)
    assert batch is not None and batch.summary["import_profiles"] == [newer.identity()]

    # depois de aplicado, nem a nova versão reinterpreta o arquivo
    batch.status = "APPLIED"
    await db_session.flush()
    newest = profile_b().model_copy(update={"version": 3, "description": "versão sintética 3"})
    with pytest.raises(StagedWithDifferentProfileError):
        await stage_import(db_session, project_context_id=ids["context_id"], source=source, profile=newest)


async def test_new_parser_version_restages_unapplied_batch(db_session) -> None:
    ids = await _seed(db_session)
    source = layout_b_xlsx()
    profile = profile_b()
    first = await stage_import(
        db_session, project_context_id=ids["context_id"], source=source, profile=profile
    )
    batch = await db_session.get(MondayImportBatch, first.batch_id)
    assert batch is not None
    batch.parser_version = "monday-xlsx-legacy"
    await db_session.flush()

    again = await stage_import(
        db_session, project_context_id=ids["context_id"], source=source, profile=profile
    )

    assert (again.batch_id, again.created, again.restaged) == (first.batch_id, False, True)
    assert batch.parser_version == "monday-xlsx-v5"
