"""Fornecedores e o vínculo com equipamentos.

`role` é texto livre: o catálogo oficial de papéis do fornecedor ainda não foi
validado pelo negócio, então nenhum enum fechado é assumido aqui.

Etapa 7A: a tabela de vínculo (`EquipmentSupplier`) continua N:N na
estrutura — evita migração destrutiva desnecessária — mas a regra de
negócio nova é "um equipamento tem no máximo um fornecedor". Isso é
garantido no banco por um índice único em `equipment_id` sozinho (não mais
só no par `equipment_id, supplier_id`): um segundo vínculo é sempre
rejeitado; substituir o fornecedor é sempre uma operação explícita
(remover o vínculo atual, criar o novo), nunca um segundo INSERT.
`is_primary` fica sem função nova (sempre verdadeiro, já que só existe uma
linha) — mantido para não descartar dado/índice existente sem necessidade.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.equipment import Equipment


class Supplier(Base):
    __tablename__ = "supplier"

    id: Mapped[str] = uuid_pk()
    # "Cód. Fornecedor. CS" da base corporativa: chave de reconciliação das
    # cargas. Opcional porque fornecedores cadastrados à mão podem não ter.
    corporate_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment_links: Mapped[list[EquipmentSupplier]] = relationship(back_populates="supplier")
    aliases: Mapped[list[SupplierAlias]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Só impede duplicidade quando o documento foi informado.
        Index("supplier_tax_id_key", "tax_id", unique=True, postgresql_where=tax_id.is_not(None)),
        Index(
            "supplier_corporate_code_key",
            "corporate_code",
            unique=True,
            postgresql_where=corporate_code.is_not(None),
        ),
        Index("supplier_legal_name_idx", "legal_name"),
    )


class SupplierAlias(Base):
    """Nome histórico de origem (ex.: Monday) que aponta para um fornecedor
    oficial, sem virar um fornecedor novo. `legal_name` nunca é sobrescrito
    pelo alias. `context` identifica o board/contexto de origem (ex.: LEM_F2)."""

    __tablename__ = "supplier_alias"

    id: Mapped[str] = uuid_pk()
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("supplier.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    context: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    supplier: Mapped[Supplier] = relationship(back_populates="aliases")

    __table_args__ = (
        CheckConstraint("length(trim(alias)) > 0", name="supplier_alias_alias_check"),
        # O mesmo nome, na mesma origem/contexto, aponta para um único fornecedor.
        Index("supplier_alias_source_key", "source", "context", "alias", unique=True),
        Index("supplier_alias_supplier_idx", "supplier_id"),
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
        # Etapa 7A: no máximo UM vínculo por equipamento, ponto — garantido
        # pelo banco. Substitui a regra antiga (múltiplos fornecedores,
        # só um `is_primary`).
        Index("equipment_supplier_single_key", "equipment_id", unique=True),
        Index("equipment_supplier_pair_key", "equipment_id", "supplier_id", unique=True),
        Index("equipment_supplier_equipment_id_idx", "equipment_id"),
    )
