"""Leitura estrita da planilha oficial do catálogo global de fornecedores."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.modules.monday_import.normalization import (
    canonical_header,
    canonical_text,
    clean_text,
    normalize_external_id,
)
from app.modules.monday_import.xlsx import XlsxReadError, read_first_sheet

SHEET_NAME = "Fornecedores_Hub"
_HEADERS = {
    "corporate_code": "CODIGO_FORNECEDOR",
    "legal_name": "NOME_FORNECEDOR_OFICIAL",
    "tax_id": "DOCUMENTO",
    "active": "ATIVO_BASE_OFICIAL",
    "aliases": "ALIAS_REFERENCIA_ORIGEM",
    "evidence": "EVIDENCIA_CRUZAMENTO",
    "equipment_count": "QTD_EQUIPAMENTOS_RELACIONADOS",
    "action": "ACAO_HUB",
}
_ACTIVE = {"sim": True, "nao": False}


class SupplierWorkbookError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class WorkbookSupplier:
    corporate_code: str
    legal_name: str
    trade_name: str | None
    tax_id: str | None
    active: bool
    aliases: tuple[str, ...]
    source_row: int
    evidence: str | None
    equipment_count: int | None
    action: str


@dataclass(slots=True, frozen=True)
class SupplierWorkbook:
    source_file: str
    source_sha256: str
    sheet: str
    suppliers: tuple[WorkbookSupplier, ...]


def _normalize_tax_id(value: Any, row: int) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) != 14:
        raise SupplierWorkbookError(f"linha {row}: DOCUMENTO deve ser CNPJ com 14 dígitos ou N/A")
    return digits


def _active(value: Any, row: int) -> bool:
    normalized = canonical_text(value)
    try:
        return _ACTIVE[normalized]
    except KeyError as exc:
        raise SupplierWorkbookError(
            f"linha {row}: ATIVO_BASE_OFICIAL inválido {value!r}; esperado SIM ou NÃO"
        ) from exc


def _aliases(value: Any) -> tuple[str, ...]:
    result: list[str] = []
    for raw in str(value or "").split(";"):
        alias = clean_text(raw)
        if alias is not None and alias not in result:
            result.append(alias)
    return tuple(result)


def _integer(value: Any, row: int) -> int | None:
    if value is None or clean_text(value) is None:
        return None
    if isinstance(value, bool):
        raise SupplierWorkbookError(f"linha {row}: quantidade inválida {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SupplierWorkbookError(f"linha {row}: quantidade inválida {value!r}") from exc
    if number < 0 or float(value) != number:
        raise SupplierWorkbookError(f"linha {row}: quantidade inválida {value!r}")
    return number


def load_supplier_workbook(
    source: bytes | str | Path, *, source_name: str | None = None
) -> SupplierWorkbook:
    if isinstance(source, bytes):
        raw, name = source, source_name or "fornecedores.xlsx"
    else:
        path = Path(source)
        raw, name = path.read_bytes(), source_name or path.name
    try:
        sheet = read_first_sheet(raw)
    except XlsxReadError as exc:
        raise SupplierWorkbookError(str(exc)) from exc
    if sheet.name != SHEET_NAME:
        raise SupplierWorkbookError(f"aba esperada {SHEET_NAME!r}, encontrada {sheet.name!r}")
    if not sheet.rows:
        raise SupplierWorkbookError("planilha vazia")
    header = sheet.rows[0]
    by_header = {canonical_header(cell.value): column for column, cell in header.cells.items()}
    missing = [title for title in _HEADERS.values() if canonical_header(title) not in by_header]
    if missing:
        raise SupplierWorkbookError(f"coluna(s) obrigatória(s) ausente(s): {missing}")

    suppliers: list[WorkbookSupplier] = []
    for row in sheet.rows[1:]:
        values = {
            key: row.value(by_header[canonical_header(title)]) for key, title in _HEADERS.items()
        }
        if all(clean_text(value) is None for value in values.values()):
            continue
        code = normalize_external_id(values["corporate_code"])
        name_value = clean_text(values["legal_name"])
        action = clean_text(values["action"])
        if code is None:
            raise SupplierWorkbookError(f"linha {row.number}: CODIGO_FORNECEDOR obrigatório")
        if name_value is None:
            raise SupplierWorkbookError(f"linha {row.number}: NOME_FORNECEDOR_OFICIAL obrigatório")
        if action is None:
            raise SupplierWorkbookError(f"linha {row.number}: ACAO_HUB obrigatória")
        suppliers.append(
            WorkbookSupplier(
                corporate_code=code,
                legal_name=name_value,
                trade_name=None,
                tax_id=_normalize_tax_id(values["tax_id"], row.number),
                active=_active(values["active"], row.number),
                aliases=_aliases(values["aliases"]),
                source_row=row.number,
                evidence=clean_text(values["evidence"]),
                equipment_count=_integer(values["equipment_count"], row.number),
                action=action,
            )
        )
    return SupplierWorkbook(name, sha256(raw).hexdigest(), sheet.name, tuple(suppliers))
