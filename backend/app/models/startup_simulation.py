"""Cadastros exclusivos do simulador e snapshots independentes das obras operacionais."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class SimulationUnit(Base):
    __tablename__ = "startup_simulation_unit"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    name_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    projects: Mapped[list[SimulationProject]] = relationship(back_populates="unit")


class SimulationProject(Base):
    __tablename__ = "startup_simulation_project"

    id: Mapped[str] = uuid_pk()
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("startup_simulation_unit.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    name_key: Mapped[str] = mapped_column(String(160), nullable=False)
    legacy_project_context_id: Mapped[str | None] = mapped_column(String(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    unit: Mapped[SimulationUnit] = relationship(back_populates="projects")
    scenarios: Mapped[list[StartupScenario]] = relationship(back_populates="project")

    __table_args__ = (Index(
        "startup_simulation_project_unit_name_key", "unit_id", "name_key", unique=True
    ),)


class StartupScenario(Base):
    __tablename__ = "startup_scenario"

    id: Mapped[str] = uuid_pk()
    simulation_project_id: Mapped[str] = mapped_column(
        ForeignKey("startup_simulation_project.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[str] = mapped_column(ForeignKey("User.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    startup_at: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="MANUAL")
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )
    project: Mapped[SimulationProject] = relationship(back_populates="scenarios")
    items: Mapped[list[StartupScenarioEquipment]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan",
        order_by="StartupScenarioEquipment.position",
    )
    __table_args__ = (
        CheckConstraint("source IN ('PROJECT','EXCEL','MANUAL')", name="startup_scenario_source_check"),
        Index("startup_scenario_context_created_idx", "simulation_project_id", "created_at"),
    )


class StartupScenarioEquipment(Base):
    __tablename__ = "startup_scenario_equipment"

    id: Mapped[str] = uuid_pk()
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("startup_scenario.id", ondelete="CASCADE"), nullable=False
    )
    # Proveniência legada opcional. Novas simulações nunca consultam Equipment.
    equipment_id: Mapped[str | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    origin: Mapped[str | None] = mapped_column(String(160), nullable=True)
    discipline: Mapped[str | None] = mapped_column(String(160), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    area: Mapped[str | None] = mapped_column(String(160), nullable=True)
    responsible: Mapped[str | None] = mapped_column(String(160), nullable=True)
    startup_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplies_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legal_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manufacture_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pre_start_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scenario: Mapped[StartupScenario] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint(
            "(supplies_days IS NULL OR supplies_days BETWEEN 0 AND 36500) AND "
            "(legal_days IS NULL OR legal_days BETWEEN 0 AND 36500) AND "
            "(manufacture_days IS NULL OR manufacture_days BETWEEN 0 AND 36500) AND "
            "(pre_start_days IS NULL OR pre_start_days BETWEEN 0 AND 36500)",
            name="startup_scenario_equipment_days_check",
        ),
        Index("startup_scenario_equipment_scenario_idx", "scenario_id", "position", unique=True),
    )
