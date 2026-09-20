"""Fornecedores e o vínculo N:N com equipamentos.

`role` é texto livre: o catálogo oficial de papéis do fornecedor ainda não foi
validado pelo negócio, então nenhum enum fechado é assumido aqui.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.equipment import Equipment


class Supplier(Base):
    __tablename__ = "supplier"

    id: Mapped[str] = uuid_pk()
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment_links: Mapped[list[EquipmentSupplier]] = relationship(back_populates="supplier")

    __table_args__ = (
        # Só impede duplicidade quando o documento foi informado.
        Index("supplier_tax_id_key", "tax_id", unique=True, postgresql_where=tax_id.is_not(None)),
        Index("supplier_legal_name_idx", "legal_name"),
    )


class EquipmentSupplier(Base):
    __tablename__ = "equipment_supplier"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("supplier.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    equipment: Mapped[Equipment] = relationship(back_populates="supplier_links")
    supplier: Mapped[Supplier] = relationship(back_populates="equipment_links")

    __table_args__ = (
        Index("equipment_supplier_pair_key", "equipment_id", "supplier_id", unique=True),
        # No máximo um principal por equipamento, garantido pelo banco.
        Index(
            "equipment_supplier_primary_key",
            "equipment_id",
            unique=True,
            postgresql_where=is_primary.is_(True),
        ),
        Index("equipment_supplier_equipment_id_idx", "equipment_id"),
    )
