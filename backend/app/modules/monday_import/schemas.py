"""Contratos internos do importador Monday.

Os schemas são dataclasses deliberadamente independentes do banco. Isso mantém
parser, dry-run e reconciliação utilizáveis sem uma conexão de produção.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
RecordKind = Literal["equipment", "component"]
IssueSeverity = Literal["warning", "error"]


@dataclass(slots=True)
class ImportIssueData:
    code: str
    message: str
    severity: IssueSeverity = "warning"
    row_number: int | None = None
    field: str | None = None
    raw_value: JsonValue = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParsedComponent:
    source_file: str
    sheet_name: str
    board_title: str | None
    group_name: str
    row_number: int
    source_key: str
    external_id: str | None
    raw: dict[str, JsonValue]
    normalized: dict[str, JsonValue]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParsedEquipment:
    source_file: str
    sheet_name: str
    board_title: str | None
    group_name: str
    row_number: int
    source_key: str
    raw: dict[str, JsonValue]
    normalized: dict[str, JsonValue]
    components: list[ParsedComponent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ParsedWorkbook:
    source_file: str
    file_sha256: str
    board_title: str | None
    sheet_name: str
    equipments: list[ParsedEquipment] = field(default_factory=list)
    issues: list[ImportIssueData] = field(default_factory=list)
    unknown_equipment_fields: set[str] = field(default_factory=set)
    unknown_component_fields: set[str] = field(default_factory=set)

    @property
    def component_count(self) -> int:
        return sum(len(equipment.components) for equipment in self.equipments)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "file_sha256": self.file_sha256,
            "board_title": self.board_title,
            "sheet_name": self.sheet_name,
            "equipments": [item.to_dict() for item in self.equipments],
            "issues": [item.to_dict() for item in self.issues],
            "unknown_equipment_fields": sorted(self.unknown_equipment_fields),
            "unknown_component_fields": sorted(self.unknown_component_fields),
        }


@dataclass(slots=True, frozen=True)
class MappingCatalog:
    """Valores conhecidos no Hub para avaliar lacunas sem criar entidades."""

    responsible_names: frozenset[str] = frozenset()
    area_names: frozenset[str] = frozenset()
    work_package_codes: frozenset[str] = frozenset()


@dataclass(slots=True)
class GroupCount:
    equipments: int = 0
    components: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class DryRunReport:
    files: list[str]
    board_titles: list[str]
    equipments: int
    components: int
    groups: dict[str, GroupCount]
    unknown_fields: list[str]
    invalid_dates: int
    unmapped_responsibles: list[str]
    unmapped_areas: list[str]
    unmapped_work_packages: list[str]
    duplicate_records: int
    warnings: int
    errors: int
    issues: list[ImportIssueData]

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": self.files,
            "board_titles": self.board_titles,
            "equipments": self.equipments,
            "components": self.components,
            "groups": {name: count.to_dict() for name, count in self.groups.items()},
            "unknown_fields": self.unknown_fields,
            "invalid_dates": self.invalid_dates,
            "unmapped_responsibles": self.unmapped_responsibles,
            "unmapped_areas": self.unmapped_areas,
            "unmapped_work_packages": self.unmapped_work_packages,
            "duplicate_records": self.duplicate_records,
            "warnings": self.warnings,
            "errors": self.errors,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True, frozen=True)
class StageImportResult:
    batch_id: str
    created: bool
    records: int
    issues: int


def source_filename(source: str | Path) -> str:
    return Path(source).name
