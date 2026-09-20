"""Entidades do processo de aquisição associadas 1:1 ao equipamento.

A cardinalidade 1:1 acompanha a decisão registrada na Etapa 1. Múltiplos
contratos/SCs/OCs por equipamento continuam pendentes de validação funcional.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.equipment import Equipment

PURCHASE_REQUEST_KINDS = ("SC", "OCI")


def _equipment_fk() -> Mapped[str]:
    return mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False, unique=True
    )


class Negotiation(Base):
    __tablename__ = "negotiation"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk()
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
    equipment_id: Mapped[str] = _equipment_fk()
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
    __tablename__ = "contract"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk()
    contract_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    executed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="contract")


class PurchaseRequest(Base):
    __tablename__ = "purchase_request"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk()
    kind: Mapped[str | None] = mapped_column(String(8), nullable=True)
    request_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    requested_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="purchase_request")

    __table_args__ = (
        CheckConstraint("kind IS NULL OR kind IN ('SC', 'OCI')", name="purchase_request_kind_check"),
    )


class PurchaseOrder(Base):
    __tablename__ = "purchase_order"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = _equipment_fk()
    order_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ordered_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="purchase_order")

    __table_args__ = (
        CheckConstraint("amount IS NULL OR amount >= 0", name="purchase_order_amount_check"),
    )
