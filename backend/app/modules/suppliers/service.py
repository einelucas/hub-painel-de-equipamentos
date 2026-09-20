"""Fornecedores e o vínculo N:N com equipamentos.

O fornecedor mestre nunca é apagado fisicamente: é desativado. O DELETE do
vínculo remove apenas a associação com o equipamento.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.auth import CurrentUser
from app.core.errors import ConflictError, DomainError, NotFoundError
from app.core.scope import assert_equipment_allowed
from app.models.supplier import EquipmentSupplier, Supplier
from app.modules.suppliers.schemas import (
    EquipmentSupplierOut,
    SupplierOut,
)
from app.shared.audit import record_audit


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


async def list_suppliers(
    session: AsyncSession, *, search: str | None, include_inactive: bool
) -> list[Supplier]:
    stmt = select(Supplier)
    if not include_inactive:
        stmt = stmt.where(Supplier.active.is_(True))
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(Supplier.legal_name.ilike(term) | Supplier.trade_name.ilike(term))
    stmt = stmt.order_by(Supplier.legal_name.asc())
    return list((await session.execute(stmt)).scalars().all())


async def get_supplier(session: AsyncSession, supplier_id: str) -> Supplier:
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None:
        raise NotFoundError("Fornecedor não encontrado")
    return supplier


async def _assert_tax_id_free(
    session: AsyncSession, tax_id: str | None, *, ignore_id: str | None = None
) -> None:
    if not tax_id:
        return
    stmt = select(Supplier.id).where(Supplier.tax_id == tax_id)
    if ignore_id:
        stmt = stmt.where(Supplier.id != ignore_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise ConflictError("Já existe um fornecedor com este documento")


async def create_supplier(
    session: AsyncSession, *, values: dict[str, Any], actor: CurrentUser
) -> Supplier:
    values = {key: _clean(value) if isinstance(value, str) else value for key, value in values.items()}
    await _assert_tax_id_free(session, values.get("tax_id"))
    supplier = Supplier(**values)
    session.add(supplier)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="supplier.create",
        entity="Supplier",
        entity_id=supplier.id,
        new_data=values,
    )
    await session.commit()
    await session.refresh(supplier)
    return supplier


async def update_supplier(
    session: AsyncSession, *, supplier_id: str, changes: dict[str, Any], actor: CurrentUser
) -> Supplier:
    supplier = await get_supplier(session, supplier_id)
    changes = {
        key: _clean(value) if isinstance(value, str) else value for key, value in changes.items()
    }
    if "tax_id" in changes:
        await _assert_tax_id_free(session, changes["tax_id"], ignore_id=supplier_id)
    previous: dict[str, Any] = {}
    changed: dict[str, Any] = {}
    for field, value in changes.items():
        if getattr(supplier, field) != value:
            previous[field] = getattr(supplier, field)
            changed[field] = value
            setattr(supplier, field, value)
    if changed:
        await record_audit(
            session,
            user_id=actor.id,
            action="supplier.update",
            entity="Supplier",
            entity_id=supplier.id,
            previous_data=previous,
            new_data=changed,
        )
    await session.commit()
    await session.refresh(supplier)
    return supplier


def _link_out(link: EquipmentSupplier) -> EquipmentSupplierOut:
    return EquipmentSupplierOut(
        supplier=SupplierOut.model_validate(link.supplier),
        role=link.role,
        is_primary=link.is_primary,
        created_at=link.created_at,
    )


async def list_equipment_suppliers(
    session: AsyncSession, equipment_id: str, actor: CurrentUser
) -> list[EquipmentSupplierOut]:
    await assert_equipment_allowed(session, actor, equipment_id)
    links = (
        (
            await session.execute(
                select(EquipmentSupplier)
                .where(EquipmentSupplier.equipment_id == equipment_id)
                .options(joinedload(EquipmentSupplier.supplier))
                .order_by(EquipmentSupplier.is_primary.desc(), EquipmentSupplier.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return [_link_out(link) for link in links]


async def _clear_primary(session: AsyncSession, equipment_id: str, keep_id: str | None) -> None:
    """Garante um único principal, liberando o índice parcial antes do novo."""
    stmt = select(EquipmentSupplier).where(
        EquipmentSupplier.equipment_id == equipment_id,
        EquipmentSupplier.is_primary.is_(True),
    )
    for link in (await session.execute(stmt)).scalars().all():
        if keep_id is None or link.id != keep_id:
            link.is_primary = False
    await session.flush()


async def link_supplier(
    session: AsyncSession,
    *,
    equipment_id: str,
    supplier_id: str,
    role: str | None,
    is_primary: bool,
    actor: CurrentUser,
) -> EquipmentSupplierOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    supplier = await get_supplier(session, supplier_id)
    if not supplier.active:
        raise DomainError("Fornecedor inativo não pode ser vinculado")
    existing = (
        await session.execute(
            select(EquipmentSupplier).where(
                EquipmentSupplier.equipment_id == equipment_id,
                EquipmentSupplier.supplier_id == supplier_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Este fornecedor já está vinculado ao equipamento")

    if is_primary:
        await _clear_primary(session, equipment_id, keep_id=None)
    link = EquipmentSupplier(
        equipment_id=equipment_id,
        supplier_id=supplier_id,
        role=_clean(role),
        is_primary=is_primary,
    )
    session.add(link)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="equipment_supplier.link",
        entity="EquipmentSupplier",
        entity_id=link.id,
        new_data={"supplier_id": supplier_id, "role": link.role, "is_primary": is_primary},
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()
    await session.refresh(link, ["supplier"])
    return _link_out(link)


async def _link_or_404(
    session: AsyncSession, equipment_id: str, supplier_id: str
) -> EquipmentSupplier:
    link = (
        await session.execute(
            select(EquipmentSupplier)
            .where(
                EquipmentSupplier.equipment_id == equipment_id,
                EquipmentSupplier.supplier_id == supplier_id,
            )
            .options(joinedload(EquipmentSupplier.supplier))
        )
    ).scalar_one_or_none()
    if link is None:
        raise NotFoundError("Vínculo de fornecedor não encontrado")
    return link


async def update_link(
    session: AsyncSession,
    *,
    equipment_id: str,
    supplier_id: str,
    changes: dict[str, Any],
    actor: CurrentUser,
) -> EquipmentSupplierOut:
    await assert_equipment_allowed(session, actor, equipment_id)
    link = await _link_or_404(session, equipment_id, supplier_id)
    previous = {"role": link.role, "is_primary": link.is_primary}
    if changes.get("is_primary"):
        await _clear_primary(session, equipment_id, keep_id=link.id)
    if "role" in changes:
        link.role = _clean(changes["role"])
    if "is_primary" in changes and changes["is_primary"] is not None:
        link.is_primary = bool(changes["is_primary"])
    await session.flush()
    new_data = {"role": link.role, "is_primary": link.is_primary}
    if previous != new_data:
        await record_audit(
            session,
            user_id=actor.id,
            action="equipment_supplier.update",
            entity="EquipmentSupplier",
            entity_id=link.id,
            previous_data=previous,
            new_data=new_data,
            metadata={"equipmentId": equipment_id},
        )
    await session.commit()
    await session.refresh(link, ["supplier"])
    return _link_out(link)


async def unlink_supplier(
    session: AsyncSession, *, equipment_id: str, supplier_id: str, actor: CurrentUser
) -> None:
    """Remove só o vínculo — o fornecedor mestre permanece cadastrado."""
    await assert_equipment_allowed(session, actor, equipment_id)
    link = await _link_or_404(session, equipment_id, supplier_id)
    link_id = link.id
    await session.delete(link)
    await session.flush()
    await record_audit(
        session,
        user_id=actor.id,
        action="equipment_supplier.unlink",
        entity="EquipmentSupplier",
        entity_id=link_id,
        previous_data={"supplier_id": supplier_id},
        metadata={"equipmentId": equipment_id},
    )
    await session.commit()


async def primary_suppliers(
    session: AsyncSession, equipment_ids: list[str]
) -> dict[str, Supplier]:
    """Fornecedor principal por equipamento, em lote (usado pelas filas)."""
    if not equipment_ids:
        return {}
    links = (
        (
            await session.execute(
                select(EquipmentSupplier)
                .where(
                    EquipmentSupplier.equipment_id.in_(equipment_ids),
                    EquipmentSupplier.is_primary.is_(True),
                )
                .options(joinedload(EquipmentSupplier.supplier))
            )
        )
        .scalars()
        .all()
    )
    return {link.equipment_id: link.supplier for link in links}
