"""Persiste payload e lease para retomada dos applies Monday.

Revision ID: 0022_resilient_apply_jobs
Revises: 0021_performance_indexes
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022_resilient_apply_jobs"
down_revision: str | None = "0021_performance_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "monday_apply_job",
        sa.Column(
            "mapping_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("monday_apply_job", sa.Column("lease_id", sa.String(length=36), nullable=True))
    op.add_column(
        "monday_apply_job", sa.Column("heartbeat_at", postgresql.TIMESTAMP(precision=3), nullable=True)
    )
    op.add_column(
        "monday_apply_job", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
    )
    op.create_index("monday_apply_job_recovery_idx", "monday_apply_job", ["status", "heartbeat_at"])


def downgrade() -> None:
    op.drop_index("monday_apply_job_recovery_idx", table_name="monday_apply_job")
    op.drop_column("monday_apply_job", "attempt_count")
    op.drop_column("monday_apply_job", "heartbeat_at")
    op.drop_column("monday_apply_job", "lease_id")
    op.drop_column("monday_apply_job", "mapping_payload")
