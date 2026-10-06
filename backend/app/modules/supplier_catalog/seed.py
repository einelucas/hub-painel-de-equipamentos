"""Reconciliação e carga idempotente do catálogo global de fornecedores.

O módulo só escreve em Supplier, SupplierAlias e AuditLog. Não importa nem
referencia os modelos de equipamento, obra, Monday ou workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier, SupplierAlias
from app.modules.supplier_catalog.catalog import (
    CatalogSupplier,
    SupplierCatalog,
    SupplierCatalogError,
    validate_catalog,
)
from app.shared.audit import record_audit

ALIAS_SOURCE = "SUPPLIER_CATALOG"
ALIAS_CONTEXT = "GLOBAL"
_OFFICIAL_FIELDS = ("legal_name", "trade_name", "tax_id", "active")


class SupplierCatalogBlockedError(RuntimeError):
    def __init__(self, message: str, result: SeedResult) -> None:
        super().__init__(message)
        self.result = result


@dataclass(slots=True)
class SupplierAction:
    corporate_code: str
    action: str  # CREATE | UNCHANGED | UPDATE | CONFLICT
    supplier_id: str | None = None
    differences: dict[str, dict[str, Any]] = field(default_factory=dict)
    detail: str | None = None


@dataclass(slots=True)
class AliasAction:
    corporate_code: str
    alias: str
    action: str  # CREATE | UNCHANGED | CONFLICT
    detail: str | None = None


@dataclass(slots=True)
class SeedResult:
    applied: bool = False
    suppliers: list[SupplierAction] = field(default_factory=list)
    aliases: list[AliasAction] = field(default_factory=list)
    extra_in_database: list[str] = field(default_factory=list)

    @property
    def conflicts(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": "supplier",
                "corporateCode": item.corporate_code,
                "detail": item.detail,
                "differences": item.differences,
            }
            for item in self.suppliers
            if item.action == "CONFLICT"
        ] + [
            {
                "kind": "alias",
                "corporateCode": item.corporate_code,
                "alias": item.alias,
                "detail": item.detail,
            }
            for item in self.aliases
            if item.action == "CONFLICT"
        ]

    def summary(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "create": sum(item.action == "CREATE" for item in self.suppliers),
            "unchanged": sum(item.action == "UNCHANGED" for item in self.suppliers),
            "update": sum(item.action == "UPDATE" for item in self.suppliers),
            "conflict": len(self.conflicts),
            "extra_in_database": len(self.extra_in_database),
            "aliases_create": sum(item.action == "CREATE" for item in self.aliases),
            "aliases_unchanged": sum(item.action == "UNCHANGED" for item in self.aliases),
        }


def _differences(current: Supplier, item: CatalogSupplier) -> dict[str, dict[str, Any]]:
    return {
        field_name: {"database": getattr(current, field_name), "catalog": getattr(item, field_name)}
        for field_name in _OFFICIAL_FIELDS
        if getattr(current, field_name) != getattr(item, field_name)
    }


async def reconcile_supplier_catalog(
    session: AsyncSession, catalog: SupplierCatalog, *, sync: bool = False
) -> SeedResult:
    errors = validate_catalog(catalog)
    if errors:
        raise SupplierCatalogError("catálogo inválido: " + "; ".join(errors))

    all_suppliers = (await session.scalars(select(Supplier))).all()
    by_code = {item.corporate_code: item for item in all_suppliers if item.corporate_code is not None}
    by_tax_id = {item.tax_id: item for item in all_suppliers if item.tax_id is not None}
    result = SeedResult()

    for item in catalog.ordered_suppliers():
        current = by_code.get(item.corporate_code)
        tax_holder = by_tax_id.get(item.tax_id) if item.tax_id is not None else None
        if tax_holder is not None and tax_holder is not current:
            result.suppliers.append(
                SupplierAction(
                    item.corporate_code,
                    "CONFLICT",
                    None if current is None else current.id,
                    detail=(
                        f"tax_id {item.tax_id} pertence ao Supplier {tax_holder.id} "
                        f"(corporate_code={tax_holder.corporate_code!r})"
                    ),
                )
            )
            continue
        if current is None:
            result.suppliers.append(SupplierAction(item.corporate_code, "CREATE"))
            continue
        differences = _differences(current, item)
        if not differences:
            result.suppliers.append(SupplierAction(item.corporate_code, "UNCHANGED", current.id))
        elif sync:
            result.suppliers.append(
                SupplierAction(item.corporate_code, "UPDATE", current.id, differences=differences)
            )
        else:
            result.suppliers.append(
                SupplierAction(
                    item.corporate_code,
                    "CONFLICT",
                    current.id,
                    differences=differences,
                    detail="campos oficiais divergem; use --sync após revisar",
                )
            )

    ids_by_code = {
        action.corporate_code: action.supplier_id
        for action in result.suppliers
        if action.supplier_id is not None
    }
    requested_aliases = [alias for item in catalog.suppliers for alias in item.aliases]
    stored_aliases = {
        item.alias: item
        for item in (
            await session.scalars(
                select(SupplierAlias).where(
                    SupplierAlias.source == ALIAS_SOURCE,
                    SupplierAlias.context == ALIAS_CONTEXT,
                    SupplierAlias.alias.in_(requested_aliases or [""]),
                )
            )
        ).all()
    }
    for item in catalog.ordered_suppliers():
        for alias in item.aliases:
            stored = stored_aliases.get(alias)
            if stored is None:
                result.aliases.append(AliasAction(item.corporate_code, alias, "CREATE"))
            elif ids_by_code.get(item.corporate_code) == stored.supplier_id:
                result.aliases.append(AliasAction(item.corporate_code, alias, "UNCHANGED"))
            else:
                result.aliases.append(
                    AliasAction(
                        item.corporate_code,
                        alias,
                        "CONFLICT",
                        f"alias já aponta para o Supplier {stored.supplier_id}",
                    )
                )

    catalog_codes = {item.corporate_code for item in catalog.suppliers}
    result.extra_in_database = sorted(
        item.corporate_code or f"id:{item.id}"
        for item in all_suppliers
        if item.corporate_code not in catalog_codes
    )
    return result


async def seed_supplier_catalog(
    session: AsyncSession,
    catalog: SupplierCatalog,
    *,
    apply: bool,
    sync: bool = False,
    actor_id: str | None = None,
) -> SeedResult:
    result = await reconcile_supplier_catalog(session, catalog, sync=sync)
    if not apply:
        await session.rollback()
        return result
    if result.conflicts:
        await session.rollback()
        raise SupplierCatalogBlockedError(
            f"apply bloqueado por {len(result.conflicts)} conflito(s)", result
        )

    by_catalog_code = {item.corporate_code: item for item in catalog.suppliers}
    supplier_ids: dict[str, str] = {}
    for action in result.suppliers:
        item = by_catalog_code[action.corporate_code]
        metadata = {
            "catalogSha256": catalog.sha256,
            "corporateCode": item.corporate_code,
            "sourceFile": catalog.source.get("file"),
            "sourceRow": item.source_row,
        }
        if action.action == "CREATE":
            values = {"corporate_code": item.corporate_code} | {
                field_name: getattr(item, field_name) for field_name in _OFFICIAL_FIELDS
            }
            stored = Supplier(**values)
            session.add(stored)
            await session.flush()
            action.supplier_id = stored.id
            await record_audit(
                session,
                user_id=actor_id,
                action="supplier_catalog.create",
                entity="Supplier",
                entity_id=stored.id,
                new_data=values,
                metadata=metadata,
            )
        else:
            assert action.supplier_id is not None
            loaded = await session.get(Supplier, action.supplier_id)
            assert loaded is not None
            stored = loaded
            if action.action == "UPDATE":
                previous = {name: values["database"] for name, values in action.differences.items()}
                updated = {name: values["catalog"] for name, values in action.differences.items()}
                for name, value in updated.items():
                    setattr(stored, name, value)
                await record_audit(
                    session,
                    user_id=actor_id,
                    action="supplier_catalog.update",
                    entity="Supplier",
                    entity_id=stored.id,
                    previous_data=previous,
                    new_data=updated,
                    metadata=metadata,
                )
        supplier_ids[item.corporate_code] = stored.id

    for alias_action in result.aliases:
        if alias_action.action != "CREATE":
            continue
        alias = SupplierAlias(
            supplier_id=supplier_ids[alias_action.corporate_code],
            alias=alias_action.alias,
            source=ALIAS_SOURCE,
            context=ALIAS_CONTEXT,
        )
        session.add(alias)
        await session.flush()
        item = by_catalog_code[alias_action.corporate_code]
        await record_audit(
            session,
            user_id=actor_id,
            action="supplier_catalog.alias_create",
            entity="SupplierAlias",
            entity_id=alias.id,
            new_data={
                "supplierId": alias.supplier_id,
                "alias": alias.alias,
                "source": ALIAS_SOURCE,
                "context": ALIAS_CONTEXT,
            },
            metadata={
                "catalogSha256": catalog.sha256,
                "corporateCode": item.corporate_code,
                "sourceFile": catalog.source.get("file"),
                "sourceRow": item.source_row,
            },
        )
    await session.commit()
    result.applied = True
    return result
