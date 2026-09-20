"""Parser semântico para a exportação hierárquica XLSX do Monday."""

from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO, Literal

from app.modules.monday_import.mappings import (
    BOOLEAN_FIELDS,
    COMPONENT_FIELDS,
    DATE_FIELDS,
    EQUIPMENT_FIELDS,
    NONNEGATIVE_INTEGER_FIELDS,
    SIGNED_INTEGER_FIELDS,
    fallback_component_key,
    provisional_equipment_key,
)
from app.modules.monday_import.normalization import (
    NormalizationError,
    canonical_header,
    canonical_text,
    clean_text,
    json_value,
    normalize_boolean,
    normalize_date,
    normalize_decimal,
    normalize_external_id,
    normalize_integer,
    normalize_multi_value,
)
from app.modules.monday_import.schemas import (
    ImportIssueData,
    ParsedComponent,
    ParsedEquipment,
    ParsedWorkbook,
)
from app.modules.monday_import.xlsx import XlsxRow, read_first_sheet

PARSER_VERSION = "monday-xlsx-v1"
_STAGE_RE = re.compile(r"(?:^|\s)([0-8])(?:\.|\s|$)")


def _source_bytes(
    source: bytes | bytearray | str | Path | BinaryIO, source_name: str | None
) -> tuple[bytes, str]:
    if isinstance(source, bytes | bytearray):
        return bytes(source), source_name or "upload.xlsx"
    if isinstance(source, str | Path):
        path = Path(source)
        return path.read_bytes(), source_name or path.name
    data = source.read()
    if not isinstance(data, bytes):
        raise TypeError("a fonte XLSX deve produzir bytes")
    return data, source_name or Path(getattr(source, "name", "upload.xlsx")).name


def _meaningful(row: XlsxRow) -> list[tuple[int, Any]]:
    return [
        (column, cell.value)
        for column, cell in sorted(row.cells.items())
        if clean_text(cell.value) is not None
    ]


def _is_main_header(row: XlsxRow) -> bool:
    headers = {canonical_header(value) for _, value in _meaningful(row)}
    return {"name", "subelementos", "a status"}.issubset(headers)


def _is_component_header(row: XlsxRow) -> bool:
    values = _meaningful(row)
    if not values:
        return False
    headers = {canonical_header(value) for _, value in values}
    return canonical_header(values[0][1]) in {"subitems", "subitem"} and "name" in headers


def _is_summary_row(row: XlsxRow) -> bool:
    raw_values = [cell.value for cell in row.cells.values()]
    return any(
        (isinstance(value, str) and value.strip().casefold() == "null")
        or (isinstance(value, str) and re.fullmatch(r"\d+/\d+", value.strip()) is not None)
        for value in raw_values
    )


def _headers(row: XlsxRow) -> dict[int, str]:
    return {
        column: clean_text(cell.value) or f"column_{column}" for column, cell in sorted(row.cells.items())
    }


def _raw_payload(row: XlsxRow, headers: dict[int, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    formulas: dict[str, str] = {}
    for column, header in headers.items():
        key = header
        suffix = 2
        while key in payload:
            key = f"{header}#{suffix}"
            suffix += 1
        cell = row.cells.get(column)
        payload[key] = json_value(None if cell is None else cell.value)
        if cell is not None and cell.formula is not None:
            formulas[key] = cell.formula
    if formulas:
        payload["_cell_formulas"] = formulas
    return payload


def _row_by_field(row: XlsxRow, headers: dict[int, str], field_map: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for column, header in headers.items():
        field = field_map.get(canonical_header(header))
        if field is not None:
            result[field] = row.value(column)
    return result


def _parse_stage(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    match = _STAGE_RE.search(text)
    return None if match is None else int(match.group(1))


def _normalize_fields(
    fields: dict[str, Any],
    *,
    epoch: Literal["1900", "1904"],
    row_number: int,
    issues: list[ImportIssueData],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field, raw_value in fields.items():
        try:
            value: Any
            if field in DATE_FIELDS:
                value = normalize_date(raw_value, excel_epoch=epoch)
            elif field in BOOLEAN_FIELDS:
                value = normalize_boolean(raw_value, empty=None)
            elif field in NONNEGATIVE_INTEGER_FIELDS:
                value = normalize_integer(raw_value, allow_negative=False)
            elif field in SIGNED_INTEGER_FIELDS:
                value = normalize_integer(raw_value)
            elif field == "work_package_codes":
                value = normalize_multi_value(raw_value)
            elif field == "external_id":
                value = normalize_external_id(raw_value)
            elif field == "current_stage":
                value = _parse_stage(raw_value)
            elif field == "capex_estimated":
                value = normalize_decimal(raw_value)
            else:
                value = clean_text(raw_value)
            normalized[field] = json_value(value)
        except NormalizationError as exc:
            code = "invalid_date" if field in DATE_FIELDS else "invalid_value"
            issues.append(
                ImportIssueData(
                    code=code,
                    message=str(exc),
                    severity="error",
                    row_number=row_number,
                    field=field,
                    raw_value=json_value(raw_value),
                )
            )
            normalized[field] = None
    return normalized


def _name_column(headers: dict[int, str]) -> int | None:
    return next((column for column, header in headers.items() if canonical_header(header) == "name"), None)


def parse_monday_xlsx(
    source: bytes | bytearray | str | Path | BinaryIO,
    *,
    source_name: str | None = None,
) -> ParsedWorkbook:
    data, filename = _source_bytes(source, source_name)
    sheet = read_first_sheet(data)
    result = ParsedWorkbook(
        source_file=filename,
        file_sha256=sha256(data).hexdigest(),
        board_title=None,
        sheet_name=sheet.name,
    )
    current_group: str | None = None
    main_headers: dict[int, str] = {}
    component_headers: dict[int, str] = {}
    current_equipment: ParsedEquipment | None = None
    equipment_keys: set[str] = set()
    component_ids: set[str] = set()

    for row in sheet.rows:
        values = _meaningful(row)
        if not values:
            continue
        first_text = clean_text(values[0][1])
        first_canonical = canonical_text(first_text)

        if len(values) == 1 and values[0][0] == 1 and first_canonical.startswith("equipamentos"):
            result.board_title = first_text
            continue
        if len(values) == 1 and values[0][0] == 1 and re.match(r"^fase\s+[0-8]\b", first_canonical):
            current_group = first_text
            current_equipment = None
            component_headers = {}
            continue
        if _is_main_header(row):
            main_headers = _headers(row)
            component_headers = {}
            current_equipment = None
            result.unknown_equipment_fields.update(
                header for header in main_headers.values() if canonical_header(header) not in EQUIPMENT_FIELDS
            )
            continue
        if _is_component_header(row):
            component_headers = _headers(row)
            result.unknown_component_fields.update(
                header
                for header in component_headers.values()
                if canonical_header(header) not in COMPONENT_FIELDS
            )
            if current_equipment is None:
                result.issues.append(
                    ImportIssueData(
                        code="orphan_component_header",
                        message="cabeçalho Subitems encontrado sem equipamento pai",
                        row_number=row.number,
                    )
                )
            continue

        main_name_column = _name_column(main_headers)
        equipment_name = None if main_name_column is None else clean_text(row.value(main_name_column))
        if equipment_name is not None:
            fields = _row_by_field(row, main_headers, EQUIPMENT_FIELDS)
            normalized = _normalize_fields(
                fields, epoch=sheet.excel_epoch, row_number=row.number, issues=result.issues
            )
            normalized["name"] = equipment_name
            normalized["group_name"] = current_group
            key = provisional_equipment_key(equipment_name)
            if key in equipment_keys:
                result.issues.append(
                    ImportIssueData(
                        code="duplicate_provisional_equipment_key",
                        message="nome normalizado de equipamento repetido no arquivo",
                        row_number=row.number,
                        field="name",
                        raw_value=equipment_name,
                    )
                )
            equipment_keys.add(key)
            current_equipment = ParsedEquipment(
                source_file=filename,
                sheet_name=sheet.name,
                board_title=result.board_title,
                group_name=current_group or "Grupo não identificado",
                row_number=row.number,
                source_key=key,
                raw=_raw_payload(row, main_headers),
                normalized=normalized,
            )
            result.equipments.append(current_equipment)
            component_headers = {}
            if current_group is None:
                result.issues.append(
                    ImportIssueData(
                        code="missing_group",
                        message="equipamento encontrado antes de um grupo/fase",
                        row_number=row.number,
                    )
                )
            continue

        component_name_column = _name_column(component_headers)
        component_name = (
            None if component_name_column is None else clean_text(row.value(component_name_column))
        )
        if component_name is not None:
            if current_equipment is None:
                result.issues.append(
                    ImportIssueData(
                        code="orphan_component",
                        message="subitem encontrado sem equipamento pai",
                        severity="error",
                        row_number=row.number,
                        raw_value=component_name,
                    )
                )
                continue
            fields = _row_by_field(row, component_headers, COMPONENT_FIELDS)
            normalized = _normalize_fields(
                fields, epoch=sheet.excel_epoch, row_number=row.number, issues=result.issues
            )
            normalized["name"] = component_name
            external_id = normalized.get("external_id")
            if not isinstance(external_id, str):
                external_id = None
            if external_id is None:
                source_key = fallback_component_key(current_equipment.source_key, component_name, row.number)
                result.issues.append(
                    ImportIssueData(
                        code="missing_component_external_id",
                        message="subitem sem ID do elemento; usada chave de fallback não definitiva",
                        row_number=row.number,
                        field="external_id",
                    )
                )
            else:
                source_key = f"monday-item-id:{external_id}"
                if external_id in component_ids:
                    result.issues.append(
                        ImportIssueData(
                            code="duplicate_component_external_id",
                            message="ID do elemento repetido no arquivo",
                            severity="error",
                            row_number=row.number,
                            field="external_id",
                            raw_value=external_id,
                        )
                    )
                component_ids.add(external_id)
            current_equipment.components.append(
                ParsedComponent(
                    source_file=filename,
                    sheet_name=sheet.name,
                    board_title=result.board_title,
                    group_name=current_equipment.group_name,
                    row_number=row.number,
                    source_key=source_key,
                    external_id=external_id,
                    raw=_raw_payload(row, component_headers),
                    normalized=normalized,
                )
            )
            continue

        # Linhas de resumo do Monday têm o nome vazio e valores como "0/31".
        # Permanecem fora das entidades; qualquer linha não vazia realmente
        # inesperada é registrada para inspeção, sem quebrar o restante.
        if not _is_summary_row(row):
            result.issues.append(
                ImportIssueData(
                    code="unclassified_row",
                    message="linha não vazia não classificada semanticamente",
                    row_number=row.number,
                    raw_value={str(column): json_value(value) for column, value in values},
                )
            )

    if result.board_title is None:
        result.issues.append(
            ImportIssueData(
                code="missing_board_title",
                message="título do board não foi identificado",
            )
        )
    if not main_headers:
        result.issues.append(
            ImportIssueData(
                code="missing_main_header",
                message="cabeçalho principal não foi identificado",
                severity="error",
            )
        )
    return result
