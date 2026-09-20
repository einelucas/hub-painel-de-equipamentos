"""stage -> plan -> apply -> reconcile: idempotência, conflitos e auditoria.

Cobre o fluxo completo do apply controlado (MIG-001.1), sem tocar o banco de
desenvolvimento — tudo roda contra o Postgres dedicado de testes.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select

from app.core.auth import CurrentUser
from app.core.permissions import Role as PermissionRole
from app.models.access import UserUnitAccess
from app.models.audit import AuditLog
from app.models.equipment import (
    Area,
    Discipline,
    Equipment,
    EquipmentComponent,
    EquipmentWorkPackage,
    ProjectContext,
    Unit,
    WorkflowTransition,
    WorkPackage,
)
from app.models.monday_import import ExternalMapping, MondayImportBatch, MondayMigrationRun
from app.models.process import PurchaseRequest
from app.models.user import Role as UserRole
from app.models.user import User
from app.modules.monday_import.apply import PlanBlockedError, PlanStaleError, apply_plan
from app.modules.monday_import.mapping_file import MappingFileSchema, validate_mapping
from app.modules.monday_import.plan import build_plan
from app.modules.monday_import.service import stage_import
from tests.unit.monday_xlsx_fixture import build_xlsx


async def _seed_context(db_session, suffix: str) -> dict[str, str]:
    unit = Unit(code=f"U-{suffix}", name=f"Unidade {suffix}")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code=f"C-{suffix}", name=f"Contexto {suffix}")
    db_session.add(context)
    await db_session.flush()
    area = Area(unit_id=unit.id, name=f"Área {suffix}")
    discipline = Discipline(code=f"D-{suffix}", name=f"Disciplina {suffix}")
    wp1 = WorkPackage(project_context_id=context.id, code="CAL100", name="Caldeira 100")
    wp2 = WorkPackage(project_context_id=context.id, code="CIV100", name="Civil 100")
    db_session.add_all([area, discipline, wp1, wp2])
    await db_session.flush()
    responsible = User(
        name=f"Responsável {suffix}", email=f"resp-{suffix}@example.com", role=UserRole.ANALYST
    )
    db_session.add(responsible)
    await db_session.flush()
    db_session.add(UserUnitAccess(user_id=responsible.id, unit_id=unit.id))
    actor = User(name=f"Admin {suffix}", email=f"admin-{suffix}@example.com", role=UserRole.ADMIN)
    db_session.add(actor)
    await db_session.flush()
    return {
        "unit_id": unit.id,
        "context_id": context.id,
        "area_id": area.id,
        "discipline_id": discipline.id,
        "work_package_1": wp1.id,
        "work_package_2": wp2.id,
        "responsible_id": responsible.id,
        "actor_id": actor.id,
    }


def _actor(actor_id: str) -> CurrentUser:
    return CurrentUser(
        id=actor_id, email="actor@example.com", name="Actor", role=PermissionRole.ADMIN, active=True
    )


async def _apply(db_session, plan, ids: dict[str, str]):
    return await apply_plan(
        db_session, plan=plan, expected_plan_sha256=plan.plan_sha256, actor=_actor(ids["actor_id"])
    )


def _rich_equipment_xlsx(
    *,
    equipment_name: str = "Bomba Apply",
    contract_number: str = "CT-9001",
    responsible_name: str = "Responsavel Um",
    area_name: str = "Area Um",
    discipline_name: str = "Disciplina Um",
    work_packages: str = "CAL100, CIV100",
    component_external_id: str = "999001",
) -> bytes:
    rows: list[list[Any]] = [
        ["Equipamentos - Teste Apply"],
        ["Fase 0 - Nova Demanda"],
        [],
        [
            "Name",
            "Subelementos",
            "A.Status",
            "0.Startup/Grãos",
            "Work Package",
            "0.Responsável",
            "0.Área",
            "0.Disciplina",
            "1.Equalização",
            "2.Data da Negociação",
            "3.Data de Abertura do Chamado",
            "3.Chamado Jurídico",
            "5.Numero Contrato",
            "5.Data Escrituração",
            "6.Numero SC/OCI",
            "6.Data de SC/OCI",
            "7.Numero OC",
            "7.Data OC",
            "CAPEX Estimado",
        ],
        [
            equipment_name,
            "Motor",
            "0.Nova demanda",
            "2026/06/01",
            work_packages,
            responsible_name,
            area_name,
            discipline_name,
            "v",
            "2026/01/10",
            "2026/01/15",
            "TCK-001",
            contract_number,
            "2026/02/01",
            "SC-9001",
            "2026/02/10",
            "OC-9001",
            "2026/02/20",
            15000.50,
        ],
        [
            "Subitems",
            "Name",
            "ID do elemento",
            "0.Startup/Grãos",
            "Frete (Dias)",
            "Lead Time de Fabricação",
            "0.Dias Antes do Startup",
        ],
        [None, "Motor Apply", component_external_id, "2027/03/15", 10, 20, 5],
    ]
    return build_xlsx(rows)


def _mapping_schema(ids: dict[str, str]) -> MappingFileSchema:
    return MappingFileSchema(
        responsibles={"Responsavel Um": ids["responsible_id"]},
        areas={"Area Um": ids["area_id"]},
        disciplines={"Disciplina Um": ids["discipline_id"]},
        workPackages={"CAL100": ids["work_package_1"], "CIV100": ids["work_package_2"]},
    )


async def test_plan_does_not_write_and_blocks_unmapped_values(db_session) -> None:
    ids = await _seed_context(db_session, "PLAN")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    empty_mapping = await validate_mapping(
        db_session, MappingFileSchema(), project_context_id=ids["context_id"]
    )
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=empty_mapping
    )

    assert plan.has_blocked is True
    equipment_item = plan.equipments[0]
    assert equipment_item.action == "BLOCKED"
    codes = {issue.code for issue in equipment_item.issues}
    assert {"unmapped_responsible", "unmapped_area", "unmapped_discipline", "unmapped_work_package"} <= codes
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 0


async def test_mapping_validation_rejects_bad_references(db_session) -> None:
    ids = await _seed_context(db_session, "MAP")
    other = await _seed_context(db_session, "MAP2")
    inactive_user = User(name="Inativo", email="inativo@example.com", role=UserRole.ANALYST, active=False)
    db_session.add(inactive_user)
    await db_session.flush()

    schema = MappingFileSchema(
        responsibles={
            "Fantasma": "00000000-0000-0000-0000-000000000000",
            "Inativo": inactive_user.id,
            "SemAcesso": other["responsible_id"],
        },
        areas={"AreaErrada": other["area_id"]},
        workPackages={"WPErrado": other["work_package_1"]},
    )
    result = await validate_mapping(db_session, schema, project_context_id=ids["context_id"])

    codes = {issue.code for issue in result.issues}
    assert "unknown_user" in codes
    assert "inactive_user" in codes
    assert "user_without_unit_access" in codes
    assert "area_wrong_unit" in codes
    assert "work_package_wrong_context" in codes
    assert result.has_errors is True


async def test_apply_creates_equipment_with_multiple_work_packages_and_component_own_startup(
    db_session,
) -> None:
    ids = await _seed_context(db_session, "APP1")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    assert plan.has_blocked is False
    assert len(plan.equipments) == 1 and plan.equipments[0].action == "CREATE"

    result = await _apply(db_session, plan, ids)
    assert result.status == "APPLIED"

    equipment = (
        await db_session.execute(select(Equipment).where(Equipment.project_context_id == ids["context_id"]))
    ).scalar_one()
    assert equipment.name == "Bomba Apply"
    assert equipment.current_stage == 0
    assert equipment.startup_at == date(2026, 6, 1)
    assert equipment.responsible_user_id == ids["responsible_id"]
    assert equipment.area_id == ids["area_id"]
    assert equipment.discipline_id == ids["discipline_id"]

    # múltiplos Work Packages: N:N preenchido e a FK primária deixada em branco
    # porque não há uma escolha correta entre os dois.
    links = (
        (
            await db_session.execute(
                select(EquipmentWorkPackage).where(EquipmentWorkPackage.equipment_id == equipment.id)
            )
        )
        .scalars()
        .all()
    )
    assert {link.work_package_id for link in links} == {ids["work_package_1"], ids["work_package_2"]}
    assert equipment.work_package_id is None

    component = (
        await db_session.execute(
            select(EquipmentComponent).where(EquipmentComponent.equipment_id == equipment.id)
        )
    ).scalar_one()
    assert component.name == "Motor Apply"
    # o startup do componente é o dele mesmo, não o do equipamento (2026-06-01).
    assert component.startup_at == date(2027, 3, 15)
    assert component.freight_days == 10

    # nenhuma transição fictícia: o estágio foi inicializado direto pela migração.
    transitions = (
        await db_session.execute(
            select(func.count(WorkflowTransition.id)).where(WorkflowTransition.equipment_id == equipment.id)
        )
    ).scalar_one()
    assert transitions == 0

    audits = (
        (await db_session.execute(select(AuditLog).where(AuditLog.entityId == equipment.id)))
        .scalars()
        .all()
    )
    assert {audit.action for audit in audits} == {"migration.import"}

    # SC/OCI sem tipo identificável: warning explícito, kind permanece nulo.
    assert any(item.code == "PURCHASE_REQUEST_KIND_UNRESOLVED" for item in plan.warnings)
    purchase_request = (
        await db_session.execute(select(PurchaseRequest).where(PurchaseRequest.equipment_id == equipment.id))
    ).scalar_one()
    assert purchase_request.kind is None
    assert purchase_request.request_number == "SC-9001"

    batch = await db_session.get(MondayImportBatch, staged.batch_id)
    assert batch is not None and batch.status == "APPLIED"

    run = (
        await db_session.execute(
            select(MondayMigrationRun).where(MondayMigrationRun.id == result.migration_run_id)
        )
    ).scalar_one()
    assert run.status == "APPLIED"


async def test_apply_is_idempotent_on_repeated_execution(db_session) -> None:
    ids = await _seed_context(db_session, "APP2")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])

    first_plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    await _apply(db_session, first_plan, ids)

    second_plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    assert all(item.action == "NOOP" for item in second_plan.equipments)
    assert all(item.action == "NOOP" for item in second_plan.components)

    second_result = await _apply(db_session, second_plan, ids)
    assert second_result.status == "APPLIED"

    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 1
    assert (await db_session.execute(select(func.count(EquipmentComponent.id)))).scalar_one() == 1
    audits = (
        await db_session.execute(select(func.count(AuditLog.id)).where(AuditLog.action == "migration.import"))
    ).scalar_one()
    # segunda rodada é NOOP: nenhuma auditoria nova além da primeira aplicação
    # (Equipment, EquipmentComponent, Negotiation, LegalProcess, Contract,
    # PurchaseRequest, PurchaseOrder — um registro cada, todos da 1a rodada).
    assert audits == 7


async def test_apply_rejects_stale_plan_hash(db_session) -> None:
    ids = await _seed_context(db_session, "STALE")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    try:
        await apply_plan(db_session, plan=plan, expected_plan_sha256="0" * 64, actor=_actor(ids["actor_id"]))
        raise AssertionError("deveria ter recusado hash divergente")
    except PlanStaleError:
        pass
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 0


async def test_apply_refuses_plan_with_blocked_items(db_session) -> None:
    ids = await _seed_context(db_session, "BLOCK")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    empty_mapping = await validate_mapping(
        db_session, MappingFileSchema(), project_context_id=ids["context_id"]
    )
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=empty_mapping
    )
    try:
        await _apply(db_session, plan, ids)
        raise AssertionError("deveria ter recusado plano bloqueado")
    except PlanBlockedError as exc:
        assert len(exc.blocked) >= 1
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 0


async def test_parent_identity_conflict_blocks_without_merging(db_session) -> None:
    ids = await _seed_context(db_session, "PARENT")
    manual = Equipment(project_context_id=ids["context_id"], name="Bomba Apply", current_stage=0)
    db_session.add(manual)
    await db_session.flush()

    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )

    equipment_item = plan.equipments[0]
    assert equipment_item.action == "BLOCKED"
    assert any(issue.code == "PARENT_IDENTITY_CONFLICT" for issue in equipment_item.issues)
    # nenhum merge automático: o equipamento manual continua sozinho.
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 1


async def test_overlapping_batches_with_diverging_payload_is_blocked(db_session) -> None:
    ids = await _seed_context(db_session, "OVERLAP")
    first = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=_rich_equipment_xlsx(contract_number="CT-9001"),
        source_name="a.xlsx",
    )
    second = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=_rich_equipment_xlsx(contract_number="CT-DIFERENTE"),
        source_name="b.xlsx",
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session,
        project_context_id=ids["context_id"],
        batch_ids=[first.batch_id, second.batch_id],
        mapping=mapping,
    )

    equipment_item = plan.equipments[0]
    assert equipment_item.action == "BLOCKED"
    assert equipment_item.issues[0].code == "IMPORT_CONFLICT"
    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 0


async def test_overlapping_batches_with_identical_payload_merge_without_conflict(db_session) -> None:
    ids = await _seed_context(db_session, "SAMEOVERLAP")
    first = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    second = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=_rich_equipment_xlsx(),
        source_name="a-copia.xlsx",
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session,
        project_context_id=ids["context_id"],
        batch_ids=[first.batch_id, second.batch_id],
        mapping=mapping,
    )
    assert plan.has_blocked is False
    assert plan.equipments[0].action == "CREATE"


async def test_hub_edit_after_migration_blocks_silent_overwrite(db_session) -> None:
    ids = await _seed_context(db_session, "CONFLICT")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    await _apply(db_session, plan, ids)

    equipment = (
        await db_session.execute(select(Equipment).where(Equipment.project_context_id == ids["context_id"]))
    ).scalar_one()
    equipment.name = "Renomeado manualmente"
    db_session.add(
        AuditLog(userId=ids["actor_id"], action="equipment.update", entity="Equipment", entityId=equipment.id)
    )
    await db_session.flush()

    # mesmo nome de origem (mesma identidade), mas outro campo alterado: como
    # o Hub já foi editado por algo além da migração, isso deve bloquear em
    # vez de sobrescrever silenciosamente.
    new_batch = await stage_import(
        db_session,
        project_context_id=ids["context_id"],
        source=_rich_equipment_xlsx(contract_number="CT-NOVO"),
        source_name="c.xlsx",
    )
    plan2 = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[new_batch.batch_id], mapping=mapping
    )
    equipment_item = plan2.equipments[0]
    assert equipment_item.action == "BLOCKED"
    assert any(issue.code == "hub_monday_conflict" for issue in equipment_item.issues)


async def test_apply_rolls_back_on_error(db_session, monkeypatch) -> None:
    ids = await _seed_context(db_session, "ROLLBACK")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )

    import app.modules.monday_import.apply as apply_module

    async def _boom(*args, **kwargs):
        raise RuntimeError("falha forçada para testar rollback")

    monkeypatch.setattr(apply_module, "_apply_component", _boom)

    try:
        await _apply(db_session, plan, ids)
        raise AssertionError("deveria ter propagado o erro")
    except RuntimeError:
        pass

    assert (await db_session.execute(select(func.count(Equipment.id)))).scalar_one() == 0
    run = (
        await db_session.execute(
            select(MondayMigrationRun).where(MondayMigrationRun.project_context_id == ids["context_id"])
        )
    ).scalar_one()
    assert run.status == "FAILED"
    assert "falha forçada" in (run.error or "")
    batch = await db_session.get(MondayImportBatch, staged.batch_id)
    assert batch is not None and batch.status == "STAGED"


async def test_external_mapping_registered_for_equipment_and_component(db_session) -> None:
    ids = await _seed_context(db_session, "MAPPING")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_rich_equipment_xlsx(), source_name="a.xlsx"
    )
    mapping = await validate_mapping(db_session, _mapping_schema(ids), project_context_id=ids["context_id"])
    plan = await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[staged.batch_id], mapping=mapping
    )
    await _apply(db_session, plan, ids)

    mappings = (
        (
            await db_session.execute(
                select(ExternalMapping).where(ExternalMapping.project_context_id == ids["context_id"])
            )
        )
        .scalars()
        .all()
    )
    kinds = {item.source_entity_type: item.identity_strategy for item in mappings}
    assert kinds["equipment"] == "normalized-name-v1"
    assert kinds["component"] == "monday-item-id-v1"
