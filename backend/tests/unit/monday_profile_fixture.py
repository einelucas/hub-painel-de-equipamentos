"""Dois layouts Monday SINTÉTICOS (A e B) com os mesmos registros fictícios.

Só a estrutura muda entre eles (título do board, grupos, cabeçalhos, rótulos de
status, ordem das colunas). Nenhum dado real.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.modules.monday_import.profile import ImportProfile, load_profile
from tests.unit.monday_xlsx_fixture import build_xlsx

PROFILES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "monday" / "profiles"
PROFILE_A_PATH = PROFILES_DIR / "profile_a.json"
PROFILE_B_PATH = PROFILES_DIR / "profile_b.json"


def profile_a() -> ImportProfile:
    return load_profile(PROFILE_A_PATH)


def profile_b() -> ImportProfile:
    return load_profile(PROFILE_B_PATH)


# Registros canônicos fictícios (o que os dois layouts devem produzir).
EQUIPMENTS: list[dict[str, Any]] = [
    {
        "name": "Equipamento Sintético A",
        "item_id": "7001",
        "stage": 2,
        "area": "Área Sintética",
        "owner": "Usuário A",
        "discipline": "Disciplina Sintética",
        "startup": "2027/10/27",
        "packages": "WP-S1, WP-S2",
        "components": [
            {
                "name": "Componente Sintético A1",
                "id": "8001",
                "startup": "2027/09/01",
                "lead": 30,
                "freight": 5,
                "pre": 10,
            },
            {
                "name": "Componente Sintético A2",
                "id": None,
                "startup": "2027/09/15",
                "lead": 20,
                "freight": None,
                "pre": 5,
            },
        ],
    },
    {
        "name": "Equipamento Sintético B",
        "item_id": None,
        "stage": 5,
        "area": "Área Sintética",
        "owner": "Usuário A",
        "discipline": "Disciplina Sintética",
        "startup": "2028/01/15",
        "packages": "WP-S1",
        "components": [
            {
                "name": "Componente Sintético B1",
                "id": "8002",
                "startup": "2028/01/01",
                "lead": 40,
                "freight": 7,
                "pre": 14,
            },
        ],
    },
]

_STATUS_A = {0: "Backlog", 1: "Engineering", 2: "Negotiation", 5: "Contract", 8: "Delivered"}
_STATUS_B = {0: "P0 Intake", 1: "P1 Design", 2: "P2 Sourcing", 5: "P5 Signed", 8: "P8 Closed"}


def layout_a_xlsx(
    *,
    status_override: str | None = None,
    extra_header: str | None = None,
    board_title: str = "Synthetic Equipment Board - Project A",
    group_title: str = "Stage 2 - Negotiation",
    drop_status_column: bool = False,
) -> bytes:
    header = [
        "Equipment",
        "Item ID",
        "Status",
        "Area",
        "Owner",
        "Discipline",
        "Startup",
        "Work Packages",
        "Notes",
    ]
    if extra_header:
        header.append(extra_header)
    sub_header = [
        "Subitems",
        "Component",
        "Component ID",
        "Component Startup",
        "Lead Time",
        "Freight",
        "Days Before Startup",
        "Attachments",
    ]
    rows: list[list[Any]] = [[board_title], [group_title], header]
    for equipment in EQUIPMENTS:
        status = status_override or _STATUS_A[equipment["stage"]]
        row = [
            equipment["name"],
            equipment["item_id"],
            status,
            equipment["area"],
            equipment["owner"],
            equipment["discipline"],
            equipment["startup"],
            equipment["packages"],
            "nota livre",
        ]
        if extra_header:
            row.append("valor novo")
        rows.append(row)
        rows.append(sub_header)
        for component in equipment["components"]:
            rows.append(
                [
                    None,
                    component["name"],
                    component["id"],
                    component["startup"],
                    component["lead"],
                    component["freight"],
                    component["pre"],
                    "anexo.pdf",
                ]
            )
    if drop_status_column:
        index = header.index("Status")
        rows = [
            [value for position, value in enumerate(row) if position != index]
            if len(row) == len(header)
            else row
            for row in rows
        ]
    return build_xlsx(rows)


def layout_b_xlsx(*, group_title: str = "Etapa 2 - Compras", all_component_ids: bool = False) -> bytes:
    # Ordem de colunas diferente da do layout A, de propósito.
    header = ["Sector", "Asset", "Phase", "Asset Code", "Trade", "Responsible Person", "Packages", "Go-Live"]
    sub_header = [
        "Sub-assets",
        "Part Code",
        "Part",
        "Shipping Days",
        "Manufacturing Days",
        "Part Go-Live",
        "Lead Before Go-Live",
    ]
    rows: list[list[Any]] = [["Quadro Sintético de Ativos - Projeto B"], [group_title], header]
    for equipment in EQUIPMENTS:
        rows.append(
            [
                equipment["area"],
                equipment["name"],
                _STATUS_B[equipment["stage"]],
                equipment["item_id"],
                equipment["discipline"],
                equipment["owner"],
                equipment["packages"],
                equipment["startup"],
            ]
        )
        rows.append(sub_header)
        for component in equipment["components"]:
            component_id = component["id"] or ("8099" if all_component_ids else None)
            rows.append(
                [
                    None,
                    component_id,
                    component["name"],
                    component["freight"],
                    component["lead"],
                    component["startup"],
                    component["pre"],
                ]
            )
    return build_xlsx(rows)
