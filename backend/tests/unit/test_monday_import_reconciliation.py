"""Snapshots Monday SINTÉTICOS: merge, contagens, prazos dos componentes e agregação no pai.

Substitui a dependência dos exports reais (privados). As datas esperadas são
calculadas aqui com `timedelta` (cadeia startup - antecedência - frete -
fabricação - 21 dias), independentemente do código do app.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.modules.monday_import.calculations import ComponentSchedule, calculate_component_deadlines
from app.modules.monday_import.dry_run import merge_workbooks
from app.modules.monday_import.parser import parse_monday_xlsx
from app.modules.monday_import.reconciliation import (
    GroupCount,
    ReconciliationCounts,
    count_records,
    reconcile_counts,
)
from tests.unit.monday_xlsx_fixture import build_xlsx

BOARD = "Equipamentos - Obra Sintética"
EQUIPMENT_HEADER = [
    "Name",
    "Subelementos",
    "A.Status",
    "E.Lead Time de Fabricação",
    "E.Dias Antes do Startup",
    "ESPELHO-FORMULA-FRETE",
    "F.Limite Entrega Obra",
    "F.Data Limite para contrato/OC",
    "F.Data Limite Negociação",
]
COMPONENT_HEADER = [
    "Subitems",
    "Name",
    "ID do elemento",
    "0.Startup/Grãos",
    "0.Dias Antes do Startup",
    "Frete (Dias)",
    "Lead Time de Fabricação",
    "Data Limite de Entrega em Obra",
    "Disponivel Coleta",
    "Data limite para contrato/OC",
    "F.Data Limite Negociação_calc",
]
NEGOTIATION_BUFFER_DAYS = 21


def _br(value: date | None) -> str | None:
    return value.strftime("%d/%m/%Y") if value is not None else None


def _chain(startup: date, pre: int, freight: int | None, lead: int | None) -> tuple[date | None, ...]:
    delivery = startup - timedelta(days=pre)
    collection = delivery - timedelta(days=freight or 0)
    contract = collection - timedelta(days=lead) if lead is not None else None
    negotiation = contract - timedelta(days=NEGOTIATION_BUFFER_DAYS) if contract is not None else None
    return delivery, collection, contract, negotiation


def _component(name: str, external_id: str, startup: date, pre: int, freight: int | None, lead: int | None):
    delivery, collection, contract, negotiation = _chain(startup, pre, freight, lead)
    row = [None, name, external_id, _br(startup), pre, freight, lead, _br(delivery), _br(collection)]
    return row + [_br(contract), _br(negotiation)], (pre, freight, lead, delivery, contract, negotiation)


def _equipment(name: str, stage: str, components: list) -> list[list]:
    rows = [component for component, _ in components]
    facts = [fact for _, fact in components]
    leads = [lead for _, _, lead, _, _, _ in facts if lead is not None]
    pres = [pre for pre, *_ in facts]
    freights = [freight for _, freight, *_ in facts if freight is not None]
    deliveries = [fact[3] for fact in facts if fact[3] is not None]
    contracts = [fact[4] for fact in facts if fact[4] is not None]
    negotiations = [fact[5] for fact in facts if fact[5] is not None]
    parent = [
        name,
        ", ".join(row[1] for row in rows),
        stage,
        max(leads) if leads else None,
        max(pres) if pres else None,
        max(freights) if freights else None,
        _br(min(deliveries)) if deliveries else None,
        _br(min(contracts)) if contracts else None,
        _br(min(negotiations)) if negotiations else None,
    ]
    return [parent, COMPONENT_HEADER, *rows]


def _group(title: str, *equipments: list[list]) -> list[list]:
    rows: list[list] = [[title], EQUIPMENT_HEADER]
    for equipment in equipments:
        rows.extend(equipment)
    return rows


def _equipment_a() -> list[list]:
    return _equipment(
        "Equipamento Sintético A",
        "0.Nova demanda",
        [
            _component("Componente A1", "900001", date(2027, 12, 1), 30, 10, 60),
            _component("Componente A2", "900002", date(2028, 1, 15), 20, None, 45),
        ],
    )


def _snapshots(directory: Path) -> list[Path]:
    first = [
        [BOARD],
        *_group("Fase 0 - Nova Demanda", _equipment_a()),
        *_group(
            "Fase 4 - Negociação",
            _equipment(
                "Equipamento Sintético B",
                "4.Negociação",
                [_component("Componente B1", "900003", date(2028, 3, 1), 15, 5, None)],
            ),
        ),
    ]
    second = [
        [BOARD],
        *_group("Fase 0 - Nova Demanda", _equipment_a()),
        *_group(
            "Fase 4 - Negociação",
            _equipment(
                "Equipamento Sintético C",
                "4.Negociação",
                [_component("Componente C1", "900004", date(2028, 6, 10), 10, 0, 30)],
            ),
        ),
    ]
    paths = [directory / "snapshot-1.xlsx", directory / "snapshot-2.xlsx"]
    for path, rows in zip(paths, (first, second), strict=True):
        path.write_bytes(build_xlsx(rows))
    return paths


SYNTHETIC_EXPECTED = ReconciliationCounts(
    equipments=3,
    components=4,
    groups={"Fase 0": GroupCount(1, 2), "Fase 4": GroupCount(2, 2)},
)


def _merged(directory: Path):
    return merge_workbooks([parse_monday_xlsx(path) for path in _snapshots(directory)])


def _parsed_date(values: dict, field: str) -> date | None:
    value = values.get(field)
    return date.fromisoformat(value) if isinstance(value, str) else None


def test_synthetic_snapshots_merge_and_reconcile(tmp_path) -> None:
    equipments, duplicate_count = _merged(tmp_path)
    report = reconcile_counts(count_records(equipments), SYNTHETIC_EXPECTED)

    assert duplicate_count == 3  # o equipamento A e seus 2 componentes se repetem entre snapshots
    assert report.matched, report.to_dict()


def test_synthetic_exports_confirm_all_component_deadlines(tmp_path) -> None:
    equipments, _ = _merged(tmp_path)

    checked = 0
    for equipment in equipments:
        for component in equipment.components:
            values = component.normalized
            calculated = calculate_component_deadlines(
                ComponentSchedule(
                    startup_at=_parsed_date(values, "startup_at"),
                    pre_start_days=values.get("pre_start_days"),
                    freight_days=values.get("freight_days"),
                    lead_time_days=values.get("lead_time_days"),
                )
            )
            assert calculated.delivery_deadline == _parsed_date(values, "delivery_deadline")
            assert calculated.collection_available_at == _parsed_date(values, "collection_available_at")
            assert calculated.contract_or_po_deadline == _parsed_date(values, "contract_or_po_deadline")
            assert calculated.negotiation_deadline == _parsed_date(values, "negotiation_deadline")
            checked += 1
    assert checked == 4


def test_synthetic_exports_confirm_all_parent_aggregations(tmp_path) -> None:
    equipments, _ = _merged(tmp_path)
    mappings = [
        ("lead_time_days_mirror", "lead_time_days", max),
        ("pre_start_days_mirror", "pre_start_days", max),
        ("freight_days_mirror", "freight_days", max),
        ("delivery_deadline", "delivery_deadline", min),
        ("contract_or_po_deadline", "contract_or_po_deadline", min),
        ("negotiation_deadline", "negotiation_deadline", min),
    ]
    for equipment in equipments:
        for parent_field, component_field, aggregate in mappings:
            values = [
                component.normalized[component_field]
                for component in equipment.components
                if component.normalized.get(component_field) is not None
            ]
            expected = aggregate(values) if values else None
            assert equipment.normalized.get(parent_field) == expected
    assert len(equipments) == 3
