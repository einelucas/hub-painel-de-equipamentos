"""Parser semântico para a exportação hierárquica XLSX do Monday.

O formato (título do board, grupos, cabeçalho principal, linhas de item,
cabeçalho e linhas de subitens) é o do Monday; o que muda entre boards —
nomes de colunas, títulos, rótulos de status, identidade — vem do ImportProfile.
Não há nenhuma regra específica de board neste módulo.
"""

from __future__ import annotations

import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any, BinaryIO, Literal

from app.modules.monday_import.mappings import (
    BOOLEAN_FIELDS,
    DATE_FIELDS,
    DATE_LIST_FIELDS,
    NONNEGATIVE_INTEGER_FIELDS,
    SIGNED_INTEGER_FIELDS,
    fallback_component_key,
    parent_name_ordinal_component_key,
    provisional_equipment_key,
)
from app.modules.monday_import.normalization import (
    NormalizationError,
    canonical_header,
    clean_text,
    json_value,
    normalize_boolean,
    normalize_date,
    normalize_date_list,
    normalize_decimal,
    normalize_external_id,
    normalize_integer,
    normalize_multi_value,
    normalized_name,
)
from app.modules.monday_import.profile import STATUS_CONCEPT, ImportProfile, SectionRules, default_profile
from app.modules.monday_import.schemas import (
    ImportIssueData,
    ParsedComponent,
    ParsedEquipment,
    ParsedWorkbook,
)
from app.modules.monday_import.xlsx import XlsxRow, read_first_sheet

PARSER_VERSION = "monday-xlsx-v4"


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


def _has_signature(headers: set[str], section: SectionRules) -> bool:
    aliases = section.alias_map()
    present = {aliases[header] for header in headers if header in aliases}
    return set(section.header_signature).issubset(present)


def _is_main_header(row: XlsxRow, profile: ImportProfile) -> bool:
    headers = {canonical_header(value) for _, value in _meaningful(row)}
    return _has_signature(headers, profile.equipment)


def _is_component_header(row: XlsxRow, profile: ImportProfile) -> bool:
    values = _meaningful(row)
    if not values:
        return False
    markers = {canonical_header(marker) for marker in profile.component.header_markers}
    headers = {canonical_header(value) for _, value in values}
    return canonical_header(values[0][1]) in markers and _has_signature(headers, profile.component)


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


def _normalize_fields(
    fields: dict[str, Any],
    *,
    epoch: Literal["1900", "1904"],
    row_number: int,
    issues: list[ImportIssueData],
    profile: ImportProfile,
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for field, raw_value in fields.items():
        try:
            value: Any
            if field in DATE_FIELDS:
                value = normalize_date(raw_value, excel_epoch=epoch)
            elif field in DATE_LIST_FIELDS:
                value = normalize_date_list(raw_value, excel_epoch=epoch)
            elif field in BOOLEAN_FIELDS:
                value = normalize_boolean(raw_value, empty=None)
            elif field in NONNEGATIVE_INTEGER_FIELDS:
                value = normalize_integer(raw_value, allow_negative=False)
            elif field in SIGNED_INTEGER_FIELDS:
                value = normalize_integer(raw_value)
            elif field == "work_package_codes":
                value = normalize_multi_value(raw_value)
            elif field in {"external_id", "supplier_corporate_code"}:
                value = normalize_external_id(raw_value)
            elif field == STATUS_CONCEPT:
                value = profile.resolve_stage(raw_value).stage
            elif field in {"capex_estimated", "planned_cost_candidate"}:
                value = normalize_decimal(raw_value)
            else:
                value = clean_text(raw_value)
            normalized[field] = json_value(value)
        except NormalizationError as exc:
            code = "invalid_date" if field in DATE_FIELDS | DATE_LIST_FIELDS else "invalid_value"
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


def _concept_column(headers: dict[int, str], aliases: dict[str, str], concept: str) -> int | None:
    return next(
        (column for column, header in headers.items() if aliases.get(canonical_header(header)) == concept),
        None,
    )


def _register_headers(
    headers: dict[int, str],
    section: SectionRules,
    *,
    level: str,
    unknown: set[str],
    issues: list[ImportIssueData],
    row_number: int,
) -> None:
    """Separa UNKNOWN de IGNORED_BY_PROFILE e acusa coluna obrigatória ausente."""
    aliases = section.alias_map()
    ignored = section.ignored_set()
    present: set[str] = set()
    for header in headers.values():
        key = canonical_header(header)
        if key in aliases:
            present.add(aliases[key])
        elif key not in ignored:
            unknown.add(header)
    for concept in section.required:
        if concept not in present:
            issues.append(
                ImportIssueData(
                    code="missing_required_column",
                    message=f"{level}: coluna obrigatória do profile ausente para '{concept}'",
                    severity="error",
                    row_number=row_number,
                    field=concept,
                )
            )


def parse_monday_xlsx(
    source: bytes | bytearray | str | Path | BinaryIO,
    *,
    source_name: str | None = None,
    profile: ImportProfile | None = None,
) -> ParsedWorkbook:
    """`profile=None` usa o profile histórico versionado (comportamento anterior)."""
    profile = profile or default_profile()
    equipment_aliases = profile.equipment.alias_map()
    component_aliases = profile.component.alias_map()
    equipment_id_concept = profile.equipment.external_id_concept
    component_id_concept = profile.component.external_id_concept
    data, filename = _source_bytes(source, source_name)
    sheet = read_first_sheet(data)
    result = ParsedWorkbook(
        source_file=filename,
        file_sha256=sha256(data).hexdigest(),
        board_title=None,
        sheet_name=sheet.name,
        import_profile=profile.identity(),
    )
    current_group: str | None = None
    main_headers: dict[int, str] = {}
    component_headers: dict[int, str] = {}
    current_equipment: ParsedEquipment | None = None
    equipment_keys: set[str] = set()
    equipment_ids: set[str] = set()
    component_ids: set[str] = set()
    sibling_names: Counter[str] = Counter()

    for row in sheet.rows:
        values = _meaningful(row)
        if not values:
            continue
        first_text = clean_text(values[0][1])
        single_cell_title = len(values) == 1 and values[0][0] == 1

        if single_cell_title and profile.is_board_title(first_text):
            result.board_title = first_text
            continue
        if single_cell_title and profile.is_group_title(first_text):
            current_group = first_text
            current_equipment = None
            component_headers = {}
            continue
        if _is_main_header(row, profile):
            main_headers = _headers(row)
            component_headers = {}
            current_equipment = None
            _register_headers(
                main_headers,
                profile.equipment,
                level="equipment",
                unknown=result.unknown_equipment_fields,
                issues=result.issues,
                row_number=row.number,
            )
            continue
        if _is_component_header(row, profile):
            component_headers = _headers(row)
            _register_headers(
                component_headers,
                profile.component,
                level="component",
                unknown=result.unknown_component_fields,
                issues=result.issues,
                row_number=row.number,
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

        # Formato Monday: dentro de um bloco de subitens, a coluna do marcador
        # ("Subitems") fica vazia nas linhas de subitem e preenchida no próximo item.
        marker_column = min(component_headers) if component_headers else None
        in_subitem_row = marker_column is not None and clean_text(row.value(marker_column)) is None
        main_name_column = _concept_column(main_headers, equipment_aliases, "name")
        equipment_name = (
            None
            if main_name_column is None or in_subitem_row
            else clean_text(row.value(main_name_column))
        )
        if equipment_name is not None:
            fields = _row_by_field(row, main_headers, equipment_aliases)
            normalized = _normalize_fields(
                fields,
                epoch=sheet.excel_epoch,
                row_number=row.number,
                issues=result.issues,
                profile=profile,
            )
            normalized["name"] = equipment_name
            normalized["group_name"] = current_group
            stage = profile.resolve_stage(fields.get(STATUS_CONCEPT))
            normalized["stage_not_applicable"] = stage.not_applicable or profile.group_is_not_applicable(
                current_group
            )
            if stage.operational_status is not None:
                # Estado operacional declarado no profile; a fase segue a regra do grupo.
                normalized["operational_status"] = stage.operational_status
            if not stage.recognized:
                # Valor preservado no raw; nunca vira estágio 0 nem cai no grupo em silêncio.
                normalized["current_stage_unrecognized"] = True
                result.issues.append(
                    ImportIssueData(
                        code="unknown_status_value",
                        message="status da origem não reconhecido pelo profile",
                        row_number=row.number,
                        field=STATUS_CONCEPT,
                        raw_value=json_value(fields.get(STATUS_CONCEPT)),
                    )
                )
            if not profile.groups.stage_fallback_from_group:
                normalized["stage_from_group_allowed"] = False

            item_id = normalized.get(equipment_id_concept) if equipment_id_concept else None
            if isinstance(item_id, str):
                key = f"monday-item-id:{item_id}"
                if item_id in equipment_ids:
                    result.issues.append(
                        ImportIssueData(
                            code="duplicate_equipment_external_id",
                            message="ID do item de equipamento repetido no arquivo",
                            severity="error",
                            row_number=row.number,
                            field=equipment_id_concept,
                            raw_value=item_id,
                        )
                    )
                equipment_ids.add(item_id)
            else:
                key = provisional_equipment_key(equipment_name)
                result.issues.append(
                    ImportIssueData(
                        code="fragile_equipment_identity",
                        message="equipamento sem ID estável na origem; identidade por nome normalizado",
                        row_number=row.number,
                        field=equipment_id_concept or "name",
                    )
                )
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
            sibling_names = Counter()
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

        component_name_column = _concept_column(component_headers, component_aliases, "name")
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
            fields = _row_by_field(row, component_headers, component_aliases)
            normalized = _normalize_fields(
                fields,
                epoch=sheet.excel_epoch,
                row_number=row.number,
                issues=result.issues,
                profile=profile,
            )
            normalized["name"] = component_name
            external_id = normalized.get(component_id_concept) if component_id_concept else None
            if not isinstance(external_id, str):
                external_id = None
            sibling_names[normalized_name(component_name)] += 1
            ordinal = sibling_names[normalized_name(component_name)]
            if external_id is None and profile.component.identity_fallback == "parent_name_ordinal":
                source_key = parent_name_ordinal_component_key(
                    current_equipment.source_key, component_name, ordinal
                )
                result.issues.append(
                    ImportIssueData(
                        code="fragile_component_identity",
                        message="subitem sem ID do elemento; identidade pelo equipamento pai, nome e ordem",
                        row_number=row.number,
                        field=component_id_concept or "external_id",
                    )
                )
            elif external_id is None:
                source_key = fallback_component_key(current_equipment.source_key, component_name, row.number)
                result.issues.append(
                    ImportIssueData(
                        code="missing_component_external_id",
                        message="subitem sem ID do elemento; usada chave de fallback não definitiva",
                        row_number=row.number,
                        field=component_id_concept or "external_id",
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
        if profile.board.title_required:
            result.issues.append(
                ImportIssueData(
                    code="board_not_recognized",
                    message=f"nenhum título de board compatível com o profile '{profile.profile_id}'",
                    severity="error",
                )
            )
        else:
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
