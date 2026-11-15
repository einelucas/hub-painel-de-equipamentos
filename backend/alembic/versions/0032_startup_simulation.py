"""Cenários isolados para simulação regressiva de datas de startup.

Revision ID: 0032_startup_simulation
Revises: 0031_bulk_edit_batch
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0032_startup_simulation"
down_revision = "0031_bulk_edit_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "startup_scenario",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_context_id", sa.String(), sa.ForeignKey("project_context.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.String(), sa.ForeignKey("User.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("startup_at", sa.Date(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("created_at", TIMESTAMP(precision=3, timezone=False), nullable=False),
        sa.Column("updated_at", TIMESTAMP(precision=3, timezone=False), nullable=False),
        sa.CheckConstraint("source IN ('PROJECT','EXCEL','MANUAL')", name="startup_scenario_source_check"),
    )
    op.create_index("startup_scenario_context_created_idx", "startup_scenario", ["project_context_id", "created_at"])
    op.create_table(
        "startup_scenario_equipment",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scenario_id", sa.String(), sa.ForeignKey("startup_scenario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_id", sa.String(), sa.ForeignKey("equipment.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("origin", sa.String(160)),
        sa.Column("discipline", sa.String(160)),
        sa.Column("supplier", sa.String(200)),
        sa.Column("area", sa.String(160)),
        sa.Column("responsible", sa.String(160)),
        sa.Column("startup_at", sa.Date()),
        sa.Column("supplies_days", sa.Integer()),
        sa.Column("legal_days", sa.Integer()),
        sa.Column("manufacture_days", sa.Integer()),
        sa.Column("pre_start_days", sa.Integer()),
        sa.CheckConstraint(
            "(supplies_days IS NULL OR supplies_days BETWEEN 0 AND 36500) AND "
            "(legal_days IS NULL OR legal_days BETWEEN 0 AND 36500) AND "
            "(manufacture_days IS NULL OR manufacture_days BETWEEN 0 AND 36500) AND "
            "(pre_start_days IS NULL OR pre_start_days BETWEEN 0 AND 36500)",
            name="startup_scenario_equipment_days_check",
        ),
    )
    op.create_index("startup_scenario_equipment_scenario_idx", "startup_scenario_equipment", ["scenario_id", "position"], unique=True)


def downgrade() -> None:
    op.drop_index("startup_scenario_equipment_scenario_idx", table_name="startup_scenario_equipment")
    op.drop_table("startup_scenario_equipment")
    op.drop_index("startup_scenario_context_created_idx", table_name="startup_scenario")
    op.drop_table("startup_scenario")
