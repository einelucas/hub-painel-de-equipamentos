"""Carga idempotente do catálogo EAP em eap_node (banco de teste, fixture sintética)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.domain.eap import EapLevel
from app.models.audit import AuditLog
from app.models.equipment import EapNode, Equipment, ProjectContext, ProjectEap, Unit
from app.modules.eap_catalog.catalog import CatalogNode, EapCatalog, EapCatalogError, load_catalog
from app.modules.eap_catalog.seed import seed_eap_catalog
from tests.eap_fixture import CATALOG_PATH


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _nodes(session) -> dict[str, EapNode]:
    return {node.code: node for node in (await session.execute(select(EapNode))).scalars().all()}


async def test_seed_loads_catalog_and_is_idempotent(db_session) -> None:
    catalog = load_catalog(CATALOG_PATH)

    first = await seed_eap_catalog(db_session, catalog, apply=True)
    assert first.summary() == {
        "applied": True,
        "created": 19,
        "updated": 0,
        "updated_in_use": 0,
        "unchanged": 0,
        "conflicts": 0,
        "skipped_review_required": len(catalog.review_required),
        "extra_in_database": 0,
    }

    nodes = await _nodes(db_session)
    assert len(nodes) == 19
    assert not catalog.review_codes & nodes.keys()
    by_id = {node.id: node for node in nodes.values()}
    for node in nodes.values():
        parent = by_id.get(node.parent_id) if node.parent_id else None
        if node.level == "AREA":
            assert parent is not None and parent.level == "PROCESS"
        elif node.level == "PROCESS":
            assert parent is None or parent.level == "ISLAND"
        else:
            assert parent is None
    assert nodes["01.A"].name == "Área Sintética Alfa" and by_id[nodes["01.A"].parent_id].code == "01"
    assert await _count(db_session, AuditLog) == 19

    second = await seed_eap_catalog(db_session, catalog, apply=True)
    assert (len(second.created), len(second.unchanged), second.conflicts) == (0, 19, [])
    assert len(await _nodes(db_session)) == 19
    assert await _count(db_session, AuditLog) == 19
    assert await _count(db_session, ProjectEap) == 0


async def test_dry_run_writes_nothing(db_session) -> None:
    result = await seed_eap_catalog(db_session, load_catalog(CATALOG_PATH), apply=False)
    assert (result.applied, len(result.created)) == (False, 19)
    assert await _count(db_session, EapNode) == 0
    assert await _count(db_session, AuditLog) == 0


def _small_catalog() -> EapCatalog:
    return EapCatalog(
        nodes=(
            CatalogNode(EapLevel.ISLAND, "D", "Ilha Sintética D", None),
            CatalogNode(EapLevel.PROCESS, "01", "Processo Sintético A", "D"),
            CatalogNode(EapLevel.AREA, "01.A", "Área Sintética Alfa", "01"),
        ),
        review_required=({"code": "21", "reason": "MALFORMED_PREFIX_MARKER"},),
    )


async def test_existing_divergent_node_is_reported_not_overwritten(db_session) -> None:
    db_session.add(EapNode(code="01", name="Nome local divergente", level="PROCESS"))
    db_session.add(EapNode(code="99", name="Nó fora do catálogo", level="PROCESS"))
    await db_session.commit()

    result = await seed_eap_catalog(db_session, _small_catalog(), apply=True)

    assert result.created == ["D", "01.A"]
    assert result.conflicts == [
        {
            "code": "01",
            "differences": {
                "name": {"database": "Nome local divergente", "catalog": "Processo Sintético A"},
                "parent_code": {"database": None, "catalog": "D"},
            },
        }
    ]
    assert result.extra_in_database == ["99"]
    nodes = await _nodes(db_session)
    assert nodes["01"].name == "Nome local divergente" and nodes["01"].parent_id is None
    assert nodes["01.A"].parent_id == nodes["01"].id
    assert "99" in nodes


async def test_review_required_is_never_inserted(db_session) -> None:
    result = await seed_eap_catalog(db_session, _small_catalog(), apply=True)
    assert result.skipped_review_required == [
        {"code": "21", "reason": "MALFORMED_PREFIX_MARKER", "existsInDatabase": False}
    ]
    assert "21" not in await _nodes(db_session)


async def test_invalid_catalog_is_refused_before_writing(db_session) -> None:
    invalid = EapCatalog(nodes=(CatalogNode(EapLevel.AREA, "01.A", "Área Sintética Alfa", "01"),))
    with pytest.raises(EapCatalogError):
        await seed_eap_catalog(db_session, invalid, apply=True)
    assert await _count(db_session, EapNode) == 0


async def test_seed_does_not_touch_equipment_or_project_eap(db_session) -> None:
    unit = Unit(code="UNS", name="Unidade Sintética")
    db_session.add(unit)
    await db_session.flush()
    context = ProjectContext(unit_id=unit.id, code="CTX-S", name="Contexto Sintético")
    db_session.add(context)
    await db_session.flush()
    db_session.add(Equipment(project_context_id=context.id, name="Equipamento Sintético A", current_stage=0))
    await db_session.commit()

    await seed_eap_catalog(db_session, load_catalog(CATALOG_PATH), apply=True)

    equipment = (await db_session.execute(select(Equipment))).scalar_one()
    assert (equipment.eap_node_id, equipment.area_id) == (None, None)
    assert (await db_session.get(ProjectContext, context.id)).eap_prefix is None
    assert await _count(db_session, ProjectEap) == 0
