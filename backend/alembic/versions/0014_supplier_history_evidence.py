"""Histórico de fornecedores e evidências corporativas de recomendação.

Revision ID: 0014_supplier_history
Revises: 0013_optional_unit_context_codes
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014_supplier_history"
down_revision: str | None = "0013_optional_unit_context_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3, timezone=False)

    op.add_column("equipment_supplier", sa.Column("start_stage", sa.Integer(), nullable=True))
    op.add_column("equipment_supplier", sa.Column("end_stage", sa.Integer(), nullable=True))
    op.add_column("equipment_supplier", sa.Column("ended_at", timestamp, nullable=True))
    op.add_column("equipment_supplier", sa.Column("change_reason", sa.String(500), nullable=True))
    op.add_column(
        "equipment_supplier",
        sa.Column("source", sa.String(40), nullable=False, server_default="LEGACY"),
    )
    op.add_column("equipment_supplier", sa.Column("changed_by_user_id", sa.String(), nullable=True))
    op.add_column(
        "equipment_supplier",
        sa.Column("updated_at", timestamp, nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_foreign_key(
        "equipment_supplier_changed_by_user_id_fkey",
        "equipment_supplier",
        "User",
        ["changed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(sa.text("UPDATE equipment_supplier SET updated_at = created_at"))
    op.drop_index("equipment_supplier_single_key", table_name="equipment_supplier")
    op.drop_index("equipment_supplier_pair_key", table_name="equipment_supplier")
    op.create_check_constraint(
        "equipment_supplier_end_check",
        "equipment_supplier",
        "(ended_at IS NULL AND end_stage IS NULL) OR ended_at IS NOT NULL",
    )
    op.create_index(
        "equipment_supplier_active_key",
        "equipment_supplier",
        ["equipment_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "equipment_supplier_supplier_id_idx", "equipment_supplier", ["supplier_id"]
    )

    op.create_table(
        "supplier_recommendation_evidence",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_key", sa.String(240), nullable=False),
        sa.Column("equipment_label", sa.String(240), nullable=False),
        sa.Column("supplier_reference", sa.String(240), nullable=True),
        sa.Column("corporate_code", sa.String(20), nullable=True),
        sa.Column("evidence_type", sa.String(40), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("occurrences", sa.Integer(), nullable=True),
        sa.Column("total_occurrences", sa.Integer(), nullable=True),
        sa.Column("share", sa.Numeric(8, 5), nullable=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("source_key", sa.String(300), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "supplier_evidence_source_key",
        "supplier_recommendation_evidence",
        ["source", "source_key"],
        unique=True,
    )
    op.create_index(
        "supplier_evidence_equipment_key_idx",
        "supplier_recommendation_evidence",
        ["equipment_key"],
    )
    op.create_index(
        "supplier_evidence_corporate_code_idx",
        "supplier_recommendation_evidence",
        ["corporate_code"],
    )


def downgrade() -> None:
    op.drop_index("supplier_evidence_corporate_code_idx", table_name="supplier_recommendation_evidence")
    op.drop_index("supplier_evidence_equipment_key_idx", table_name="supplier_recommendation_evidence")
    op.drop_index("supplier_evidence_source_key", table_name="supplier_recommendation_evidence")
    op.drop_table("supplier_recommendation_evidence")

    op.drop_index("equipment_supplier_supplier_id_idx", table_name="equipment_supplier")
    op.drop_index("equipment_supplier_active_key", table_name="equipment_supplier")
    op.drop_constraint("equipment_supplier_end_check", "equipment_supplier", type_="check")
    op.create_index(
        "equipment_supplier_pair_key",
        "equipment_supplier",
        ["equipment_id", "supplier_id"],
        unique=True,
    )
    op.create_index(
        "equipment_supplier_single_key", "equipment_supplier", ["equipment_id"], unique=True
    )
    op.drop_constraint(
        "equipment_supplier_changed_by_user_id_fkey", "equipment_supplier", type_="foreignkey"
    )
    for column in (
        "updated_at",
        "changed_by_user_id",
        "source",
        "change_reason",
        "ended_at",
        "end_stage",
        "start_stage",
    ):
        op.drop_column("equipment_supplier", column)
