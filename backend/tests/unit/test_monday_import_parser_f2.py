"""Board LEM F2: fornecedor singular, código corporativo, área padrão e 'Não se Aplica'."""

from __future__ import annotations

from app.modules.monday_import.parser import parse_monday_xlsx
from tests.unit.monday_xlsx_fixture import build_xlsx

_HEADER = [
    "Name",
    "Subelementos",
    "A.Status",
    "0.Fornecedor",
    "Cód. Fornecedor. CS",
    "0.Disciplina",
    "z.0.Área",
    "0.Área (padrão)",
]

_AUXILIARY_EQUIPMENT_HEADERS = [
    "A.Dias até limite negociação",
    "A.Folga relativa",
    "E.Limite p/ contrato-OC (mín. subelem.)",
    "S.Escalonamento",
    "z.Espelho Frete (dias)",
    "z.Espelho Prazo (dias)",
    "z.F.Limite Entrega Obra (duplicada)",
    "z.F.Limite contrato-OC (duplicada)",
]
_AUXILIARY_COMPONENT_HEADERS = ["Visualização", "z.Calc Limite contrato-OC"]


def _f2_xlsx() -> bytes:
    return build_xlsx(
        [
            ["Equipamentos LEM F2"],
            ["Fase 0 - Nova Demanda"],
            _HEADER,
            [
                "Trocador de calor",
                None,
                "0.Nova demanda",
                "AMPLA",
                3307.0,
                "Metal Mec.",
                "Texto antigo",
                "Diversos",
            ],
            ["Não se Aplica"],
            _HEADER,
            [
                "Decanter",
                None,
                "Não se Aplica",
                "FORNECEDOR B",
                "90002",
                "Metal Mec.",
                "Caldeira",
                "Destilaria",
            ],
        ]
    )


def _f2_with_responsible_cost_and_subitem() -> bytes:
    return build_xlsx(
        [
            ["Equipamentos LEM F2"],
            ["Fase 0 - Nova Demanda"],
            [
                "Name",
                "Subelementos",
                "A.Status",
                "z.0.Responsável (texto antigo)",
                "0.Responsável (padrão)",
                "Custo Previsto",
            ],
            ["Secador", "Motor", "0.Nova demanda", "Antigo", "Analista Sintético B", 388433.8],
            [
                "Subitems",
                "Name",
                "1.TAG",
                "0.Lead Time de Fabricação",
                "0.Frete (Dias)",
                "F.Data Limite de Entrega em Obra",
                "5.Data de Entrega pelo contrato",
                "Prazo",
            ],
            [None, "Motor", "SC-02", 138, "10", "2027/11/17", "2027/10/01", 244],
        ]
    )


def _f2_with_auxiliary_columns() -> bytes:
    main_headers = ["Name", "Subelementos", "A.Status", *_AUXILIARY_EQUIPMENT_HEADERS]
    component_headers = ["Subitems", "Name", *_AUXILIARY_COMPONENT_HEADERS]
    return build_xlsx(
        [
            ["Equipamentos Obra Sintética"],
            ["Fase 0 - Nova Demanda"],
            main_headers,
            [
                "Equipamento Sintético",
                "Componente Sintético",
                "0.Nova demanda",
                120,
                1.25,
                46_500,
                "v",
                "10, 20",
                120,
                "2027/04/01",
                "2027/01/01",
            ],
            component_headers,
            [None, "Componente Sintético", "https://example.invalid/doc", 46_500],
        ]
    )


def test_responsible_comes_from_padrao_column_and_legacy_text_is_preserved_apart() -> None:
    equipment = parse_monday_xlsx(_f2_with_responsible_cost_and_subitem(), source_name="f2.xlsx").equipments[
        0
    ]
    assert equipment.normalized["responsible_name"] == "Analista Sintético B"
    assert equipment.normalized["responsible_legacy_text"] == "Antigo"


def test_custo_previsto_is_only_a_candidate_never_capex() -> None:
    equipment = parse_monday_xlsx(_f2_with_responsible_cost_and_subitem(), source_name="f2.xlsx").equipments[
        0
    ]
    assert equipment.normalized["planned_cost_candidate"] == "388433.8"
    assert "capex_estimated" not in equipment.normalized
    assert equipment.raw["Custo Previsto"] == 388433.8


def test_prefixed_f2_subitem_columns_map_to_the_c2_concepts() -> None:
    parsed = parse_monday_xlsx(_f2_with_responsible_cost_and_subitem(), source_name="f2.xlsx")
    component = parsed.equipments[0].components[0]
    assert component.normalized["tag"] == "SC-02"
    assert component.normalized["lead_time_days"] == 138
    assert component.normalized["freight_days"] == 10
    assert component.normalized["delivery_deadline"] == "2027-11-17"
    assert component.normalized["contract_delivery_at"] == "2027-10-01"
    assert component.raw["1.TAG"] == "SC-02"
    # P1.3.1: "Prazo" do subitem validado em UAT como o mesmo conceito de "Prazo Neg"
    # (prazo de negociação − data da exportação, em todas as linhas analisadas).
    assert "Prazo" not in parsed.unknown_component_fields
    assert component.normalized["negotiation_days_remaining_observed"] == 244
    assert component.raw["Prazo"] == 244


def test_f2_auxiliary_columns_are_explicitly_ignored_and_preserved_in_raw() -> None:
    parsed = parse_monday_xlsx(_f2_with_auxiliary_columns(), source_name="f2.xlsx")

    assert parsed.unknown_equipment_fields == set()
    assert parsed.unknown_component_fields == set()
    equipment = parsed.equipments[0]
    component = equipment.components[0]
    assert set(equipment.raw) >= set(_AUXILIARY_EQUIPMENT_HEADERS)
    assert set(component.raw) >= set(_AUXILIARY_COMPONENT_HEADERS)
    assert not set(equipment.normalized) & {
        "negotiation_days_remaining_observed",
        "delivery_margin_days_observed",
    }


def _by_name(parsed):
    return {item.normalized["name"]: item for item in parsed.equipments}


def test_nao_se_aplica_is_a_group_not_an_equipment() -> None:
    parsed = parse_monday_xlsx(_f2_xlsx(), source_name="f2.xlsx")
    assert sorted(_by_name(parsed)) == ["Decanter", "Trocador de calor"]
    assert not [issue for issue in parsed.issues if issue.code == "missing_group"]


def test_nao_se_aplica_is_preserved_and_never_becomes_stage_zero() -> None:
    equipments = _by_name(parse_monday_xlsx(_f2_xlsx(), source_name="f2.xlsx"))

    decanter = equipments["Decanter"]
    assert decanter.group_name == "Não se Aplica"
    assert decanter.normalized["current_stage"] is None
    assert decanter.normalized["stage_not_applicable"] is True

    trocador = equipments["Trocador de calor"]
    assert trocador.normalized["current_stage"] == 0
    assert trocador.normalized["stage_not_applicable"] is False


def test_area_comes_from_area_padrao_not_from_legacy_z_column() -> None:
    equipments = _by_name(parse_monday_xlsx(_f2_xlsx(), source_name="f2.xlsx"))

    assert equipments["Trocador de calor"].normalized["area_name"] == "Diversos"
    assert equipments["Trocador de calor"].normalized["area_legacy_text"] == "Texto antigo"
    assert equipments["Decanter"].normalized["area_name"] == "Destilaria"


def test_reads_singular_supplier_and_corporate_code_as_text() -> None:
    parsed = parse_monday_xlsx(_f2_xlsx(), source_name="f2.xlsx")
    equipments = _by_name(parsed)

    assert equipments["Trocador de calor"].normalized["suppliers_raw"] == "AMPLA"
    assert equipments["Trocador de calor"].normalized["supplier_corporate_code"] == "3307"
    assert equipments["Decanter"].normalized["supplier_corporate_code"] == "90002"
    assert (
        not {"0.Fornecedor", "Cód. Fornecedor. CS", "0.Área (padrão)", "z.0.Área"}
        & parsed.unknown_equipment_fields
    )
