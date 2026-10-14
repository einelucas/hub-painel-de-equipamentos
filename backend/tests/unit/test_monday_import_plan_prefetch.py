"""Prefetch em lote do plano Monday: o número de consultas não cresce com as linhas.

Sessão falsa (sem banco): registra cada statement e responde por entidade. Garante
que o plano consulta o banco remoto com poucos `IN (...)` em vez de uma consulta por
equipamento/componente/processo (N+1), e que as respostas viram os mapas usados
pelo laço do plano.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.models.audit import AuditLog
from app.models.equipment import Equipment, EquipmentComponent
from app.models.monday_import import ExternalMapping
from app.models.process import Contract, LegalProcess, Negotiation, PurchaseOrder, PurchaseRequest
from app.models.supplier import EquipmentSupplier
from app.modules.monday_import import plan as plan_module
from app.modules.monday_import.plan import _chunks, _PlanPrefetch

CONTEXT = "ctx-1"


class _FakeSession:
    def __init__(self, responder: Any) -> None:
        self.statements: list[Any] = []
        self._responder = responder

    def _rows(self, statement: Any) -> list[Any]:
        self.statements.append(statement)
        description = statement.column_descriptions[0]
        params = statement.compile().params
        in_values = next((value for value in params.values() if isinstance(value, list)), [])
        return list(self._responder(description["entity"], description["name"], in_values))

    async def scalars(self, statement: Any) -> list[Any]:
        return self._rows(statement)

    async def execute(self, statement: Any) -> list[Any]:
        return self._rows(statement)


def _empty(*_: Any) -> list[Any]:
    return []


async def test_prefetch_query_count_is_independent_of_row_count() -> None:
    session = _FakeSession(_empty)
    await _PlanPrefetch.load(
        session,  # type: ignore[arg-type]
        project_context_id=CONTEXT,
        equipment_keys=[f"eq-{index}" for index in range(77)],
        component_keys=[f"comp-{index}" for index in range(540)],
        equipment_names=[f"Equipamento {index}" for index in range(77)] + [None],
    )
    # mappings de equipamento + de componente + colisão de nome; sem mapping, nada mais.
    assert len(session.statements) == 3


async def test_prefetch_chunks_large_in_lists() -> None:
    session = _FakeSession(_empty)
    total = plan_module._IN_CHUNK * 2 + 1
    await _PlanPrefetch.load(
        session,  # type: ignore[arg-type]
        project_context_id=CONTEXT,
        equipment_keys=[f"eq-{index}" for index in range(total)],
        component_keys=[],
        equipment_names=[],
    )
    assert len(session.statements) == 3


def test_chunks_dedupes_and_splits() -> None:
    values = [str(index) for index in range(plan_module._IN_CHUNK + 5)] * 2
    chunks = list(_chunks(values))
    assert [len(chunk) for chunk in chunks] == [plan_module._IN_CHUNK, 5]
    assert list(_chunks([])) == []


async def test_prefetch_builds_lookup_maps() -> None:
    mappings = {
        "equipment": [SimpleNamespace(external_id="eq-a", target_entity_id="E1")],
        "component": [SimpleNamespace(external_id="comp-a", target_entity_id="C1")],
    }
    equipment = SimpleNamespace(id="E1", work_package_links=[])
    component = SimpleNamespace(id="C1")
    contract_first = SimpleNamespace(id="K1", equipment_id="E1")
    contract_second = SimpleNamespace(id="K2", equipment_id="E1")
    mapping_calls: list[str] = []

    def responder(entity: Any, name: str, in_values: list[str]) -> list[Any]:
        if entity is ExternalMapping:
            kind = "equipment" if in_values and in_values[0].startswith("eq") else "component"
            mapping_calls.append(kind)
            return mappings[kind]
        if entity is Equipment and name == "id":
            return [("E9", "Bomba"), ("E8", "Bomba")]
        if entity is Equipment:
            assert in_values == ["E1"]
            return [equipment]
        if entity is EquipmentSupplier:
            return [("E1", "S1", "L1"), ("E1", "S2", "L2")]
        if entity is Contract:
            return [contract_first, contract_second]
        if entity in (Negotiation, LegalProcess, PurchaseRequest, PurchaseOrder):
            return []
        if entity is EquipmentComponent:
            assert in_values == ["C1"]
            return [component]
        if entity is AuditLog:
            return [("Contract", "K1")] if "K1" in in_values else []
        raise AssertionError(f"consulta inesperada: {entity} {name}")

    session = _FakeSession(responder)
    prefetch = await _PlanPrefetch.load(
        session,  # type: ignore[arg-type]
        project_context_id=CONTEXT,
        equipment_keys=["eq-a", "eq-b"],
        component_keys=["comp-a"],
        equipment_names=["Bomba"],
    )

    assert mapping_calls == ["equipment", "component"]
    assert prefetch.mapping("equipment", "eq-a").target_entity_id == "E1"  # type: ignore[union-attr]
    assert prefetch.mapping("equipment", "eq-b") is None
    assert prefetch.mapping("component", "comp-a").target_entity_id == "C1"  # type: ignore[union-attr]
    # Primeira linha vence, como o `session.scalar` por linha fazia.
    assert prefetch.equipment_id_by_name == {"Bomba": "E9"}
    assert prefetch.current_supplier == {"E1": "S1"}
    assert prefetch.current_supplier_link == {"E1": "L1"}
    assert prefetch.equipments == {"E1": equipment}
    assert prefetch.components == {"C1": component}
    assert prefetch.sub_entity(Contract, "E1") is contract_first
    assert prefetch.sub_entity(Negotiation, "E1") is None
    assert prefetch.sub_entity(Contract, None) is None
    assert prefetch.touched("Contract", "K1")
    assert not prefetch.touched("Equipment", "E1")
    # mappings(2) + nomes(1) + equipamento(1) + fornecedor(1) + 5 processos
    # + componente(1) + auditoria (Equipment, EquipmentComponent, Contract) = 14
    assert len(session.statements) == 14
