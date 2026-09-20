"""Dry-run puro: não abre sessão de banco e não persiste dados."""

from __future__ import annotations

from collections.abc import Iterable

from app.modules.monday_import.normalization import canonical_text
from app.modules.monday_import.reconciliation import count_records
from app.modules.monday_import.schemas import (
    DryRunReport,
    ImportIssueData,
    MappingCatalog,
    ParsedEquipment,
    ParsedWorkbook,
)


def merge_workbooks(
    workbooks: Iterable[ParsedWorkbook],
) -> tuple[list[ParsedEquipment], int]:
    """Mescla snapshots; o último registro da mesma identidade prevalece."""
    equipment_by_key: dict[tuple[str, str], ParsedEquipment] = {}
    duplicate_records = 0
    for workbook in workbooks:
        board = canonical_text(workbook.board_title)
        for equipment in workbook.equipments:
            key = (board, equipment.source_key)
            previous = equipment_by_key.get(key)
            if previous is not None:
                duplicate_records += 1
                previous_components = {item.source_key for item in previous.components}
                duplicate_records += sum(
                    item.source_key in previous_components for item in equipment.components
                )
            equipment_by_key[key] = equipment
    return list(equipment_by_key.values()), duplicate_records


def _unmapped(values: Iterable[str | None], known: frozenset[str]) -> list[str]:
    known_keys = {canonical_text(value) for value in known}
    unique = {value for value in values if value is not None and canonical_text(value) not in known_keys}
    return sorted(unique, key=canonical_text)


def build_dry_run_report(
    workbooks: Iterable[ParsedWorkbook], mapping_catalog: MappingCatalog | None = None
) -> DryRunReport:
    parsed = list(workbooks)
    catalog = mapping_catalog or MappingCatalog()
    equipments, duplicate_records = merge_workbooks(parsed)
    issues: list[ImportIssueData] = [issue for item in parsed for issue in item.issues]
    counts = count_records(equipments)
    responsibles = [
        value
        for equipment in equipments
        if isinstance((value := equipment.normalized.get("responsible_name")), str)
    ]
    areas = [
        value for equipment in equipments if isinstance((value := equipment.normalized.get("area_name")), str)
    ]
    work_packages: list[str] = []
    for equipment in equipments:
        codes = equipment.normalized.get("work_package_codes")
        if isinstance(codes, list):
            work_packages.extend(code for code in codes if isinstance(code, str))
    unknown_fields = sorted(
        {
            *(f"equipment:{field}" for item in parsed for field in item.unknown_equipment_fields),
            *(f"component:{field}" for item in parsed for field in item.unknown_component_fields),
        },
        key=canonical_text,
    )
    return DryRunReport(
        files=[item.source_file for item in parsed],
        board_titles=sorted(
            {item.board_title for item in parsed if item.board_title is not None},
            key=canonical_text,
        ),
        equipments=counts.equipments,
        components=counts.components,
        groups=counts.groups,
        unknown_fields=unknown_fields,
        invalid_dates=sum(issue.code == "invalid_date" for issue in issues),
        unmapped_responsibles=_unmapped(responsibles, catalog.responsible_names),
        unmapped_areas=_unmapped(areas, catalog.area_names),
        unmapped_work_packages=_unmapped(work_packages, catalog.work_package_codes),
        duplicate_records=duplicate_records,
        warnings=sum(issue.severity == "warning" for issue in issues),
        errors=sum(issue.severity == "error" for issue in issues),
        issues=issues,
    )
