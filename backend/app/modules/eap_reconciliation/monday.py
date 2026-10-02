"""Reconciliação EAP dos equipamentos do Monday — montagem do relatório (sem banco).

Lê os exports com o parser do importador (`parse_monday_xlsx`), usa o MESMO
campo de área (`normalized["area_name"]`) e a MESMA identidade do equipamento
(`source_key`, gravada em `external_mapping.external_id` pelo apply). Os 164
subitens não geram vínculo EAP: a reconciliação é no nível do equipamento pai.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modules.eap_catalog.catalog import EapCatalog
from app.modules.eap_reconciliation.reconcile import (
    CatalogIndex,
    MatchStatus,
    ValueReconciliation,
    reconcile_value,
)
from app.modules.monday_import.parser import parse_monday_xlsx

REPORT_FORMAT_VERSION = 1


@dataclass(slots=True, frozen=True)
class SourceEquipment:
    source_key: str
    name: str
    area_value: str | None
    group_name: str
    source_file: str
    source_row: int


def load_equipments(paths: list[Path]) -> tuple[list[SourceEquipment], list[dict[str, Any]], list[str]]:
    """Equipamentos dos exports, por `source_key`. Devolve também a descrição
    dos arquivos e os conflitos (mesmo equipamento com áreas diferentes entre
    exports) — conflito não é resolvido aqui."""
    by_key: dict[str, list[SourceEquipment]] = defaultdict(list)
    sources: list[dict[str, Any]] = []
    for path in paths:
        workbook = parse_monday_xlsx(path)
        sources.append(
            {
                "file": workbook.source_file,
                "sha256": workbook.file_sha256,
                "boardTitle": workbook.board_title,
                "equipments": len(workbook.equipments),
                "components": sum(len(item.components) for item in workbook.equipments),
            }
        )
        for item in workbook.equipments:
            area = item.normalized.get("area_name")
            by_key[item.source_key].append(
                SourceEquipment(
                    source_key=item.source_key,
                    name=str(item.normalized["name"]),
                    area_value=area if isinstance(area, str) else None,
                    group_name=item.group_name,
                    source_file=item.source_file,
                    source_row=item.row_number,
                )
            )
    conflicts = sorted(key for key, items in by_key.items() if len({item.area_value for item in items}) > 1)
    equipments = [items[0] for _, items in sorted(by_key.items())]
    return equipments, sources, conflicts


def _record(equipment: SourceEquipment, result: ValueReconciliation) -> dict[str, Any]:
    return {
        "externalId": equipment.source_key,
        "equipmentName": equipment.name,
        "rawEapValue": equipment.area_value,
        "observedPrefix": result.observed_prefix,
        "parsedCode": result.parsed_code,
        "parsedLabel": result.parsed_label,
        "matchedEapCode": result.matched_code,
        "matchedEapName": result.matched_name,
        "matchedEapLevel": result.matched_level,
        "status": result.status.value,
        "category": result.category,
        "reason": result.reason,
        "candidates": result.candidates,
        "sourceFile": equipment.source_file,
        "sourceRow": equipment.source_row,
        "group": equipment.group_name,
    }


def build_reconciliation(
    *,
    project: str,
    paths: list[Path],
    catalog: EapCatalog,
) -> dict[str, Any]:
    equipments, sources, conflicts = load_equipments(paths)
    index = CatalogIndex(catalog)
    records = []
    for equipment in equipments:
        result = reconcile_value(equipment.area_value, index)
        if equipment.source_key in conflicts:
            result = ValueReconciliation(
                equipment.area_value,
                MatchStatus.REVIEW_MULTIPLE_EAP,
                "Exports diferentes trazem áreas diferentes para o mesmo equipamento.",
            )
        records.append(_record(equipment, result))

    statuses = Counter(record["status"] for record in records)
    prefixes: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record["observedPrefix"] is not None:
            prefixes[record["observedPrefix"]].append(record["equipmentName"])
    safe = [record for record in records if record["category"] == "MATCH"]
    metrics = {
        "total_equipment": len(records),
        "matched_code_and_name": statuses[MatchStatus.MATCH_CODE_AND_NAME],
        "matched_code": statuses[MatchStatus.MATCH_CODE],
        "matched_unique_name": statuses[MatchStatus.MATCH_UNIQUE_NAME],
        "review_name_mismatch": statuses[MatchStatus.REVIEW_NAME_MISMATCH],
        "review_catalog": statuses[MatchStatus.REVIEW_EAP_CATALOG],
        "review_multiple_eap": statuses[MatchStatus.REVIEW_MULTIPLE_EAP],
        "unresolved_unknown_code": statuses[MatchStatus.UNRESOLVED_UNKNOWN_CODE],
        "unresolved_generic": statuses[MatchStatus.UNRESOLVED_GENERIC_VALUE],
        "unresolved_ambiguous_name": statuses[MatchStatus.UNRESOLVED_AMBIGUOUS_NAME],
        "auto_match_safe_total": len(safe),
    }
    return {
        "format_version": REPORT_FORMAT_VERSION,
        "description": (
            "Relatório de reconciliação READ-ONLY Monday × catálogo EAP oficial. NÃO é seed: "
            "nenhum vínculo é gravado a partir deste arquivo."
        ),
        "project": project,
        "catalog": {"sha256": catalog.sha256, "source": catalog.source.get("file")},
        "sources": sources,
        "metrics": metrics,
        "observed_prefixes": [
            {
                "prefix": prefix,
                "occurrences": len(names),
                "equipments": sorted(names),
            }
            for prefix, names in sorted(prefixes.items())
        ],
        "prefix_consistent": len(prefixes) <= 1,
        "multiple_eap_equipments": [
            record["equipmentName"]
            for record in records
            if record["status"] == MatchStatus.REVIEW_MULTIPLE_EAP
        ],
        "source_conflicts": conflicts,
        "candidate_project_eap_codes": sorted({record["matchedEapCode"] for record in safe}),
        "records": records,
    }


def check_auxiliary_exports(canonical: list[Path], auxiliary: list[Path]) -> dict[str, Any]:
    """Exports parciais do mesmo board: só conferidos (subconjunto e mesma área),
    nunca somados ao universo."""
    base, _, _ = load_equipments(canonical)
    base_area = {item.source_key: item.area_value for item in base}
    extra, sources, _ = load_equipments(auxiliary)
    return {
        "files": [source["file"] for source in sources],
        "equipments": len(extra),
        "subset_of_canonical": all(item.source_key in base_area for item in extra),
        "same_area": all(base_area.get(item.source_key) == item.area_value for item in extra),
    }
