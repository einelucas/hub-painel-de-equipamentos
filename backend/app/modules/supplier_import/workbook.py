"""Leitura da planilha auditada de fornecedores (LEM C2/F2).

Só lê as abas usadas pela carga e falha explicitamente se um cabeçalho
obrigatório estiver ausente — nunca adivinha a coluna por posição.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.modules.monday_import.normalization import canonical_header, clean_text, normalize_external_id
from app.modules.monday_import.xlsx import XlsxReadError, XlsxSheet, read_sheet

CONFIRMED_SHEET = "Confirmados"
PROBABLE_SHEET = "Prováveis"
AMBIGUOUS_SHEET = "Ambíguos"
NOT_FOUND_SHEET = "Não Encontrados"
EQUIPMENT_SHEET = "Fornecedores F2"

_ALIAS_COLUMNS = {
    "alias": "Nome original Monday",
    "corporate_code": "Código corporativo validado",
    "tax_id": "CNPJ/documento oficial",
    "legal_name": "Razão social oficial",
    "active": "Ativo",
    "classification": "Classificação validada",
}
_EQUIPMENT_COLUMNS = {
    "equipment": "Equipamento",
    "supplier_text": "Fornecedor original",
    "phase": "Fase",
    "status": "A.Status",
    "corporate_code": "Cód. Fornecedor. CS",
    "classification": "Classificação do item",
    "source_file": "Arquivo",
    "source_row": "Linha",
}


class SupplierWorkbookError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class AliasRow:
    """Linha de Confirmados/Prováveis/Ambíguos/Não Encontrados (nível do nome Monday)."""

    sheet: str
    row_number: int
    alias: str | None
    corporate_code: str | None
    tax_id: str | None
    legal_name: str | None
    active: Any
    classification: str | None


@dataclass(slots=True, frozen=True)
class EquipmentRow:
    """Linha de "Fornecedores F2" (nível do equipamento)."""

    row_number: int
    equipment: str | None
    supplier_text: str | None
    phase: str | None
    status: str | None
    corporate_code: str | None
    classification: str | None
    source_file: str | None
    source_row: Any


@dataclass(slots=True)
class SupplierWorkbook:
    source_file: str
    file_sha256: str
    confirmed: list[AliasRow] = field(default_factory=list)
    probable: list[AliasRow] = field(default_factory=list)
    ambiguous: list[AliasRow] = field(default_factory=list)
    not_found: list[AliasRow] = field(default_factory=list)
    equipments: list[EquipmentRow] = field(default_factory=list)


def _table(sheet: XlsxSheet, columns: dict[str, str]) -> list[tuple[int, dict[str, Any]]]:
    if not sheet.rows:
        raise SupplierWorkbookError(f"aba {sheet.name!r} está vazia")
    header = sheet.rows[0]
    by_header = {canonical_header(header.value(column)): column for column in header.cells}
    missing = [title for title in columns.values() if canonical_header(title) not in by_header]
    if missing:
        raise SupplierWorkbookError(f"aba {sheet.name!r} sem coluna(s) obrigatória(s): {missing}")
    rows: list[tuple[int, dict[str, Any]]] = []
    for row in sheet.rows[1:]:
        values = {key: row.value(by_header[canonical_header(title)]) for key, title in columns.items()}
        if all(clean_text(value) is None for value in values.values()):
            continue
        rows.append((row.number, values))
    return rows


def _code(value: Any) -> str | None:
    return normalize_external_id(value)


def _alias_rows(source: bytes, sheet_name: str) -> list[AliasRow]:
    sheet = read_sheet(source, sheet_name)
    return [
        AliasRow(
            sheet=sheet_name,
            row_number=number,
            alias=clean_text(values["alias"]),
            corporate_code=_code(values["corporate_code"]),
            tax_id=clean_text(values["tax_id"]),
            legal_name=clean_text(values["legal_name"]),
            active=values["active"],
            classification=clean_text(values["classification"]),
        )
        for number, values in _table(sheet, _ALIAS_COLUMNS)
    ]


def load_supplier_workbook(source: bytes | str | Path, *, source_name: str | None = None) -> SupplierWorkbook:
    if isinstance(source, bytes):
        data, name = source, source_name or "upload.xlsx"
    else:
        path = Path(source)
        data, name = path.read_bytes(), source_name or path.name
    try:
        workbook = SupplierWorkbook(source_file=name, file_sha256=sha256(data).hexdigest())
        workbook.confirmed = _alias_rows(data, CONFIRMED_SHEET)
        workbook.probable = _alias_rows(data, PROBABLE_SHEET)
        workbook.ambiguous = _alias_rows(data, AMBIGUOUS_SHEET)
        workbook.not_found = _alias_rows(data, NOT_FOUND_SHEET)
        equipment_sheet = read_sheet(data, EQUIPMENT_SHEET)
    except XlsxReadError as exc:
        raise SupplierWorkbookError(str(exc)) from exc
    workbook.equipments = [
        EquipmentRow(
            row_number=number,
            equipment=clean_text(values["equipment"]),
            supplier_text=clean_text(values["supplier_text"]),
            phase=clean_text(values["phase"]),
            status=clean_text(values["status"]),
            corporate_code=_code(values["corporate_code"]),
            classification=clean_text(values["classification"]),
            source_file=clean_text(values["source_file"]),
            source_row=values["source_row"],
        )
        for number, values in _table(equipment_sheet, _EQUIPMENT_COLUMNS)
    ]
    return workbook
