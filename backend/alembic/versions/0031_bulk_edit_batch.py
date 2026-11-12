"""Fundação transacional da edição em lote, sem atualização de dados existentes.

Revision ID: 0031_bulk_edit_batch
Revises: 0030_unaccent_search
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from alembic import op

revision = "0031_bulk_edit_batch"
down_revision = "0030_unaccent_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bulk_edit_batch",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column("preview_token", sa.String(length=100), nullable=False, unique=True),
        sa.Column("actor_user_id", sa.String(), sa.ForeignKey("User.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "project_context_id", sa.String(),
            sa.ForeignKey("project_context.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "equipment_id", sa.String(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("target", sa.String(length=20), nullable=False),
        sa.Column("request_payload", JSONB(), nullable=False),
        sa.Column("preview_payload", JSONB(), nullable=False),
        sa.Column("expires_at", TIMESTAMP(precision=3, timezone=False), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("result_payload", JSONB(), nullable=True),
        sa.Column("created_at", TIMESTAMP(precision=3, timezone=False), nullable=False),
        sa.CheckConstraint(
            "target IN ('equipment', 'component')",
            name="bulk_edit_batch_target_check",
        ),
        sa.CheckConstraint(
            "status IN ('PREVIEW', 'APPLIED')",
            name="bulk_edit_batch_status_check",
        ),
        sa.CheckConstraint(
            "(target = 'equipment' AND equipment_id IS NULL) "
            "OR (target = 'component' AND equipment_id IS NOT NULL)",
            name="bulk_edit_batch_target_equipment_check",
        ),
    )
    op.create_index(
        "bulk_edit_batch_actor_idempotency_key", "bulk_edit_batch",
        ["actor_user_id", "idempotency_key"], unique=True,
    )
    op.create_index("bulk_edit_batch_expiry_idx", "bulk_edit_batch", ["expires_at"])


def downgrade() -> None:
    op.drop_index("bulk_edit_batch_expiry_idx", table_name="bulk_edit_batch")
    op.drop_index("bulk_edit_batch_actor_idempotency_key", table_name="bulk_edit_batch")
    op.drop_table("bulk_edit_batch")
