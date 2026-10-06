"""Fornecedores, histórico de vínculos e evidências de recomendação.

`role` é texto livre: o catálogo oficial de papéis do fornecedor ainda não foi
validado pelo negócio, então nenhum enum fechado é assumido aqui.

`EquipmentSupplier` é o histórico confirmado. Pode haver vários vínculos ao
longo do tempo, mas o índice parcial garante no máximo um com `ended_at IS
NULL`. `SupplierRecommendationEvidence` é apenas evidência para sugestão e
nunca representa vínculo com equipamento.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
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
    # Legado: vínculos ativos continuam marcados como principais. A fonte de
    # verdade para atividade é `ended_at IS NULL`.
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="MANUAL")
    changed_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="supplier_links")
    supplier: Mapped[Supplier] = relationship(back_populates="equipment_links")

    __table_args__ = (
        CheckConstraint(
            "(ended_at IS NULL AND end_stage IS NULL) OR ended_at IS NOT NULL",
            name="equipment_supplier_end_check",
        ),
        Index(
            "equipment_supplier_active_key",
            "equipment_id",
            unique=True,
            postgresql_where=ended_at.is_(None),
        ),
        Index("equipment_supplier_equipment_id_idx", "equipment_id"),
        Index("equipment_supplier_supplier_id_idx", "supplier_id"),
    )


class SupplierRecommendationEvidence(Base):
    """Evidência corporativa para sugestão; nunca cria vínculo automaticamente."""

    __tablename__ = "supplier_recommendation_evidence"

    id: Mapped[str] = uuid_pk()
    equipment_key: Mapped[str] = mapped_column(String(240), nullable=False)
    equipment_label: Mapped[str] = mapped_column(String(240), nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(String(240), nullable=True)
    corporate_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    occurrences: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_occurrences: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_key: Mapped[str] = mapped_column(String(300), nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    details: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index("supplier_evidence_source_key", "source", "source_key", unique=True),
        Index("supplier_evidence_equipment_key_idx", "equipment_key"),
        Index("supplier_evidence_corporate_code_idx", "corporate_code"),
    )
