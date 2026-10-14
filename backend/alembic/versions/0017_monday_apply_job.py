"""Job em segundo plano do apply da importação Monday.

Revision ID: 0017_monday_apply_job
Revises: 0016_global_work_packages
Create Date: 2026-10-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017_monday_apply_job"
down_revision: str | None = "0016_global_work_packages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

timestamp = postgresql.TIMESTAMP(precision=3, timezone=False)


def upgrade() -> None:
    op.create_table(
        "monday_apply_job",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("batch_ids", postgresql.JSONB(), nullable=False),
        sa.Column("plan_sha256", sa.String(length=64), nullable=False),
        sa.Column("migration_run_id", sa.String(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.Column("finished_at", timestamp, nullable=True),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="monday_apply_job_status_check",
        ),
        sa.ForeignKeyConstraint(["project_context_id"], ["project_context.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["User.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "monday_apply_job_running_key",
        "monday_apply_job",
        ["project_context_id"],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )


def downgrade() -> None:
    op.drop_index("monday_apply_job_running_key", table_name="monday_apply_job")
    op.drop_table("monday_apply_job")
