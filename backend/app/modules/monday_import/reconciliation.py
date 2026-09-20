"""Comparação explícita de contagens da origem Monday com o destino Hub."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from app.modules.monday_import.normalization import canonical_text
from app.modules.monday_import.schemas import GroupCount, ParsedEquipment


@dataclass(slots=True, frozen=True)
class ReconciliationCounts:
    equipments: int
    components: int
    groups: dict[str, GroupCount]

    def to_dict(self) -> dict[str, Any]:
        return {
            "equipments": self.equipments,
            "components": self.components,
            "groups": {name: count.to_dict() for name, count in self.groups.items()},
        }


@dataclass(slots=True, frozen=True)
class ReconciliationMismatch:
    scope: str
    metric: str
    source: int
    destination: int


@dataclass(slots=True, frozen=True)
class ReconciliationReport:
    matched: bool
    mismatches: list[ReconciliationMismatch]

    def to_dict(self) -> dict[str, Any]:
        return {"matched": self.matched, "mismatches": [asdict(item) for item in self.mismatches]}


def stage_key(group_name: str) -> str:
    match = re.search(r"\bfase\s*([0-8])\b", canonical_text(group_name))
    return f"Fase {match.group(1)}" if match else group_name


def count_records(equipments: Iterable[ParsedEquipment]) -> ReconciliationCounts:
    items = list(equipments)
    groups: dict[str, GroupCount] = {}
    for equipment in items:
        key = stage_key(equipment.group_name)
        count = groups.setdefault(key, GroupCount())
        count.equipments += 1
        count.components += len(equipment.components)
    return ReconciliationCounts(
        equipments=len(items),
        components=sum(len(item.components) for item in items),
        groups=groups,
    )


def reconcile_counts(source: ReconciliationCounts, destination: ReconciliationCounts) -> ReconciliationReport:
    mismatches: list[ReconciliationMismatch] = []
    for metric in ("equipments", "components"):
        source_value = getattr(source, metric)
        destination_value = getattr(destination, metric)
        if source_value != destination_value:
            mismatches.append(ReconciliationMismatch("TOTAL", metric, source_value, destination_value))
    for group in sorted(source.groups.keys() | destination.groups.keys()):
        source_count = source.groups.get(group, GroupCount())
        destination_count = destination.groups.get(group, GroupCount())
        for metric in ("equipments", "components"):
            source_value = getattr(source_count, metric)
            destination_value = getattr(destination_count, metric)
            if source_value != destination_value:
                mismatches.append(ReconciliationMismatch(group, metric, source_value, destination_value))
    return ReconciliationReport(not mismatches, mismatches)


C2_EXPECTED = ReconciliationCounts(
    equipments=41,
    components=164,
    groups={
        "Fase 0": GroupCount(31, 55),
        "Fase 4": GroupCount(6, 8),
        "Fase 6": GroupCount(3, 77),
        "Fase 8": GroupCount(1, 24),
    },
)
