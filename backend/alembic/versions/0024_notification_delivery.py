"""Centro de notificações: regras configuráveis e outbox de e-mails."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0024_notification_delivery"
down_revision = "0023_discipline_criticality"
branch_labels = None
depends_on = None
_TIMESTAMP3 = TIMESTAMP(precision=3, timezone=False)


def upgrade() -> None:
    op.create_table(
        "notification_rule",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("include_responsible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("days_before", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recipient_emails", sa.Text(), nullable=False, server_default=""),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("updated_at", _TIMESTAMP3, nullable=False),
        sa.CheckConstraint("days_before >= 0 AND days_before <= 365", name="notification_rule_days_check"),
    )
    op.create_table(
        "email_delivery",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dedup_key", sa.String(250), nullable=False, unique=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column(
            "equipment_id", sa.String(),
            sa.ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("recipient_summary", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", _TIMESTAMP3, nullable=False),
        sa.Column("processed_at", _TIMESTAMP3, nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','ACCEPTED','SIMULATED','FAILED','SKIPPED')",
            name="email_delivery_status_check",
        ),
    )
    op.create_index("email_delivery_status_idx", "email_delivery", ["status", "created_at"])
    op.create_index("email_delivery_equipment_idx", "email_delivery", ["equipment_id"])


def downgrade() -> None:
    op.drop_index("email_delivery_equipment_idx", table_name="email_delivery")
    op.drop_index("email_delivery_status_idx", table_name="email_delivery")
    op.drop_table("email_delivery")
    op.drop_table("notification_rule")
