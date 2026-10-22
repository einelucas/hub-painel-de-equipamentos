"""Catálogo de modelos reutilizáveis de equipamentos, sem vínculo operacional.

Revision ID: 0027_master_equipment_catalog
Revises: 0026_email_templates
"""
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP
from alembic import op

revision = "0027_master_equipment_catalog"
down_revision = "0026_email_templates"
branch_labels = None
depends_on = None
_TS = TIMESTAMP(precision=3, timezone=False)


def upgrade() -> None:
    op.create_table(
        "master_area",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(180), nullable=False, unique=True),
        sa.Column("is_unassigned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_table(
        "master_equipment",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(220), nullable=False, unique=True),
        sa.Column("review_flags", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )
    op.create_table(
        "master_equipment_area",
        sa.Column("equipment_id", sa.String(), sa.ForeignKey("master_equipment.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("area_id", sa.String(), sa.ForeignKey("master_area.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "master_component_option",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("equipment_id", sa.String(), sa.ForeignKey("master_equipment.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(520), nullable=False),
        sa.Column("requires_quantity_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_name_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("master_component_equipment_name_key", "master_component_option", ["equipment_id", "normalized_name"], unique=True)
    op.create_table(
        "master_project_creation",
        sa.Column("request_id", sa.String(80), primary_key=True),
        sa.Column("project_context_id", sa.String(), sa.ForeignKey("project_context.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.String(80), nullable=False),
        sa.Column("created_at", _TS, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("master_project_creation")
    op.drop_index("master_component_equipment_name_key", table_name="master_component_option")
    op.drop_table("master_component_option")
    op.drop_table("master_equipment_area")
    op.drop_table("master_equipment")
    op.drop_table("master_area")
