"""Conciliação de domínio em lote: o número de consultas não cresce com os
equipamentos/componentes, e o resultado é o mesmo da comparação item a item.

Sessão falsa (sem banco): responde por entidade e filtra pelos valores do `IN (...)`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.models.equipment import Equipment
from app.models.monday_import import ExternalMapping, MondayImportRecord
from app.modules.monday_import import domain_reconciliation as module
from app.modules.monday_import.catalog_planner import EquipmentCatalogs

CONTEXT = "ctx-1"


class _Result:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _Result:
        return self

    def unique(self) -> _Result:
        return self

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeSession:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.statements: list[Any] = []

    def _rows(self, statement: Any) -> _Result:
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        values = list(params.values())
        in_values: list[Any] = next((value for value in values if isinstance(value, list)), [])
        if entity is ExternalMapping:
            kind = "component" if "component" in values else "equipment"
            rows = [item for item in self.data["mappings"] if item.source_entity_type == kind]
            if kind == "component":
                rows = [item for item in rows if item.target_entity_id in in_values]
        elif entity is Equipment:
            rows = [item for item in self.data["equipments"] if item.id in in_values]
        elif entity is MondayImportRecord:
            kind = "component" if "component" in values else "equipment"
            rows = [
                item
                for item in self.data["records"]
                if item.record_kind == kind and item.source_key in in_values
            ]
        else:
            rows = []
        return _Result(rows)

    async def scalars(self, statement: Any) -> _Result:
        return self._rows(statement)

    async def execute(self, statement: Any) -> _Result:
        return self._rows(statement)


class _Catalogs:
    async def resolve(self, _session: Any, _normalized: dict[str, Any]) -> EquipmentCatalogs:
        return EquipmentCatalogs()


@pytest.fixture(autouse=True)
def _stub_catalogs(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _load(*_: Any, **__: Any) -> _Catalogs:
        return _Catalogs()

    monkeypatch.setattr(module.CatalogPlanner, "load", _load)


def _mapping(kind: str, external_id: str, target: str) -> SimpleNamespace:
    return SimpleNamespace(source_entity_type=kind, external_id=external_id, target_entity_id=target)


def _record(kind: str, key: str, batch: str, payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"{kind}-{key}-{batch}",
        record_kind=kind,
        source_key=key,
        batch_id=batch,
        normalized_payload=payload,
    )


def _equipment(index: int, components: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"eq-{index}",
        name=f"Equipamento {index}",
        startup_at=None,
        contractual_delivery_end=None,
        current_stage=None,
        operational_status="ACTIVE",
        eap_node_id=None,
        discipline_id=None,
        responsible_user_id=None,
        work_package_links=[],
        negotiation=None,
        legal_process=None,
        contracts=[],
        purchase_requests=[],
        purchase_orders=[],
        components=components,
    )


def _dataset(count: int) -> dict[str, Any]:
    mappings: list[SimpleNamespace] = []
    equipments: list[SimpleNamespace] = []
    records: list[SimpleNamespace] = []
    for index in range(count):
        comps = [SimpleNamespace(id=f"c-{index}-{n}", lead_time_days=10) for n in range(3)]
        equipments.append(_equipment(index, comps))
        mappings.append(_mapping("equipment", f"k-{index}", f"eq-{index}"))
        name = f"Equipamento {index}" if index % 2 == 0 else "Outro nome"
        records.append(_record("equipment", f"k-{index}", "b1", {"name": name}))
        for n, comp in enumerate(comps):
            mappings.append(_mapping("component", f"ck-{index}-{n}", comp.id))
            # c0 bate, c1 diverge, c2 em conflito entre batches.
            if n == 0:
                records.append(_record("component", f"ck-{index}-{n}", "b1", {"lead_time_days": 10}))
            elif n == 1:
                records.append(_record("component", f"ck-{index}-{n}", "b1", {"lead_time_days": 99}))
            else:
                records.append(_record("component", f"ck-{index}-{n}", "b1", {"lead_time_days": 10}))
                records.append(_record("component", f"ck-{index}-{n}", "b2", {"lead_time_days": 11}))
    # Equipamento com batches em conflito: não comparável.
    equipments.append(_equipment(count, []))
    mappings.append(_mapping("equipment", "k-conflict", f"eq-{count}"))
    records.append(_record("equipment", "k-conflict", "b1", {"name": "A"}))
    records.append(_record("equipment", "k-conflict", "b2", {"name": "B"}))
    # Vínculo para equipamento removido: ignorado.
    mappings.append(_mapping("equipment", "k-gone", "eq-gone"))
    return {"mappings": mappings, "equipments": equipments, "records": records}


async def test_reconcile_domain_query_count_is_constant() -> None:
    small = _FakeSession(_dataset(3))
    await module.reconcile_domain(small, project_context_id=CONTEXT)  # type: ignore[arg-type]
    large = _FakeSession(_dataset(60))
    await module.reconcile_domain(large, project_context_id=CONTEXT)  # type: ignore[arg-type]
    # mappings de equipamento + equipamentos + staging equipamento + mappings de
    # componente + staging componente.
    assert len(small.statements) == len(large.statements) == 5


async def test_reconcile_domain_results() -> None:
    session = _FakeSession(_dataset(4))
    report = await module.reconcile_domain(session, project_context_id=CONTEXT)  # type: ignore[arg-type]

    assert report.equipments_compared == 5
    assert report.components_compared == 12
    by_key = {item.source_key: item for item in report.equipments}
    assert set(by_key) == {"k-0", "k-1", "k-2", "k-3", "k-conflict"}
    assert [(f.field, f.status) for f in by_key["k-conflict"].fields] == [("name", "NOT_COMPARABLE")]

    for key, expected in (("k-0", "MATCH"), ("k-1", "MISMATCH")):
        fields = {item.field: item for item in by_key[key].fields}
        assert fields["name"].status == expected
        components = fields["components"]
        assert components.status == "MISMATCH"
        assert components.hub_value == 1  # um componente bate
        assert components.source_value == 3  # total de vínculos de componente


async def test_reconcile_domain_chunks_large_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_IN_CHUNK", 7)
    session = _FakeSession(_dataset(20))
    report = await module.reconcile_domain(session, project_context_id=CONTEXT)  # type: ignore[arg-type]
    assert report.equipments_compared == 21
    assert report.components_compared == 60
