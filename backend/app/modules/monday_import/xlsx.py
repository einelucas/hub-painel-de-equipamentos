"""Leitor XLSX mínimo, somente leitura e protegido contra arquivos excessivos.

O XLSX é um contêiner ZIP. Ler apenas as partes necessárias evita transformar
as planilhas de referência em dependência de runtime ou em arquivos de produção.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Literal
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF_RE = re.compile(r"([A-Z]+)(\d+)")
_MAX_ENTRIES = 2_000
_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
_MAX_ROWS = 100_000
_MAX_COLUMNS = 1_024


class XlsxReadError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class XlsxCell:
    coordinate: str
    value: Any
    formula: str | None = None


@dataclass(slots=True, frozen=True)
class XlsxRow:
    number: int
    cells: dict[int, XlsxCell]

    def value(self, column: int) -> Any:
        cell = self.cells.get(column)
        return None if cell is None else cell.value


@dataclass(slots=True, frozen=True)
class XlsxSheet:
    name: str
    rows: list[XlsxRow]
    excel_epoch: Literal["1900", "1904"]


def _column_number(reference: str) -> int:
    match = _CELL_REF_RE.fullmatch(reference)
    if match is None:
        raise XlsxReadError(f"referência de célula inválida: {reference!r}")
    number = 0
    for char in match.group(1):
        number = number * 26 + ord(char) - ord("A") + 1
    if number > _MAX_COLUMNS:
        raise XlsxReadError(f"planilha excede {_MAX_COLUMNS} colunas")
    return number


def _parse_scalar(text: str | None) -> Any:
    if text is None or text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return text
    return int(number) if number.is_integer() else number


def _xml(data: bytes, part: str) -> ElementTree.Element:
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise XlsxReadError(f"XML inválido em {part}") from exc


def _safe_part(target: str) -> str:
    normalized = posixpath.normpath(posixpath.join("xl", target)).lstrip("/")
    if normalized.startswith("../") or not normalized.startswith("xl/"):
        raise XlsxReadError(f"relação XLSX insegura: {target!r}")
    return normalized


def _read_shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = _xml(archive.read("xl/sharedStrings.xml"), "xl/sharedStrings.xml")
    except KeyError:
        return []
    return ["".join(node.itertext()) for node in root.findall(f"{{{_MAIN_NS}}}si")]


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> tuple[Any, str | None]:
    cell_type = cell.get("t")
    formula_node = cell.find(f"{{{_MAIN_NS}}}f")
    formula = None if formula_node is None else formula_node.text
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{_MAIN_NS}}}is")
        return (None if inline is None else "".join(inline.itertext())), formula
    value_node = cell.find(f"{{{_MAIN_NS}}}v")
    text = None if value_node is None else value_node.text
    if cell_type in {"str", "e"}:
        return text, formula
    if cell_type == "s":
        try:
            return shared_strings[int(text or "")], formula
        except (ValueError, IndexError) as exc:
            raise XlsxReadError("índice inválido em sharedStrings") from exc
    if cell_type == "b":
        return text == "1", formula
    return _parse_scalar(text), formula


def read_first_sheet(source: bytes | bytearray | str | Path | BinaryIO) -> XlsxSheet:
    if isinstance(source, bytes | bytearray):
        stream: BinaryIO | str | Path = BytesIO(source)
    else:
        stream = source
    try:
        archive = ZipFile(stream)
    except (BadZipFile, OSError) as exc:
        raise XlsxReadError("arquivo não é um XLSX/ZIP válido") from exc

    with archive:
        infos = archive.infolist()
        if len(infos) > _MAX_ENTRIES:
            raise XlsxReadError("XLSX contém entradas demais")
        if sum(info.file_size for info in infos) > _MAX_UNCOMPRESSED_BYTES:
            raise XlsxReadError("XLSX excede o limite descompactado de 64 MiB")

        try:
            workbook = _xml(archive.read("xl/workbook.xml"), "xl/workbook.xml")
            relationships = _xml(archive.read("xl/_rels/workbook.xml.rels"), "xl/_rels/workbook.xml.rels")
        except KeyError as exc:
            raise XlsxReadError("XLSX sem workbook ou relacionamentos") from exc

        workbook_pr = workbook.find(f"{{{_MAIN_NS}}}workbookPr")
        epoch: Literal["1900", "1904"] = (
            "1904" if workbook_pr is not None and workbook_pr.get("date1904") in {"1", "true"} else "1900"
        )
        relationship_targets = {
            item.get("Id"): item.get("Target")
            for item in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship")
        }
        sheets = workbook.find(f"{{{_MAIN_NS}}}sheets")
        if sheets is None:
            raise XlsxReadError("workbook sem planilhas")
        selected = next((sheet for sheet in sheets if sheet.get("state", "visible") == "visible"), None)
        if selected is None:
            raise XlsxReadError("workbook sem planilha visível")
        relation_id = selected.get(f"{{{_REL_NS}}}id")
        target = relationship_targets.get(relation_id)
        if target is None:
            raise XlsxReadError("planilha visível sem relacionamento")
        sheet_part = _safe_part(target)
        try:
            sheet_root = _xml(archive.read(sheet_part), sheet_part)
        except KeyError as exc:
            raise XlsxReadError(f"parte de planilha ausente: {sheet_part}") from exc
        shared_strings = _read_shared_strings(archive)

        rows: list[XlsxRow] = []
        sheet_data = sheet_root.find(f"{{{_MAIN_NS}}}sheetData")
        if sheet_data is None:
            return XlsxSheet(selected.get("name", "Sheet1"), [], epoch)
        for row_node in sheet_data.findall(f"{{{_MAIN_NS}}}row"):
            if len(rows) >= _MAX_ROWS:
                raise XlsxReadError(f"planilha excede {_MAX_ROWS} linhas")
            row_number = int(row_node.get("r", str(len(rows) + 1)))
            cells: dict[int, XlsxCell] = {}
            for cell_node in row_node.findall(f"{{{_MAIN_NS}}}c"):
                coordinate = cell_node.get("r")
                if coordinate is None:
                    continue
                column = _column_number(coordinate)
                value, formula = _cell_value(cell_node, shared_strings)
                cells[column] = XlsxCell(coordinate, value, formula)
            rows.append(XlsxRow(row_number, cells))
        return XlsxSheet(selected.get("name", "Sheet1"), rows, epoch)
