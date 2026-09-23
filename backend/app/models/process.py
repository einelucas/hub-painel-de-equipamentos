"""Entidades do processo de aquisição.

Etapa 7A: Negotiation e LegalProcess continuam 1:1 com o equipamento (nenhuma
decisão de negócio pediu mudar isso). Contract, PurchaseRequest e
PurchaseOrder passam a 1:N — um equipamento pode ter vários contratos,
várias SC/OCI e várias OCs (`Equipment.contracts` etc.). O fornecedor NÃO
pertence ao contrato individual: é único por equipamento
(`app.models.supplier.EquipmentSupplier`, no máximo 1 vínculo ativo).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.equipment import Equipment
from app.models.user import User

PURCHASE_REQUEST_KINDS = ("SC", "OCI")


def _equipment_fk_unique() -> Mapped[str]:
    """Para as entidades que continuam 1:1 (Negotiation/LegalProcess)."""
    return mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, unique=True
    )


def _equipment_fk_many() -> Mapped[str]:
    """Para as entidades 1:N (Contract/PurchaseRequest/PurchaseOrder)."""
    return mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)


class Negotiation(Base):
    __tablename__ = "negotiation"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk_unique()
    equalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    negotiated_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="negotiation")


class LegalProcess(Base):
    __tablename__ = "legal_process"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk_unique()
    opened_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    ticket_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    draft_prepared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    draft_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="legal_process")


class Contract(Base):
    """1:N com o equipamento (Etapa 7A). A janela de entrega contratual
    (`Equipment.contractual_delivery_start/end`) pertence ao equipamento, não
    a um contrato individual — um fornecedor pode entregar em partes ao
    longo de vários contratos. O arquivo é 1:1 com o contrato (colunas de
    metadado aqui; bytes no storage configurado, ver `app.core.storage`)."""

    __tablename__ = "contract"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk_many()
    contract_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    executed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_uploaded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    file_uploaded_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="contracts")
    file_uploaded_by: Mapped[User | None] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "file_size_bytes IS NULL OR file_size_bytes >= 0", name="contract_file_size_check"
        ),
    )


class PurchaseRequest(Base):
    """1:N com o equipamento (Etapa 7A) — pode haver mais de uma SC/OCI."""

    __tablename__ = "purchase_request"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk_many()
    kind: Mapped[str | None] = mapped_column(String(8), nullable=True)
    request_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    requested_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="purchase_requests")

    __table_args__ = (
        CheckConstraint("kind IS NULL OR kind IN ('SC', 'OCI')", name="purchase_request_kind_check"),
    )


class PurchaseOrder(Base):
    """1:N com o equipamento (Etapa 7A) — pode haver mais de uma OC."""

    __tablename__ = "purchase_order"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk_many()
    order_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ordered_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="purchase_orders")

    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="purchase_order_amount_check"),
    )
