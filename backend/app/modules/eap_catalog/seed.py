"""Carga idempotente do catálogo EAP canônico em `eap_node`.

Regras:
- insere só códigos inexistentes, pais antes de filhos;
- código já existente com mesmo nível, nome e pai → `unchanged`;
- código já existente com qualquer divergência → `conflicts` (nunca sobrescreve);
- itens `review_required` nunca são inseridos (`skipped_review_required`);
- nada é excluído: nós do banco fora do catálogo são só reportados;
- não toca em `project_eap`, `equipment` nem `project_context`.

Cada nó criado gera um AuditLog `eap_catalog.create` com o SHA-256 do catálogo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.eap import ALLOWED_PARENT_LEVELS, EapLevel
from app.models.equipment import EapNode
from app.modules.eap_catalog.catalog import EapCatalog, EapCatalogError, validate_catalog
from app.shared.audit import record_audit


@dataclass(slots=True)
class SeedResult:
    applied: bool
    created: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    skipped_review_required: list[dict[str, Any]] = field(default_factory=list)
    extra_in_database: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "created": len(self.created),
            "unchanged": len(self.unchanged),
            "conflicts": len(self.conflicts),
            "skipped_review_required": len(self.skipped_review_required),
            "extra_in_database": len(self.extra_in_database),
        }


async def seed_eap_catalog(
    session: AsyncSession, catalog: EapCatalog, *, apply: bool, actor_id: str | None = None
) -> SeedResult:
    errors = validate_catalog(catalog)
    if errors:
        raise EapCatalogError("catálogo inválido: " + "; ".join(errors))

    result = SeedResult(applied=apply)
    existing = {node.code: node for node in (await session.execute(select(EapNode))).scalars().all()}
    code_by_id = {node.id: node.code for node in existing.values()}
    # código -> (id, nível) dos nós que existem ou existirão após a carga
    available: dict[str, tuple[str | None, str]] = {
        code: (node.id, node.level) for code, node in existing.items()
    }

    for item in catalog.ordered_nodes():
        current = existing.get(item.code)
        if current is not None:
            current_parent = code_by_id.get(current.parent_id) if current.parent_id else None
            differences = {
                field_name: {"database": found, "catalog": expected}
                for field_name, found, expected in (
                    ("level", current.level, item.level.value),
                    ("name", current.name, item.name),
                    ("parent_code", current_parent, item.parent_code),
                )
                if found != expected
            }
            if differences:
                result.conflicts.append({"code": item.code, "differences": differences})
            else:
                result.unchanged.append(item.code)
            continue

        parent_id: str | None = None
        if item.parent_code is not None:
            parent = available.get(item.parent_code)
            if parent is None or EapLevel(parent[1]) not in ALLOWED_PARENT_LEVELS[item.level]:
                result.conflicts.append(
                    {
                        "code": item.code,
                        "differences": {
                            "parent": {
                                "database": None if parent is None else parent[1],
                                "catalog": item.parent_code,
                            }
                        },
                    }
                )
                continue
            parent_id = parent[0]

        result.created.append(item.code)
        if not apply:
            available[item.code] = (None, item.level.value)
            continue
        node = EapNode(code=item.code, name=item.name, level=item.level.value, parent_id=parent_id)
        session.add(node)
        await session.flush()
        available[item.code] = (node.id, node.level)
        await record_audit(
            session,
            user_id=actor_id,
            action="eap_catalog.create",
            entity="EapNode",
            entity_id=node.id,
            new_data={
                "code": item.code,
                "name": item.name,
                "level": item.level.value,
                "parentCode": item.parent_code,
            },
            metadata={"catalogSha256": catalog.sha256, "sourceRows": list(item.source_rows)},
        )

    for review in catalog.review_required:
        code = review.get("code")
        result.skipped_review_required.append(
            {"code": code, "reason": review.get("reason"), "existsInDatabase": code in existing}
        )

    catalog_codes = {node.code for node in catalog.nodes} | catalog.review_codes
    result.extra_in_database = sorted(code for code in existing if code not in catalog_codes)

    if apply:
        await session.commit()
    else:
        await session.rollback()
    return result
