"""Catálogo mestre global, sem TAG nem vínculo a obras de origem."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class MasterArea(Base):
    __tablename__ = "master_area"
    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    is_unassigned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)
    links: Mapped[list[MasterEquipmentArea]] = relationship(
        back_populates="area", cascade="all, delete-orphan"
    )


class MasterEquipment(Base):
    __tablename__ = "master_equipment"
    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    review_flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)
    links: Mapped[list[MasterEquipmentArea]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    components: Mapped[list[MasterComponentOption]] = relationship(back_populates="equipment", cascade="all, delete-orphan")


class MasterEquipmentArea(Base):
    __tablename__ = "master_equipment_area"
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("master_equipment.id", ondelete="CASCADE"), primary_key=True
    )
    area_id: Mapped[str] = mapped_column(ForeignKey("master_area.id", ondelete="CASCADE"), primary_key=True)
    equipment: Mapped[MasterEquipment] = relationship(back_populates="links")
    area: Mapped[MasterArea] = relationship(back_populates="links")


class MasterComponentOption(Base):
    __tablename__ = "master_component_option"
    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("master_equipment.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(520), nullable=False)
    requires_quantity_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_name_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    equipment: Mapped[MasterEquipment] = relationship(back_populates="components")
    __table_args__ = (
        Index("master_component_equipment_name_key", "equipment_id", "normalized_name", unique=True),
    )


class MasterProjectCreation(Base):
    """Idempotência da criação de obra; não é vínculo do catálogo ao projeto."""
    __tablename__ = "master_project_creation"
    request_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_context_id: Mapped[str] = mapped_column(
        ForeignKey("project_context.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
