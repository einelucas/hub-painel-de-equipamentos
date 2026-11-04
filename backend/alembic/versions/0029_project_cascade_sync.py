"""Exclusão segura de obras e log persistente de sincronização.

Revision ID: 0029_project_cascade_sync
Revises: 0028_user_notifications
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0029_project_cascade_sync"
down_revision = "0028_user_notifications"
branch_labels = None
depends_on = None
_TS = TIMESTAMP(precision=3, timezone=False)

_PROJECT_FKS = (
    ("project_eap", "project_eap_project_context_id_fkey"),
    ("equipment", "equipment_project_context_id_fkey"),
    ("monday_import_batch", "monday_import_batch_project_context_id_fkey"),
    ("monday_migration_run", "monday_migration_run_project_context_id_fkey"),
    ("monday_apply_job", "monday_apply_job_project_context_id_fkey"),
    ("master_project_creation", "master_project_creation_project_context_id_fkey"),
)


def _replace_project_fks(ondelete: str) -> None:
    for table, constraint in _PROJECT_FKS:
        op.drop_constraint(constraint, table, type_="foreignkey")
        op.create_foreign_key(
            constraint,
            table,
            "project_context",
            ["project_context_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    _replace_project_fks("CASCADE")
    op.create_table(
        "sync_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=True),
        sa.Column("equipment_id", sa.String(), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("User.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("created_at", _TS, nullable=False),
        sa.CheckConstraint(
            "event_type IN ('created','updated','deleted')", name="sync_event_type_check"
        ),
    )
    op.create_index("sync_event_unit_id_id_idx", "sync_event", ["unit_id", "id"])
    op.create_index(
        "sync_event_project_context_id_id_idx", "sync_event", ["project_context_id", "id"]
    )
    op.create_index("sync_event_equipment_id_id_idx", "sync_event", ["equipment_id", "id"])

    op.create_table(
        "contract_file_cleanup",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("updated_at", _TS, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("contract_file_cleanup")
    op.drop_index("sync_event_equipment_id_id_idx", table_name="sync_event")
    op.drop_index("sync_event_project_context_id_id_idx", table_name="sync_event")
    op.drop_index("sync_event_unit_id_id_idx", table_name="sync_event")
    op.drop_table("sync_event")
    _replace_project_fks("RESTRICT")
