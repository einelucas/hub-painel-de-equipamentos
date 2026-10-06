"""Apply com criação de catálogos na mesma transação (somente dados sintéticos).

Cobre: EAP PROCESS + AREA, ProjectEap, Discipline, WorkPackage e Supplier criados
com evidência; vínculo do equipamento aos IDs novos; rollback total se algo
falhar depois de criar catálogos; reimportação sem duplicações.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from app.core.auth import CurrentUser
from app.core.permissions import Role as PermissionRole
from app.models.access import UserUnitAccess
from app.models.equipment import (
    Discipline,
    EapNode,
    Equipment,
    EquipmentWorkPackage,
    ProjectContext,
    ProjectEap,
    Unit,
    WorkPackage,
)
from app.models.supplier import EquipmentSupplier, Supplier
from app.models.user import Role as UserRole
from app.models.user import User
from app.modules.monday_import import apply as apply_module
from app.modules.monday_import.apply import apply_plan
from app.modules.monday_import.mapping_file import MappingFileSchema, validate_mapping
from app.modules.monday_import.plan import build_plan
from app.modules.monday_import.service import stage_import
from tests.unit.monday_xlsx_fixture import build_xlsx

HEADER = [
    "Name",
    "Subelementos",
    "A.Status",
    "0.Startup/Grãos",
    "Work Package",
    "0.Responsável",
    "0.Área",
    "0.Disciplina",
    "Cód. Fornecedor. CS",
]


def _board(*, responsible: str = "Responsável Sintético", supplier: str = "9001") -> bytes:
    return build_xlsx(
        [
            ["Equipamentos - Projeto Sintético"],
            ["Fase 0 - Nova Demanda"],
            HEADER,
            [
                "Equipamento Catálogo Novo",
                "Componente Sintético",
                "0.Nova demanda",
                "2027/10/27",
                "WPN1",
                responsible,
                "2377.A - Área Sintética Nova",
                "Disciplina Nova Sintética",
                supplier,
            ],
            ["Subitems", "Name", "ID do elemento", "0.Startup/Grãos"],
            [None, "Componente Sintético", "700001", "2027/09/01"],
        ]
    )


EVIDENCE = {
    "catalogEvidence": {
        "disciplines": {"Disciplina Nova Sintética": {"code": "DNS"}},
        "workPackages": {"WPN1": {"name": "Pacote Novo Sintético"}},
        "eapProcesses": {"77": {"name": "Processo Sintético Novo"}},
        "suppliers": {"9001": {"legalName": "Fornecedor Sintético Novo SA"}},
    }
}


async def _seed(db_session) -> dict[str, str]:
    unit = Unit(code="U-CAT", name="Unidade Catálogos")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="C-CAT", name="Contexto Catálogos")
    db_session.add(context)
    await db_session.flush()
    responsible = User(name="Responsável Sintético", email="resp-cat@example.com", role=UserRole.ANALYST)
    actor = User(name="Admin Catálogos", email="admin-cat@example.com", role=UserRole.ADMIN)
    db_session.add_all([responsible, actor])
    await db_session.flush()
    db_session.add(UserUnitAccess(user_id=responsible.id, unit_id=unit.id))
    await db_session.flush()
    return {"context_id": context.id, "responsible_id": responsible.id, "actor_id": actor.id}


def _actor(actor_id: str) -> CurrentUser:
    return CurrentUser(
        id=actor_id, email="actor@example.com", name="Actor", role=PermissionRole.ADMIN, active=True
    )


async def _plan(db_session, ids: dict[str, str], batch_id: str, schema: dict[str, Any] | None = None):
    mapping = await validate_mapping(
        db_session, MappingFileSchema.model_validate(schema or EVIDENCE), project_context_id=ids["context_id"]
    )
    return await build_plan(
        db_session, project_context_id=ids["context_id"], batch_ids=[batch_id], mapping=mapping
    )


async def _count(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


def _actions(plan) -> dict[tuple[str, str], str]:
    return {(item.kind, item.key): item.action.value for item in plan.catalog_items}


async def test_apply_creates_catalogs_and_links_equipment_in_same_transaction(db_session) -> None:
    ids = await _seed(db_session)
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_board(), source_name="a.xlsx"
    )
    plan = await _plan(db_session, ids, staged.batch_id)

    actions = _actions(plan)
    assert actions[("eap_node", "77")] == "CREATE"
    assert actions[("eap_node", "77.A")] == "CREATE"
    assert actions[("project_eap", "77.A")] == "CREATE"
    assert actions[("discipline", "Disciplina Nova Sintética")] == "CREATE"
    assert actions[("work_package", "WPN1")] == "CREATE"
    assert actions[("supplier", "9001")] == "CREATE"
    assert plan.responsible_summary == {"resolved": 1, "unresolved": 0}  # nome exato e único
    assert plan.has_blocked is False
    # plan não grava
    assert await _count(db_session, EapNode) == 0

    result = await apply_plan(
        db_session, plan=plan, expected_plan_sha256=plan.plan_sha256, actor=_actor(ids["actor_id"])
    )
    assert result.status == "APPLIED"
    assert result.counts["catalogs"] == {"eapNodes": 2, "disciplines": 1, "workPackages": 1, "suppliers": 1}

    area = (await db_session.execute(select(EapNode).where(EapNode.code == "77.A"))).scalar_one()
    process = (await db_session.execute(select(EapNode).where(EapNode.code == "77"))).scalar_one()
    assert (process.level, process.name) == ("PROCESS", "Processo Sintético Novo")
    assert (area.level, area.parent_id, area.name) == ("AREA", process.id, "Área Sintética Nova")

    equipment = (await db_session.execute(select(Equipment))).scalar_one()
    assert equipment.eap_node_id == area.id  # nunca fica NULL quando a EAP foi criada
    discipline = (await db_session.execute(select(Discipline))).scalar_one()
    assert (discipline.code, discipline.name, equipment.discipline_id) == (
        "DNS",
        "Disciplina Nova Sintética",
        discipline.id,
    )
    assert equipment.responsible_user_id == ids["responsible_id"]
    work_package = (await db_session.execute(select(WorkPackage))).scalar_one()
    assert work_package.project_context_id == ids["context_id"]
    links = (await db_session.execute(select(EquipmentWorkPackage.work_package_id))).scalars().all()
    assert links == [work_package.id]
    supplier = (await db_session.execute(select(Supplier))).scalar_one()
    assert (supplier.corporate_code, supplier.legal_name) == ("9001", "Fornecedor Sintético Novo SA")
    supplier_link = (await db_session.execute(select(EquipmentSupplier))).scalar_one()
    assert (supplier_link.equipment_id, supplier_link.supplier_id) == (equipment.id, supplier.id)
    project_eap = (await db_session.execute(select(ProjectEap))).scalar_one()
    assert (project_eap.project_context_id, project_eap.eap_node_id) == (ids["context_id"], area.id)


async def test_reimport_is_existing_and_noop_without_duplicates(db_session) -> None:
    ids = await _seed(db_session)
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_board(), source_name="a.xlsx"
    )
    first = await _plan(db_session, ids, staged.batch_id)
    await apply_plan(
        db_session, plan=first, expected_plan_sha256=first.plan_sha256, actor=_actor(ids["actor_id"])
    )

    second = await _plan(db_session, ids, staged.batch_id)
    assert set(_actions(second).values()) == {"EXISTING"}
    assert all(item.action == "NOOP" for item in second.equipments)
    assert all(item.action == "NOOP" for item in second.components)
    await apply_plan(
        db_session, plan=second, expected_plan_sha256=second.plan_sha256, actor=_actor(ids["actor_id"])
    )

    for model, expected in (
        (EapNode, 2),
        (ProjectEap, 1),
        (Discipline, 1),
        (WorkPackage, 1),
        (Supplier, 1),
        (EquipmentSupplier, 1),
        (Equipment, 1),
    ):
        assert await _count(db_session, model) == expected, model.__name__


async def test_failure_after_catalog_creation_rolls_back_everything(db_session, monkeypatch) -> None:
    ids = await _seed(db_session)
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=_board(), source_name="a.xlsx"
    )
    plan = await _plan(db_session, ids, staged.batch_id)

    async def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("falha sintética após criar catálogos")

    monkeypatch.setattr(apply_module, "_apply_component", boom)
    with pytest.raises(RuntimeError):
        await apply_plan(
            db_session, plan=plan, expected_plan_sha256=plan.plan_sha256, actor=_actor(ids["actor_id"])
        )

    for model in (EapNode, ProjectEap, Discipline, WorkPackage, Supplier, EquipmentSupplier, Equipment):
        assert await _count(db_session, model) == 0, model.__name__


async def test_unresolved_catalogs_do_not_block_and_leave_links_empty(db_session) -> None:
    ids = await _seed(db_session)
    board = _board(responsible="Pessoa Sem Usuário", supplier="???")
    staged = await stage_import(
        db_session, project_context_id=ids["context_id"], source=board, source_name="a.xlsx"
    )
    plan = await _plan(db_session, ids, staged.batch_id, schema={})

    actions = _actions(plan)
    assert actions[("eap_node", "77.A")] == "UNRESOLVED"  # pai sem nome comprovado
    assert actions[("discipline", "Disciplina Nova Sintética")] == "UNRESOLVED"
    assert actions[("work_package", "WPN1")] == "UNRESOLVED"
    assert actions[("supplier", "???")] == "UNRESOLVED"
    assert plan.has_blocked is False
    codes = {issue.code for issue in plan.equipments[0].issues}
    assert {
        "EAP_PARENT_REQUIRED",
        "DISCIPLINE_CODE_REQUIRED",
        "WORK_PACKAGE_UNRESOLVED",
        "SUPPLIER_UNRESOLVED",
        "RESPONSIBLE_UNRESOLVED",
    } <= codes

    await apply_plan(
        db_session, plan=plan, expected_plan_sha256=plan.plan_sha256, actor=_actor(ids["actor_id"])
    )
    equipment = (await db_session.execute(select(Equipment))).scalar_one()
    assert (equipment.eap_node_id, equipment.discipline_id, equipment.responsible_user_id) == (
        None,
        None,
        None,
    )
    for model in (EapNode, Discipline, WorkPackage, Supplier, EquipmentSupplier):
        assert await _count(db_session, model) == 0, model.__name__
