"""Fundação da EAP corporativa (Unidade + EAP).

Só estrutura — nenhum dado é inserido ou alterado:

- `unit.numeric_code` (nulo nos registros legados; único quando preenchido);
- `eap_node` (catálogo hierárquico ISLAND/PROCESS/AREA, código sem o prefixo
  da unidade);
- `project_eap` (quais nós cada obra utiliza);
- `equipment.eap_node_id` (nulo; `equipment.area_id` permanece intocado).

Revision ID: 0011_eap_foundation
Revises: 0010_supplier_corporate_code
Create Date: 2026-10-01
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

_TIMESTAMP3 = TIMESTAMP(precision=3, timezone=False)

revision = "0011_eap_foundation"
down_revision = "0010_supplier_corporate_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("unit", sa.Column("numeric_code", sa.String(length=10), nullable=True))
    op.create_check_constraint(
        "unit_numeric_code_check", "unit", "numeric_code IS NULL OR numeric_code ~ '^[0-9]+$'"
    )
    op.create_index(
        "unit_numeric_code_key",
        "unit",
        ["numeric_code"],
        unique=True,
        postgresql_where=sa.text("numeric_code IS NOT NULL"),
    )

    op.create_table(
        "eap_node",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column(
            "parent_id",
            sa.String(),
            sa.ForeignKey("eap_node.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", _TIMESTAMP3, nullable=False),
        sa.Column("updated_at", _TIMESTAMP3, nullable=False),
        sa.CheckConstraint("level IN ('ISLAND','PROCESS','AREA')", name="eap_node_level_check"),
        sa.CheckConstraint(
            "length(code) > 0 AND code = btrim(code) AND position(' ' in code) = 0",
            name="eap_node_code_check",
        ),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="eap_node_not_self_parent_check"),
    )
    op.create_index("eap_node_code_key", "eap_node", ["code"], unique=True)
    op.create_index("eap_node_parent_id_idx", "eap_node", ["parent_id"])
    op.create_index("eap_node_level_idx", "eap_node", ["level"])
    op.alter_column("eap_node", "active", server_default=None)

    op.create_table(
        "project_eap",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column(
            "project_context_id",
            sa.String(),
            sa.ForeignKey("project_context.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "eap_node_id",
            sa.String(),
            sa.ForeignKey("eap_node.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", _TIMESTAMP3, nullable=False),
    )
    op.create_index(
        "project_eap_context_node_key",
        "project_eap",
        ["project_context_id", "eap_node_id"],
        unique=True,
    )
    op.create_index("project_eap_eap_node_id_idx", "project_eap", ["eap_node_id"])
    op.alter_column("project_eap", "active", server_default=None)

    op.add_column(
        "equipment",
        sa.Column(
            "eap_node_id",
            sa.String(),
            sa.ForeignKey("eap_node.id", ondelete="SET NULL", name="equipment_eap_node_id_fkey"),
            nullable=True,
        ),
    )
    op.create_index("equipment_eap_node_id_idx", "equipment", ["eap_node_id"])


def downgrade() -> None:
    op.drop_index("equipment_eap_node_id_idx", table_name="equipment")
    op.drop_constraint("equipment_eap_node_id_fkey", "equipment", type_="foreignkey")
    op.drop_column("equipment", "eap_node_id")
    op.drop_index("project_eap_eap_node_id_idx", table_name="project_eap")
    op.drop_index("project_eap_context_node_key", table_name="project_eap")
    op.drop_table("project_eap")
    op.drop_index("eap_node_level_idx", table_name="eap_node")
    op.drop_index("eap_node_parent_id_idx", table_name="eap_node")
    op.drop_index("eap_node_code_key", table_name="eap_node")
    op.drop_table("eap_node")
    op.drop_index("unit_numeric_code_key", table_name="unit")
    op.drop_constraint("unit_numeric_code_check", "unit", type_="check")
    op.drop_column("unit", "numeric_code")
