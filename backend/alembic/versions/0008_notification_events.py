"""Etapa 7F — notification_event (Kickoff/FUP).

Revision ID: 0008_notification_events
Revises: 0007_operational_business_rules
Create Date: 2026-09-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

_TIMESTAMP3 = TIMESTAMP(precision=3, timezone=False)

revision = "0008_notification_events"
down_revision = "0007_operational_business_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_event",
        sa.Column("id", sa.String(), primary_key=True, nullable=False),
        sa.Column(
            "equipment_id",
            sa.String(),
            sa.ForeignKey("equipment.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_transition_id",
            sa.String(),
            sa.ForeignKey("workflow_transition.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="PENDING"),
        sa.Column("recipient_summary", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", _TIMESTAMP3, nullable=False),
        sa.Column("sent_at", _TIMESTAMP3, nullable=True),
        sa.CheckConstraint("kind IN ('KICKOFF','FUP')", name="notification_event_kind_check"),
        sa.CheckConstraint(
            "status IN ('PENDING','SENT','FAILED')", name="notification_event_status_check"
        ),
    )
    op.create_index(
        "notification_event_transition_kind_key",
        "notification_event",
        ["workflow_transition_id", "kind"],
        unique=True,
    )
    op.create_index(
        "notification_event_equipment_id_idx", "notification_event", ["equipment_id"]
    )


def downgrade() -> None:
    op.drop_index("notification_event_equipment_id_idx", table_name="notification_event")
    op.drop_index("notification_event_transition_kind_key", table_name="notification_event")
    op.drop_table("notification_event")
