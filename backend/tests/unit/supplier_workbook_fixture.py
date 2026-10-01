"""Planilha mínima no formato da auditoria de fornecedores (dados fictícios)."""

from __future__ import annotations

from typing import Any

from tests.unit.monday_xlsx_fixture import build_workbook

ALIAS_HEADER = [
    "Nome original Monday",
    "Nome normalizado",
    "Origem",
    "Quantidade equipamentos",
    "Código corporativo validado",
    "CNPJ/documento oficial",
    "Razão social oficial",
    "Ativo",
    "Classificação anterior",
    "Classificação validada",
]
EQUIPMENT_HEADER = [
    "Equipamento",
    "Fornecedor original",
    "Fase",
    "A.Status",
    "Disciplina",
    "Área_original_auditoria",
    "Área_validada_monday",
    "Cód. Fornecedor. CS",
    "Classificação do item",
    "Arquivo",
    "Linha",
]


def alias(
    name: str,
    code: str | None,
    legal_name: str | None,
    *,
    tax_id: str | None = "12345678000199",
    active: str | None = "SIM",
    classification: str = "CONFIRMADO",
) -> list[Any]:
    return [name, name.upper(), "F2", 1, code, tax_id, legal_name, active, classification, classification]


def equipment(
    name: str,
    supplier: str | None,
    code: str | None,
    classification: str,
    *,
    phase: str = "Fase 0 - Nova Demanda",
    status: str = "0.Nova demanda",
) -> list[Any]:
    return [
        name,
        supplier,
        phase,
        status,
        "Metal Mec.",
        code,
        "Caldeira",
        code,
        classification,
        "f2.xlsx",
        10,
    ]


def supplier_workbook(
    *,
    confirmed: list[list[Any]],
    equipments: list[list[Any]],
    probable: list[list[Any]] | None = None,
    ambiguous: list[list[Any]] | None = None,
    not_found: list[list[Any]] | None = None,
) -> bytes:
    return build_workbook(
        {
            "Resumo": [["Indicador", "Resultado"]],
            "Fornecedores F2": [EQUIPMENT_HEADER, *equipments],
            "Confirmados": [ALIAS_HEADER, *confirmed],
            "Prováveis": [ALIAS_HEADER, *(probable or [])],
            "Ambíguos": [ALIAS_HEADER, *(ambiguous or [])],
            "Não Encontrados": [ALIAS_HEADER, *(not_found or [])],
        }
    )


def representative_supplier_workbook() -> bytes:
    """Dois aliases do mesmo código, um estrangeiro sem CNPJ e os bloqueios."""
    return supplier_workbook(
        confirmed=[
            alias("AGI BRASIL (MM)", "13974", "AGI BRASIL INDUSTRIA LTDA", tax_id="11111111000111"),
            alias("AGI BRASIL (Grãos)", "13974", "AGI BRASIL INDUSTRIA LTDA", tax_id="11111111000111"),
            alias("FLOTTWEG", "3026", "FLOTTWEG SE", tax_id="N/A"),
        ],
        probable=[alias("DUJUA", None, None, tax_id=None, active=None, classification="PROVÁVEL")],
        ambiguous=[alias("ASHCROFT", None, None, tax_id=None, active=None, classification="AMBÍGUO")],
        not_found=[
            alias("EM DEFINIÇÃO", None, None, tax_id=None, active=None, classification="NÃO ENCONTRADO")
        ],
        equipments=[
            equipment("Secador de grãos", "AGI BRASIL (Grãos)", "13974", "CONFIRMADO"),
            equipment("Elevador de canecas", "AGI BRASIL (MM)", "13974", "CONFIRMADO"),
            equipment(
                "Decanter",
                "FLOTTWEG",
                "3026",
                "CONFIRMADO",
                phase="Não se Aplica",
                status="Não se Aplica",
            ),
            equipment("Termômetros", "ASHCROFT", "692", "AMBÍGUO"),
            equipment("Moega", "DUJUA", "448", "PROVÁVEL"),
            equipment("Linha de alternativos", "DUJUA", "448", "CONFIRMADO"),
            equipment("Atuadores de requeima", "EM DEFINIÇÃO", None, "NÃO ENCONTRADO"),
        ],
    )
