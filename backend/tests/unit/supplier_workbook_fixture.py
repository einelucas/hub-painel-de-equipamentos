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
            alias("FORNECEDOR A (MM)", "90001", "FORNECEDOR SINTETICO A LTDA", tax_id="11111111000111"),
            alias("FORNECEDOR A (Grãos)", "90001", "FORNECEDOR SINTETICO A LTDA", tax_id="11111111000111"),
            alias("FORNECEDOR B", "90002", "FORNECEDOR SINTETICO B SE", tax_id="N/A"),
        ],
        probable=[alias("FORNECEDOR D", None, None, tax_id=None, active=None, classification="PROVÁVEL")],
        ambiguous=[alias("FORNECEDOR C", None, None, tax_id=None, active=None, classification="AMBÍGUO")],
        not_found=[
            alias("EM DEFINIÇÃO", None, None, tax_id=None, active=None, classification="NÃO ENCONTRADO")
        ],
        equipments=[
            equipment("Secador de grãos", "FORNECEDOR A (Grãos)", "90001", "CONFIRMADO"),
            equipment("Elevador de canecas", "FORNECEDOR A (MM)", "90001", "CONFIRMADO"),
            equipment(
                "Decanter",
                "FORNECEDOR B",
                "90002",
                "CONFIRMADO",
                phase="Não se Aplica",
                status="Não se Aplica",
            ),
            equipment("Termômetros", "FORNECEDOR C", "90003", "AMBÍGUO"),
            equipment("Moega", "FORNECEDOR D", "90004", "PROVÁVEL"),
            equipment("Linha de alternativos", "FORNECEDOR D", "90004", "CONFIRMADO"),
            equipment("Atuadores de requeima", "EM DEFINIÇÃO", None, "NÃO ENCONTRADO"),
        ],
    )
