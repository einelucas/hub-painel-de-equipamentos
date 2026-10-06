from __future__ import annotations

from argparse import Namespace

import pytest
from sqlalchemy import func, select

from app.models.audit import AuditLog
from app.models.supplier import EquipmentSupplier, Supplier, SupplierAlias
from app.modules.supplier_catalog.catalog import CatalogSupplier, SupplierCatalog
from app.modules.supplier_catalog.cli import _seed
from app.modules.supplier_catalog.seed import (
    ALIAS_CONTEXT,
    ALIAS_SOURCE,
    SupplierCatalogBlockedError,
    seed_supplier_catalog,
)


def _catalog(*items: CatalogSupplier) -> SupplierCatalog:
    return SupplierCatalog(
        items,
        source={"file": "fornecedores_oficiais.xlsx"},
        sha256="catalog-sha-sintetico",
    )


def _item(
    code: str,
    *,
    name: str = "FORNECEDOR SINTÉTICO",
    trade_name: str | None = None,
    tax_id: str | None = None,
    active: bool = True,
    aliases: tuple[str, ...] = (),
) -> CatalogSupplier:
    return CatalogSupplier(code, name, trade_name, tax_id, active, aliases, 2)


async def _count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_dry_run_does_not_write_and_apply_is_idempotent(db_session) -> None:
    catalog = _catalog(
        _item("100", tax_id="11111111000111", aliases=("ALIAS A",)),
        _item("200", name="FORNECEDOR INATIVO", active=False),
    )

    dry = await seed_supplier_catalog(db_session, catalog, apply=False)
    assert dry.summary()["create"] == 2
    assert await _count(db_session, Supplier) == 0
    assert await _count(db_session, SupplierAlias) == 0
    assert await _count(db_session, AuditLog) == 0

    first = await seed_supplier_catalog(db_session, catalog, apply=True)
    assert first.summary() == {
        "applied": True,
        "create": 2,
        "unchanged": 0,
        "update": 0,
        "conflict": 0,
        "extra_in_database": 0,
        "aliases_create": 1,
        "aliases_unchanged": 0,
    }
    inactive = await db_session.scalar(select(Supplier).where(Supplier.corporate_code == "200"))
    assert inactive is not None and inactive.active is False
    alias = (await db_session.scalars(select(SupplierAlias))).one()
    assert (alias.alias, alias.source, alias.context) == ("ALIAS A", ALIAS_SOURCE, ALIAS_CONTEXT)
    assert await _count(db_session, EquipmentSupplier) == 0
    assert await _count(db_session, AuditLog) == 3

    second = await seed_supplier_catalog(db_session, catalog, apply=True)
    assert (second.summary()["create"], second.summary()["unchanged"]) == (0, 2)
    assert second.summary()["aliases_unchanged"] == 1
    assert await _count(db_session, Supplier) == 2
    assert await _count(db_session, AuditLog) == 3


async def test_default_conflict_blocks_entire_apply_and_sync_updates_only_official_fields(
    db_session,
) -> None:
    stored = Supplier(
        corporate_code="100",
        legal_name="NOME ANTIGO",
        trade_name="ANTIGO",
        tax_id="11111111000111",
        active=False,
    )
    db_session.add(stored)
    await db_session.commit()
    catalog = _catalog(
        _item(
            "100",
            name="NOME OFICIAL",
            trade_name="OFICIAL",
            tax_id="22222222000122",
            active=True,
        )
    )

    dry = await seed_supplier_catalog(db_session, catalog, apply=False)
    assert dry.suppliers[0].action == "CONFLICT"
    with pytest.raises(SupplierCatalogBlockedError):
        await seed_supplier_catalog(db_session, catalog, apply=True)
    await db_session.refresh(stored)
    assert (stored.corporate_code, stored.legal_name, stored.tax_id, stored.active) == (
        "100",
        "NOME ANTIGO",
        "11111111000111",
        False,
    )

    synced = await seed_supplier_catalog(db_session, catalog, apply=True, sync=True)
    assert synced.suppliers[0].action == "UPDATE"
    await db_session.refresh(stored)
    assert (stored.corporate_code, stored.legal_name, stored.trade_name, stored.tax_id, stored.active) == (
        "100",
        "NOME OFICIAL",
        "OFICIAL",
        "22222222000122",
        True,
    )
    audit = await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "supplier_catalog.update")
    )
    assert audit is not None
    assert audit.previousData["legal_name"] == "NOME ANTIGO"
    assert audit.newData["legal_name"] == "NOME OFICIAL"
    assert audit.metadata_["corporateCode"] == "100"


async def test_tax_id_and_alias_conflicts_block_apply(db_session) -> None:
    first = Supplier(corporate_code="900", legal_name="OUTRO", tax_id="11111111000111")
    second = Supplier(corporate_code="901", legal_name="DONO DO ALIAS")
    db_session.add_all([first, second])
    await db_session.flush()
    db_session.add(
        SupplierAlias(
            supplier_id=second.id,
            alias="ALIAS EM CONFLITO",
            source=ALIAS_SOURCE,
            context=ALIAS_CONTEXT,
        )
    )
    await db_session.commit()
    catalog = _catalog(
        _item("100", tax_id="11111111000111"),
        _item("200", aliases=("ALIAS EM CONFLITO",)),
    )

    dry = await seed_supplier_catalog(db_session, catalog, apply=False)
    assert {item["kind"] for item in dry.conflicts} == {"supplier", "alias"}
    with pytest.raises(SupplierCatalogBlockedError):
        await seed_supplier_catalog(db_session, catalog, apply=True)
    assert await _count(db_session, Supplier) == 2


async def test_extra_supplier_is_reported_and_never_deleted(db_session) -> None:
    extra = Supplier(corporate_code="999", legal_name="FORA DO CATÁLOGO")
    db_session.add(extra)
    await db_session.commit()

    result = await seed_supplier_catalog(db_session, _catalog(_item("100")), apply=True)

    assert result.extra_in_database == ["999"]
    assert await db_session.get(Supplier, extra.id) is not None


async def test_wrong_database_name_aborts_before_seed(db_session) -> None:
    args = Namespace(
        catalog=None,
        apply=True,
        sync=False,
        actor_id=None,
        expect_database="banco_que_nao_existe",
    )
    from app.modules.supplier_catalog.catalog import CATALOG_PATH

    args.catalog = CATALOG_PATH
    with pytest.raises(SystemExit, match="difere de --expect-database"):
        await _seed(args)
    assert await _count(db_session, Supplier) == 0
