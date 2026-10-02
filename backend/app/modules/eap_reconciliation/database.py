"""Comparação READ-ONLY dos equipamentos reconciliados com um banco já migrado.

Usa SQL cru só com colunas que existem desde a migration 0009 (o DEV ainda não
tem `eap_node`/`eap_prefix`) e roda dentro de `SET TRANSACTION READ ONLY`:
qualquer escrita acidental falharia no próprio PostgreSQL.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eap import comparable_eap_name
from app.modules.monday_import.mappings import SOURCE_SYSTEM

_EQUIPMENT_MAPPINGS = text(
    """
    SELECT em.external_id, e.id AS equipment_id, e.name, a.name AS area_name,
           u.code AS unit_code, pc.code AS context_code
    FROM external_mapping em
    JOIN equipment e ON e.id = em.target_entity_id
    JOIN project_context pc ON pc.id = em.project_context_id
    JOIN unit u ON u.id = pc.unit_id
    LEFT JOIN area a ON a.id = e.area_id
    WHERE em.source_system = :source AND em.source_entity_type = 'equipment'
    """
)


async def compare_with_database(session: AsyncSession, report: dict[str, Any]) -> dict[str, Any]:
    await session.execute(text("SET TRANSACTION READ ONLY"))
    database = (await session.execute(text("SELECT current_database()"))).scalar_one()
    revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    rows = (await session.execute(_EQUIPMENT_MAPPINGS, {"source": SOURCE_SYSTEM})).mappings().all()
    equipment_total = (await session.execute(text("SELECT count(*) FROM equipment"))).scalar_one()
    unmapped = (
        (
            await session.execute(
                text(
                    "SELECT e.name FROM equipment e WHERE NOT EXISTS ("
                    "SELECT 1 FROM external_mapping em WHERE em.target_entity_id = e.id "
                    "AND em.source_entity_type = 'equipment') ORDER BY e.name"
                )
            )
        )
        .scalars()
        .all()
    )
    await session.rollback()

    duplicates = sorted(
        key for key, count in Counter(row["external_id"] for row in rows).items() if count > 1
    )
    by_key = {row["external_id"]: row for row in rows}
    records = report["records"]
    export_keys = {record["externalId"] for record in records}

    for record in records:
        row = by_key.get(record["externalId"])
        if row is None:
            record["database"] = None
            continue
        legacy = row["area_name"]
        eap_name = record["matchedEapName"]
        if eap_name is None:
            comparison = "NO_EAP_MATCH"
        elif legacy is None:
            comparison = "NO_LEGACY_AREA"
        elif comparable_eap_name(legacy) == comparable_eap_name(eap_name):
            comparison = "SAME_NAME"
        else:
            comparison = "DIFFERENT_NAME"
        record["database"] = {
            "equipmentName": row["name"],
            "legacyAreaName": legacy,
            "legacyAreaVsEap": comparison,
        }

    return {
        "database": database,
        "alembicRevision": revision,
        "equipmentTotal": equipment_total,
        "mappedEquipments": len(rows),
        "matchedExportAndDatabase": len(export_keys & by_key.keys()),
        "exportWithoutEquipment": sorted(export_keys - by_key.keys()),
        "equipmentWithoutExport": sorted(
            row["name"] for key, row in by_key.items() if key not in export_keys
        ),
        "equipmentWithoutMapping": list(unmapped),
        "duplicateExternalIds": duplicates,
        "contexts": sorted({f"{row['unit_code']}/{row['context_code']}" for row in rows}),
        "legacyAreaVsEap": dict(
            sorted(Counter(r["database"]["legacyAreaVsEap"] for r in records if r.get("database")).items())
        ),
    }
