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
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="equipamentos - teste" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return output.getvalue()


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
