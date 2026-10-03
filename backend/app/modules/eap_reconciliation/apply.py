"""Apply controlado da reconciliação EAP: grava `equipment.eap_node_id` a partir do
JSON versionado de reconciliação — nunca recalcula a reconciliação.

Fluxo: exports Monday → analyze → JSON versionado → validação → apply.

Regras:
- só status seguros (`SAFE_STATUSES`) geram vínculo; REVIEW_* e UNRESOLVED_* são pulados;
- pré-validação COMPLETA antes de qualquer UPDATE; qualquer erro aborta sem escrever;
- `eap_node_id` já igual ao alvo → unchanged; diferente → conflito → aborta tudo;
- transação única; um AuditLog `eap_reconciliation.apply` por vínculo criado;
- não toca em `area_id`, `project_eap`, `project_context.eap_prefix` nem em subitens.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eap import EapLevel
from app.models.equipment import EapNode, Equipment
from app.models.monday_import import ExternalMapping
from app.modules.eap_catalog.catalog import EapCatalog
from app.modules.eap_reconciliation.reconcile import SAFE_STATUSES, MatchStatus, category_of
from app.modules.monday_import.mappings import SOURCE_SYSTEM
from app.shared.audit import record_audit

APPLY_ACTION = "eap_reconciliation.apply"
_LINKABLE_LEVELS = {EapLevel.PROCESS.value, EapLevel.AREA.value}


class ReconciliationApplyBlocked(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(slots=True, frozen=True)
class Expectations:
    total: int | None = None
    safe: int | None = None
    review: int | None = None
    unresolved: int | None = None


@dataclass(slots=True)
class ApplyResult:
    applied: bool
    artifact_sha256: str
    planned_updates: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    skipped_unresolved: list[str] = field(default_factory=list)
    skipped_review: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "planned_updates": len(self.planned_updates),
            "unchanged": len(self.unchanged),
            "skipped_unresolved": len(self.skipped_unresolved),
            "skipped_review": len(self.skipped_review),
            "conflicts": len(self.conflicts),
        }


def load_artifact(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _validate_artifact(artifact: dict[str, Any], catalog: EapCatalog, expect: Expectations) -> list[str]:
    errors: list[str] = []
    records = artifact.get("records", [])
    if artifact.get("catalog", {}).get("sha256") != catalog.sha256:
        errors.append(
            "o JSON de reconciliação foi gerado com outro catálogo EAP; rode `analyze` de novo antes do apply"
        )
    categories: Counter[str] = Counter()
    for record in records:
        try:
            status = MatchStatus(record["status"])
        except (KeyError, ValueError):
            errors.append(f"status inválido em {record.get('externalId')!r}: {record.get('status')!r}")
            continue
        if record.get("category") != category_of(status):
            errors.append(f"categoria incoerente em {record.get('externalId')!r}")
        categories[category_of(status)] += 1
        if status in SAFE_STATUSES and not record.get("matchedEapCode"):
            errors.append(f"match seguro sem código EAP em {record.get('externalId')!r}")
    ids = [record.get("externalId") for record in records]
    if any(not item for item in ids):
        errors.append("registro sem identidade Monday (externalId)")
    duplicated = sorted(key for key, count in Counter(ids).items() if key and count > 1)
    if duplicated:
        errors.append(f"identidades Monday repetidas no JSON: {duplicated}")
    metrics = artifact.get("metrics", {})
    if metrics.get("total_equipment") != len(records):
        errors.append("metrics.total_equipment não confere com os registros")
    if metrics.get("auto_match_safe_total") != categories["MATCH"]:
        errors.append("metrics.auto_match_safe_total não confere com os registros")
    for label, expected, found in (
        ("total", expect.total, len(records)),
        ("seguros", expect.safe, categories["MATCH"]),
        ("review", expect.review, categories["REVIEW"]),
        ("unresolved", expect.unresolved, categories["UNRESOLVED"]),
    ):
        if expected is not None and expected != found:
            errors.append(f"esperado {expected} {label}, JSON tem {found}")
    return errors


async def apply_reconciliation(
    session: AsyncSession,
    *,
    artifact: dict[str, Any],
    artifact_sha256: str,
    catalog: EapCatalog,
    project_context_id: str,
    apply: bool,
    expect: Expectations | None = None,
    actor_id: str | None = None,
) -> ApplyResult:
    result = ApplyResult(applied=apply, artifact_sha256=artifact_sha256)
    errors = _validate_artifact(artifact, catalog, expect or Expectations())
    records = artifact.get("records", [])
    safe = [r for r in records if r.get("status") in {s.value for s in SAFE_STATUSES}]
    for record in records:
        category = record.get("category")
        if category == "REVIEW":
            result.skipped_review.append(record["externalId"])
        elif category == "UNRESOLVED":
            result.skipped_unresolved.append(record["externalId"])

    external_ids = [record["externalId"] for record in safe]
    mappings = (
        (
            await session.execute(
                select(ExternalMapping).where(
                    ExternalMapping.project_context_id == project_context_id,
                    ExternalMapping.source_system == SOURCE_SYSTEM,
                    ExternalMapping.source_entity_type == "equipment",
                    ExternalMapping.external_id.in_(external_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    mapping_by_key: dict[str, list[ExternalMapping]] = {}
    for mapping in mappings:
        mapping_by_key.setdefault(mapping.external_id, []).append(mapping)
    equipment_ids = [mapping.target_entity_id for mapping in mappings]
    equipments = {
        item.id: item
        for item in (
            await session.execute(
                select(Equipment).where(
                    Equipment.id.in_(equipment_ids), Equipment.project_context_id == project_context_id
                )
            )
        )
        .scalars()
        .all()
    }
    codes = sorted({record["matchedEapCode"] for record in safe if record.get("matchedEapCode")})
    nodes = {
        node.code: node
        for node in (await session.execute(select(EapNode).where(EapNode.code.in_(codes)))).scalars().all()
    }

    targets_by_equipment: dict[str, set[str]] = {}
    plan: list[tuple[dict[str, Any], Equipment, EapNode]] = []
    for record in safe:
        key, code = record["externalId"], record.get("matchedEapCode")
        found = mapping_by_key.get(key, [])
        if len(found) != 1:
            errors.append(f"{key}: esperado 1 Equipment pela identidade Monday, encontrados {len(found)}")
            continue
        equipment = equipments.get(found[0].target_entity_id)
        if equipment is None:
            errors.append(f"{key}: Equipment do mapping não existe neste project_context")
            continue
        node = nodes.get(code or "")
        if node is None:
            errors.append(f"{key}: EapNode {code} não existe no banco")
            continue
        if node.level not in _LINKABLE_LEVELS:
            errors.append(f"{key}: EapNode {code} é {node.level}; equipamento só aponta para PROCESS/AREA")
            continue
        if node.code in catalog.review_codes or not node.active:
            errors.append(f"{key}: EapNode {code} está em revisão ou inativo")
            continue
        targets_by_equipment.setdefault(equipment.id, set()).add(node.id)
        plan.append((record, equipment, node))

    for equipment_id, targets in targets_by_equipment.items():
        if len(targets) > 1:
            errors.append(f"Equipment {equipment_id} recebeu alvos EAP conflitantes")

    for record, equipment, node in plan:
        if equipment.eap_node_id == node.id:
            result.unchanged.append(record["externalId"])
        elif equipment.eap_node_id is not None:
            result.conflicts.append(
                {
                    "externalId": record["externalId"],
                    "equipmentId": equipment.id,
                    "currentEapNodeId": equipment.eap_node_id,
                    "targetEapCode": node.code,
                }
            )
        else:
            result.planned_updates.append(
                {
                    "externalId": record["externalId"],
                    "equipmentId": equipment.id,
                    "equipmentName": equipment.name,
                    "eapCode": node.code,
                    "eapNodeId": node.id,
                    "status": record["status"],
                }
            )
    errors += [
        f"{item['externalId']}: já aponta para outro EapNode ({item['currentEapNodeId']}), alvo "
        f"{item['targetEapCode']}; nada é sobrescrito"
        for item in result.conflicts
    ]

    if errors:
        await session.rollback()
        raise ReconciliationApplyBlocked(errors)
    if not apply:
        await session.rollback()
        return result

    planned = {item["equipmentId"]: item for item in result.planned_updates}
    for record, equipment, node in plan:
        item = planned.get(equipment.id)
        if item is None:
            continue
        previous = equipment.eap_node_id
        equipment.eap_node_id = node.id
        await record_audit(
            session,
            user_id=actor_id,
            action=APPLY_ACTION,
            entity="Equipment",
            entity_id=equipment.id,
            previous_data={"eap_node_id": previous},
            new_data={"eap_node_id": node.id, "eapCode": node.code},
            metadata={
                "externalId": record["externalId"],
                "reconciliationStatus": record["status"],
                "artifactSha256": artifact_sha256,
                "projectContextId": project_context_id,
            },
        )
    await session.commit()
    return result
