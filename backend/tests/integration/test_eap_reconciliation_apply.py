"""Apply controlado da reconciliação EAP (artefato JSON → equipment.eap_node_id). Dados sintéticos."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.equipment import Area, EapNode, Equipment, ProjectContext, ProjectEap, Unit
from app.models.monday_import import ExternalMapping
from app.modules.eap_catalog.catalog import load_catalog
from app.modules.eap_reconciliation.apply import (
    APPLY_ACTION,
    Expectations,
    ReconciliationApplyBlocked,
    apply_reconciliation,
)
from tests.eap_fixture import CATALOG_PATH

CATALOG = load_catalog(CATALOG_PATH)
EQUIPMENTS = {
    "alfa": ("Equipamento Sintético A", "MATCH_UNIQUE_NAME", "01.A"),
    "estrutura": ("Equipamento Sintético B", "MATCH_UNIQUE_NAME", "00.A"),
    "rede": ("Equipamento Sintético C", "MATCH_APPROVED_ALIAS", "00.C"),
    "geral": ("Equipamento Sintético D", "UNRESOLVED_GENERIC_VALUE", None),
    "review": ("Equipamento em revisão", "REVIEW_EAP_CATALOG", None),
}


def _category(status: str) -> str:
    return "MATCH" if status.startswith("MATCH") else status.split("_", 1)[0]


def _artifact() -> dict[str, Any]:
    records = [
        {
            "externalId": f"normalized-name:{key}",
            "equipmentName": name,
            "status": status,
            "category": _category(status),
            "matchedEapCode": code,
        }
        for key, (name, status, code) in EQUIPMENTS.items()
    ]
    return {
        "catalog": {"sha256": CATALOG.sha256},
        "metrics": {"total_equipment": len(records), "auto_match_safe_total": 3},
        "records": records,
    }


async def _setup(db_session) -> dict[str, Any]:
    nodes: dict[str, EapNode] = {}
    for code, name, level, parent in (
        ("D", "Ilha Sintética D", "ISLAND", None),
        ("00", "Geral", "PROCESS", None),
        ("00.A", "Estrutura Sintética", "AREA", "00"),
        ("00.C", "Rede Sintética", "AREA", "00"),
        ("01", "Processo Sintético A", "PROCESS", "D"),
        ("01.A", "Área Sintética Alfa", "AREA", "01"),
    ):
        node = EapNode(code=code, name=name, level=level, parent_id=nodes[parent].id if parent else None)
        db_session.add(node)
        await db_session.flush()
        nodes[code] = node
    unit = Unit(code="UNS", name="Unidade Sintética")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="CTX-S", name="Contexto Sintético")
    area = Area(unit_id=unit.id, name="Área Sintética Alfa")
    db_session.add_all([context, area])
    await db_session.flush()
    equipments: dict[str, Equipment] = {}
    for key, (name, _, _) in EQUIPMENTS.items():
        equipment = Equipment(project_context_id=context.id, name=name, current_stage=0, area_id=area.id)
        db_session.add(equipment)
        await db_session.flush()
        db_session.add(
            ExternalMapping(
                project_context_id=context.id,
                source_system="monday",
                source_entity_type="equipment",
                external_id=f"normalized-name:{key}",
                identity_strategy="normalized-name",
                target_entity_type="Equipment",
                target_entity_id=equipment.id,
            )
        )
        equipments[key] = equipment
    await db_session.commit()
    # Só ids: os objetos expiram nos expire_all() dos testes.
    return {
        "context": context.id,
        "area": area.id,
        "nodes": {code: node.id for code, node in nodes.items()},
        "equipments": {key: equipment.id for key, equipment in equipments.items()},
    }


async def _state(db_session) -> dict[str, tuple[str | None, str | None]]:
    db_session.expire_all()
    rows = (await db_session.execute(select(Equipment.name, Equipment.eap_node_id, Equipment.area_id))).all()
    return {name: (eap, area) for name, eap, area in rows}


async def _audits(db_session) -> list[AuditLog]:
    return list(
        (await db_session.execute(select(AuditLog).where(AuditLog.action == APPLY_ACTION))).scalars().all()
    )


async def _run(db_session, ctx, artifact=None, *, apply: bool, expect: Expectations | None = None):
    return await apply_reconciliation(
        db_session,
        artifact=artifact or _artifact(),
        artifact_sha256="sha-teste",
        catalog=CATALOG,
        project_context_id=ctx["context"],
        apply=apply,
        expect=expect,
    )


async def test_dry_run_plans_only_safe_statuses_and_writes_nothing(db_session) -> None:
    ctx = await _setup(db_session)
    result = await _run(db_session, ctx, apply=False)
    assert result.summary() == {
        "applied": False,
        "planned_updates": 3,
        "unchanged": 0,
        "skipped_unresolved": 1,
        "skipped_review": 1,
        "conflicts": 0,
    }
    assert {item["eapCode"] for item in result.planned_updates} == {"00.A", "00.C", "01.A"}
    assert all(eap is None for eap, _ in (await _state(db_session)).values())
    assert await _audits(db_session) == []


async def test_apply_links_safe_matches_audits_and_is_idempotent(db_session) -> None:
    ctx = await _setup(db_session)
    expect = Expectations(total=5, safe=3, review=1, unresolved=1)
    result = await _run(db_session, ctx, apply=True, expect=expect)
    assert (len(result.planned_updates), len(result.unchanged)) == (3, 0)

    state = await _state(db_session)
    nodes = ctx["nodes"]
    assert state["Equipamento Sintético A"][0] == nodes["01.A"]
    assert state["Equipamento Sintético B"][0] == nodes["00.A"]
    assert state["Equipamento Sintético C"][0] == nodes["00.C"]
    assert state["Equipamento Sintético D"][0] is None
    assert state["Equipamento em revisão"][0] is None
    assert {area for _, area in state.values()} == {ctx["area"]}  # area_id intacto

    audits = await _audits(db_session)
    assert len(audits) == 3
    network = next(a for a in audits if a.newData["eapCode"] == "00.C")
    assert network.previousData == {"eap_node_id": None}
    assert network.metadata_["reconciliationStatus"] == "MATCH_APPROVED_ALIAS"
    assert network.metadata_["externalId"] == "normalized-name:rede"
    assert network.metadata_["artifactSha256"] == "sha-teste"
    assert network.entityId == ctx["equipments"]["rede"] and network.createdAt is not None

    again = await _run(db_session, ctx, apply=True, expect=expect)
    assert again.summary()["planned_updates"] == 0 and again.summary()["unchanged"] == 3
    assert len(await _audits(db_session)) == 3

    assert (await db_session.execute(select(func.count()).select_from(ProjectEap))).scalar_one() == 0
    context = await db_session.get(ProjectContext, ctx["context"])
    assert context.eap_prefix is None


async def test_conflicting_existing_eap_aborts_everything(db_session) -> None:
    ctx = await _setup(db_session)
    structure = await db_session.get(Equipment, ctx["equipments"]["estrutura"])
    structure.eap_node_id = ctx["nodes"]["01.A"]
    await db_session.commit()

    with pytest.raises(ReconciliationApplyBlocked) as blocked:
        await _run(db_session, ctx, apply=True)
    assert any("já aponta para outro EapNode" in error for error in blocked.value.errors)
    state = await _state(db_session)
    assert state["Equipamento Sintético A"][0] is None and state["Equipamento Sintético C"][0] is None
    assert state["Equipamento Sintético B"][0] == ctx["nodes"]["01.A"]
    assert await _audits(db_session) == []


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda a: a["records"][0].update(externalId="normalized-name:inexistente"), "esperado 1 Equipment"),
        (lambda a: a["records"][0].update(matchedEapCode="99.Z"), "não existe no banco"),
        (lambda a: a["records"][0].update(matchedEapCode="D"), "só aponta para PROCESS/AREA"),
        (lambda a: a["records"][0].update(matchedEapCode="02.G"), "não existe no banco"),
        (lambda a: a["catalog"].update(sha256="outro"), "outro catálogo EAP"),
        (lambda a: a["records"][1].update(externalId="normalized-name:alfa"), "repetidas"),
    ],
)
async def test_prevalidation_failures_abort_before_any_write(db_session, mutate, fragment) -> None:
    ctx = await _setup(db_session)
    artifact = copy.deepcopy(_artifact())
    mutate(artifact)
    with pytest.raises(ReconciliationApplyBlocked) as blocked:
        await _run(db_session, ctx, artifact, apply=True)
    assert any(fragment in error for error in blocked.value.errors), blocked.value.errors
    assert all(eap is None for eap, _ in (await _state(db_session)).values())
    assert await _audits(db_session) == []


async def test_expectation_mismatch_aborts(db_session) -> None:
    ctx = await _setup(db_session)
    with pytest.raises(ReconciliationApplyBlocked) as blocked:
        await _run(
            db_session, ctx, apply=True, expect=Expectations(total=99, safe=98, review=0, unresolved=1)
        )
    assert any("esperado 99 total" in error for error in blocked.value.errors)
    assert all(eap is None for eap, _ in (await _state(db_session)).values())
