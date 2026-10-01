"""Código corporativo do fornecedor e aliases de origem (carga LEM F2).

`supplier.corporate_code` ("Cód. Fornecedor. CS") entra como coluna nula:
fornecedores cadastrados manualmente antes desta etapa não têm código e a
migration não pode falhar por isso. A unicidade vale só quando preenchido.

`supplier_alias` guarda os nomes históricos do Monday apontando para o
fornecedor oficial, sem criar fornecedores duplicados.

Revision ID: 0010_supplier_corporate_code
Revises: 0009_requirement_waivers
Create Date: 2026-09-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

_TIMESTAMP3 = TIMESTAMP(precision=3, timezone=False)

revision = "0010_supplier_corporate_code"
down_revision = "0009_requirement_waivers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("supplier", sa.Column("corporate_code", sa.String(length=20), nullable=True))
    op.create_index(
        "supplier_corporate_code_key",
        "supplier",
        ["corporate_code"],
        unique=True,
        postgresql_where=sa.text("corporate_code IS NOT NULL"),
    )

    op.create_table(
        "supplier_alias",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column(
            "supplier_id",
            sa.String(),
            sa.ForeignKey("supplier.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("context", sa.String(length=80), nullable=False),
        sa.Column("created_at", _TIMESTAMP3, nullable=False),
        sa.CheckConstraint("length(trim(alias)) > 0", name="supplier_alias_alias_check"),
    )
    op.create_index(
        "supplier_alias_source_key",
        "supplier_alias",
        ["source", "context", "alias"],
        unique=True,
    )
    op.create_index("supplier_alias_supplier_idx", "supplier_alias", ["supplier_id"])


def downgrade() -> None:
    op.drop_index("supplier_alias_supplier_idx", table_name="supplier_alias")
    op.drop_index("supplier_alias_source_key", table_name="supplier_alias")
    op.drop_table("supplier_alias")
    op.drop_index("supplier_corporate_code_key", table_name="supplier")
    op.drop_column("supplier", "corporate_code")
