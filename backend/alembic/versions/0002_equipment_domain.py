"""Domínio normalizado de equipamentos.

Revision ID: 0002_equipment_domain
Revises: 0001_shared_base
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_equipment_domain"
down_revision: str | None = "0001_shared_base"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3)
    op.create_table(
        "unit",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "discipline",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "project_context",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["unit.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("project_context_unit_code_key", "project_context", ["unit_id", "code"], unique=True)
    op.create_index("project_context_unit_id_idx", "project_context", ["unit_id"])
    op.create_table(
        "area",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["unit.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("area_unit_name_key", "area", ["unit_id", "name"], unique=True)
    op.create_table(
        "work_package",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["project_context_id"], ["project_context.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "work_package_context_code_key", "work_package", ["project_context_id", "code"], unique=True
    )
    op.create_index("work_package_context_id_idx", "work_package", ["project_context_id"])
    op.create_table(
        "equipment",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("origin", sa.String(length=160), nullable=True),
        sa.Column("startup_at", sa.Date(), nullable=True),
        sa.Column("discipline_id", sa.String(), nullable=True),
        sa.Column("area_id", sa.String(), nullable=True),
        sa.Column("work_package_id", sa.String(), nullable=True),
        sa.Column("responsible_user_id", sa.String(), nullable=True),
        sa.Column("criticality", sa.String(length=40), nullable=True),
        sa.Column("current_stage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capex_estimated", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("current_stage BETWEEN 0 AND 8", name="equipment_current_stage_check"),
        sa.CheckConstraint("capex_estimated IS NULL OR capex_estimated >= 0", name="equipment_capex_check"),
        sa.ForeignKeyConstraint(["area_id"], ["area.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["discipline_id"], ["discipline.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_context_id"], ["project_context.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["User.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_package_id"], ["work_package.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("equipment_project_context_id_idx", "equipment", ["project_context_id"])
    op.create_index("equipment_current_stage_idx", "equipment", ["current_stage"])
    op.create_index("equipment_name_idx", "equipment", ["name"])
    op.create_table(
        "equipment_component",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tag", sa.String(length=100), nullable=True),
        sa.Column("sector", sa.String(length=120), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("pre_start_days", sa.Integer(), nullable=True),
        sa.Column("contract_delivery_at", sa.Date(), nullable=True),
        sa.Column("freight_days", sa.Integer(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("lead_time_days IS NULL OR lead_time_days >= 0", name="component_lead_time_check"),
        sa.CheckConstraint("pre_start_days IS NULL OR pre_start_days >= 0", name="component_pre_start_check"),
        sa.CheckConstraint("freight_days IS NULL OR freight_days >= 0", name="component_freight_check"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("equipment_component_equipment_id_idx", "equipment_component", ["equipment_id"])
    op.create_table(
        "workflow_transition",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("from_stage", sa.Integer(), nullable=False),
        sa.Column("to_stage", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.CheckConstraint("from_stage BETWEEN 0 AND 8", name="transition_from_stage_check"),
        sa.CheckConstraint("to_stage BETWEEN 0 AND 8", name="transition_to_stage_check"),
        sa.ForeignKeyConstraint(["actor_id"], ["User.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "workflow_transition_equipment_date_idx",
        "workflow_transition",
        ["equipment_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("workflow_transition_equipment_date_idx", table_name="workflow_transition")
    op.drop_table("workflow_transition")
    op.drop_index("equipment_component_equipment_id_idx", table_name="equipment_component")
    op.drop_table("equipment_component")
    op.drop_index("equipment_name_idx", table_name="equipment")
    op.drop_index("equipment_current_stage_idx", table_name="equipment")
    op.drop_index("equipment_project_context_id_idx", table_name="equipment")
    op.drop_table("equipment")
    op.drop_index("work_package_context_id_idx", table_name="work_package")
    op.drop_index("work_package_context_code_key", table_name="work_package")
    op.drop_table("work_package")
    op.drop_index("area_unit_name_key", table_name="area")
    op.drop_table("area")
    op.drop_index("project_context_unit_id_idx", table_name="project_context")
    op.drop_index("project_context_unit_code_key", table_name="project_context")
    op.drop_table("project_context")
    op.drop_table("discipline")
    op.drop_table("unit")
