"""Etapa 7.1 — requirement_waiver (dispensa de requisitos por grupo/fase).

Substitui o mecanismo rígido de `workflow_exception` (não removido aqui:
nenhum registro real existe em DEV, mantido só por compatibilidade de
schema — ver docs/validation/etapa-07-1-requirement-waivers.md).

Revision ID: 0009_requirement_waivers
Revises: 0008_notification_events
Create Date: 2026-09-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

_TIMESTAMP3 = TIMESTAMP(precision=3, timezone=False)

revision = "0009_requirement_waivers"
down_revision = "0008_notification_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requirement_waiver",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column(
            "equipment_id",
            sa.String(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("requirement_group_code", sa.String(length=40), nullable=False),
        sa.Column("reason_code", sa.String(length=20), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_by_id",
            sa.String(),
            sa.ForeignKey("User.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", _TIMESTAMP3, nullable=False),
        sa.Column(
            "revoked_by_id",
            sa.String(),
            sa.ForeignKey("User.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("revoked_at", _TIMESTAMP3, nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("stage BETWEEN 0 AND 8", name="requirement_waiver_stage_check"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','REVOKED')", name="requirement_waiver_status_check"
        ),
        sa.CheckConstraint(
            "reason_code IN ('IMPORTATION','FIXED_SUPPLIER','EXCEPTIONAL_PROCESS','OTHER')",
            name="requirement_waiver_reason_code_check",
        ),
        sa.CheckConstraint(
            "length(trim(justification)) > 0", name="requirement_waiver_justification_check"
        ),
    )
    op.create_index(
        "requirement_waiver_one_active_key",
        "requirement_waiver",
        ["equipment_id", "stage", "requirement_group_code"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "requirement_waiver_equipment_id_idx", "requirement_waiver", ["equipment_id"]
    )
    op.alter_column("requirement_waiver", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("requirement_waiver_equipment_id_idx", table_name="requirement_waiver")
    op.drop_index("requirement_waiver_one_active_key", table_name="requirement_waiver")
    op.drop_table("requirement_waiver")
