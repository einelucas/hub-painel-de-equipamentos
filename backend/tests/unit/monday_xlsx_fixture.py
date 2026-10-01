"""Construtor em memória de fixtures XLSX mínimas e legíveis."""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def build_xlsx(rows: list[list[Any]]) -> bytes:
    return build_workbook({"equipamentos - teste": rows})


def build_workbook(sheets: dict[str, list[list[Any]]]) -> bytes:
    """XLSX com várias abas nomeadas, na ordem do dicionário."""
    sheet_entries: list[str] = []
    relationship_entries: list[str] = []
    parts: dict[str, str] = {}
    for index, (name, rows) in enumerate(sheets.items(), start=1):
        sheet_entries.append(f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>')
        relationship_entries.append(
            f'<Relationship Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        parts[f"xl/worksheets/sheet{index}.xml"] = _worksheet(rows)
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(sheet_entries)}</sheets>'
        "</workbook>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(relationship_entries)}</Relationships>'
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        for part, content in parts.items():
            archive.writestr(part, content)
    return output.getvalue()


def _worksheet(rows: list[list[Any]]) -> str:
    xml_rows: list[str] = []
    for row_number, values in enumerate(rows, start=1):
        cells: list[str] = []
        for column, value in enumerate(values, start=1):
            if value is None:
                continue
            reference = f"{_column_name(column)}{row_number}"
            if isinstance(value, bool):
                cells.append(f'<c r="{reference}" t="b"><v>{int(value)}</v></c>')
            elif isinstance(value, int | float):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{reference}" t="str"><v>{escape(str(value))}</v></c>')
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )


def representative_xlsx(*, duplicate_component: bool = False) -> bytes:
    rows = [
        ["Equipamentos - Teste"],
        ["Fase 0 - Nova Demanda"],
        [],
        [
            "Name",
            "Subelementos",
            "A.Status",
            "0.Startup/Grãos",
            "Work Package",
            "1.Equalização",
            "Coluna futura",
        ],
        ["Bomba principal", "Motor", "0.Nova demanda", 46687, "CAL012, CIV014", "v", "raw"],
        ["Subitems", "Name", "ID do elemento", "0.Startup/Grãos", "Frete (Dias)"],
        [None, "Motor", "123456", "2027/10/27", 10],
    ]
    if duplicate_component:
        rows.append([None, "Motor reserva", "123456", "27/10/2027", 5])
    return build_xlsx(rows)
