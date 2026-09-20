"""Entidades normalizadas do domínio do Painel de Equipamentos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.user import User

if TYPE_CHECKING:
    from app.models.process import (
        Contract,
        LegalProcess,
        Negotiation,
        PurchaseOrder,
        PurchaseRequest,
    )
    from app.models.supplier import EquipmentSupplier


class Unit(Base):
    __tablename__ = "unit"

    id: Mapped[str] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    project_contexts: Mapped[list[ProjectContext]] = relationship(back_populates="unit")
    areas: Mapped[list[Area]] = relationship(back_populates="unit")


class ProjectContext(Base):
    __tablename__ = "project_context"

    id: Mapped[str] = uuid_pk()
    unit_id: Mapped[str] = mapped_column(ForeignKey("unit.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    unit: Mapped[Unit] = relationship(back_populates="project_contexts")
    work_packages: Mapped[list[WorkPackage]] = relationship(back_populates="project_context")
    equipments: Mapped[list[Equipment]] = relationship(back_populates="project_context")

    __table_args__ = (
        Index("project_context_unit_code_key", "unit_id", "code", unique=True),
        Index("project_context_unit_id_idx", "unit_id"),
    )


class Area(Base):
    __tablename__ = "area"

    id: Mapped[str] = uuid_pk()
    unit_id: Mapped[str] = mapped_column(ForeignKey("unit.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    unit: Mapped[Unit] = relationship(back_populates="areas")
    equipments: Mapped[list[Equipment]] = relationship(back_populates="area")

    __table_args__ = (Index("area_unit_name_key", "unit_id", "name", unique=True),)


class Discipline(Base):
    __tablename__ = "discipline"

    id: Mapped[str] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    equipments: Mapped[list[Equipment]] = relationship(back_populates="discipline")


class WorkPackage(Base):
    __tablename__ = "work_package"

    id: Mapped[str] = uuid_pk()
    project_context_id: Mapped[str] = mapped_column(
        ForeignKey("project_context.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project_context: Mapped[ProjectContext] = relationship(back_populates="work_packages")
    equipments: Mapped[list[Equipment]] = relationship(back_populates="work_package")
    equipment_links: Mapped[list[EquipmentWorkPackage]] = relationship(back_populates="work_package")

    __table_args__ = (
        Index("work_package_context_code_key", "project_context_id", "code", unique=True),
        Index("work_package_context_id_idx", "project_context_id"),
    )


class EquipmentWorkPackage(Base):
    """Relação N:N: a origem real traz múltiplos Work Packages por equipamento.

    `equipment.work_package_id` permanece como referência "primária" (compat
    com telas/consultas existentes que assumem 0..1); esta tabela é a fonte de
    verdade para 0..N. Nenhum código escolhe arbitrariamente qual é o
    primário — a migração só preenche `work_package_id` quando há exatamente
    um Work Package na origem.
    """

    __tablename__ = "equipment_work_package"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    work_package_id: Mapped[str] = mapped_column(
        ForeignKey("work_package.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    equipment: Mapped[Equipment] = relationship(back_populates="work_package_links")
    work_package: Mapped[WorkPackage] = relationship(back_populates="equipment_links")

    __table_args__ = (
        Index(
            "equipment_work_package_pair_key", "equipment_id", "work_package_id", unique=True
        ),
        Index("equipment_work_package_equipment_id_idx", "equipment_id"),
    )


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[str] = uuid_pk()
    project_context_id: Mapped[str] = mapped_column(
        ForeignKey("project_context.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    origin: Mapped[str | None] = mapped_column(String(160), nullable=True)
    startup_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    discipline_id: Mapped[str | None] = mapped_column(
        ForeignKey("discipline.id", ondelete="SET NULL"), nullable=True
    )
    area_id: Mapped[str | None] = mapped_column(ForeignKey("area.id", ondelete="SET NULL"), nullable=True)
    work_package_id: Mapped[str | None] = mapped_column(
        ForeignKey("work_package.id", ondelete="SET NULL"), nullable=True
    )
    responsible_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    criticality: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_stage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capex_estimated: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    project_context: Mapped[ProjectContext] = relationship(back_populates="equipments")
    discipline: Mapped[Discipline | None] = relationship(back_populates="equipments")
    area: Mapped[Area | None] = relationship(back_populates="equipments")
    work_package: Mapped[WorkPackage | None] = relationship(back_populates="equipments")
    responsible_user: Mapped[User | None] = relationship("User")
    components: Mapped[list[EquipmentComponent]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    transitions: Mapped[list[WorkflowTransition]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    negotiation: Mapped[Negotiation | None] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    legal_process: Mapped[LegalProcess | None] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    contract: Mapped[Contract | None] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    purchase_request: Mapped[PurchaseRequest | None] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    purchase_order: Mapped[PurchaseOrder | None] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    supplier_links: Mapped[list[EquipmentSupplier]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    work_package_links: Mapped[list[EquipmentWorkPackage]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("current_stage BETWEEN 0 AND 8", name="equipment_current_stage_check"),
        CheckConstraint("capex_estimated IS NULL OR capex_estimated >= 0", name="equipment_capex_check"),
        Index("equipment_project_context_id_idx", "project_context_id"),
        Index("equipment_current_stage_idx", "current_stage"),
        Index("equipment_name_idx", "name"),
    )


class EquipmentComponent(Base):
    __tablename__ = "equipment_component"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Startup do componente, observado por subitem na origem Monday. Não é
    # preenchido a partir de `equipment.startup_at`: quando o componente tem
    # valor próprio, ele prevalece nos cálculos de prazo.
    startup_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pre_start_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contract_delivery_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    freight_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    equipment: Mapped[Equipment] = relationship(back_populates="components")

    __table_args__ = (
        CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="component_lead_time_check"),
        CheckConstraint("pre_start_days IS NULL OR pre_start_days >= 0", name="component_pre_start_check"),
        CheckConstraint("freight_days IS NULL OR freight_days >= 0", name="component_freight_check"),
        Index("equipment_component_equipment_id_idx", "equipment_id"),
    )


class WorkflowTransition(Base):
    __tablename__ = "workflow_transition"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    from_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    to_stage: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("User.id", ondelete="SET NULL"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    equipment: Mapped[Equipment] = relationship(back_populates="transitions")
    actor: Mapped[User | None] = relationship("User")

    __table_args__ = (
        CheckConstraint("from_stage BETWEEN 0 AND 8", name="transition_from_stage_check"),
        CheckConstraint("to_stage BETWEEN 0 AND 8", name="transition_to_stage_check"),
        Index("workflow_transition_equipment_date_idx", "equipment_id", "occurred_at"),
    )


STAGES: dict[int, str] = {
    0: "Nova demanda",
    1: "Negociação",
    2: "Equalização",
    3: "Abertura do chamado",
    4: "Aprovação da minuta",
    5: "Escrituração do contrato",
    6: "SC ou OCI",
    7: "Aprovação da OC",
    8: "Concluído",
}
