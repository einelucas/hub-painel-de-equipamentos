from __future__ import annotations

import hashlib
import json

from app.modules.supplier_catalog.catalog import (
    CatalogSupplier,
    SupplierCatalog,
    build_catalog_document,
    parse_catalog,
    validate_catalog,
)
from app.modules.supplier_catalog.workbook import load_supplier_workbook
from tests.unit.monday_xlsx_fixture import build_workbook

HEADERS = [
    "CODIGO_FORNECEDOR",
    "NOME_FORNECEDOR_OFICIAL",
    "DOCUMENTO",
    "ATIVO_BASE_OFICIAL",
    "ALIAS_REFERENCIA_ORIGEM",
    "EVIDENCIA_CRUZAMENTO",
    "QTD_EQUIPAMENTOS_RELACIONADOS",
    "ACAO_HUB",
]


def _xlsx() -> bytes:
    return build_workbook(
        {
            "Fornecedores_Hub": [
                HEADERS,
                [
                    393,
                    "FORNECEDOR SINTÉTICO A LTDA",
                    "61.074.829/0087-01",
                    "SIM",
                    "ALIAS A; Nome histórico A",
                    "LGE",
                    3,
                    "IMPORTAR COMO SUPPLIER GLOBAL",
                ],
                [
                    90002,
                    "FORNECEDOR ESTRANGEIRO B",
                    "N/A",
                    "NÃO",
                    None,
                    "MONDAY",
                    0,
                    "IMPORTAR INATIVO PARA HISTÓRICO; NÃO SUGERIR",
                ],
            ]
        }
    )


def test_extract_is_deterministic_and_preserves_source() -> None:
    raw = _xlsx()
    workbook = load_supplier_workbook(raw, source_name="oficial.xlsx")
    first = build_catalog_document(workbook)
    second = build_catalog_document(load_supplier_workbook(raw, source_name="oficial.xlsx"))

    assert json.dumps(first, ensure_ascii=False, sort_keys=True) == json.dumps(
        second, ensure_ascii=False, sort_keys=True
    )
    assert first["source"] == {
        "file": "oficial.xlsx",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sheet": "Fornecedores_Hub",
    }
    assert first["summary"] == {"suppliers": 2, "active": 1, "inactive": 1, "aliases": 2}
    assert first["suppliers"][0]["tax_id"] == "61074829008701"
    assert first["suppliers"][1]["tax_id"] is None
    assert validate_catalog(parse_catalog(first)) == []


def _supplier(code: str, *, tax_id: str | None = None, name: str = "Fornecedor") -> CatalogSupplier:
    return CatalogSupplier(code, name, None, tax_id, True, (), 2)


def test_validate_rejects_duplicate_code_tax_id_and_missing_name() -> None:
    catalog = SupplierCatalog(
        (
            _supplier("100", tax_id="11111111000111"),
            _supplier("100", tax_id="22222222000122"),
            _supplier("200", tax_id="11111111000111"),
            _supplier("300", name=""),
        )
    )
    errors = validate_catalog(catalog)
    assert any("corporate_code duplicado" in error for error in errors)
    assert any("também pertence ao código 100" in error for error in errors)
    assert any("legal_name obrigatório" in error for error in errors)


def test_validate_requires_real_boolean_and_nonempty_alias() -> None:
    item = CatalogSupplier("100", "Fornecedor", None, None, "SIM", ("",), 2)  # type: ignore[arg-type]
    errors = validate_catalog(SupplierCatalog((item,)))
    assert any("active deve ser boolean" in error for error in errors)
    assert any("alias vazio ou inválido" in error for error in errors)
