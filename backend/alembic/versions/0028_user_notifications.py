"""Caixa interna por usuário do Painel de Equipamentos.

Revision ID: 0028_user_notifications
Revises: 0027_master_equipment_catalog
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision = "0028_user_notifications"
down_revision = "0027_master_equipment_catalog"
branch_labels = None
depends_on = None
_TS = TIMESTAMP(precision=3, timezone=False)


def upgrade() -> None:
    op.create_table(
        "user_notification",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "recipient_user_id",
            sa.String(),
            sa.ForeignKey("User.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("User.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("module_key", sa.String(40), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column(
            "equipment_id",
            sa.String(),
            sa.ForeignKey("equipment.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reopen_request_id",
            sa.String(),
            sa.ForeignKey("reopen_request.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("target_url", sa.String(500), nullable=True),
        sa.Column("event_key", sa.String(200), nullable=False),
        sa.Column("created_at", _TS, nullable=False),
        sa.Column("read_at", _TS, nullable=True),
        sa.CheckConstraint(
            "module_key = 'EQUIPMENT_PANEL'", name="user_notification_module_check"
        ),
        sa.CheckConstraint(
            "event_type IN ('REOPEN_REQUESTED','REOPEN_APPROVED','REOPEN_REJECTED',"
            "'KICKOFF','FUP','STARTUP_REMINDER','NEGOTIATION_OVERDUE',"
            "'DELIVERY_REMINDER','COMPLETED')",
            name="user_notification_event_type_check",
        ),
    )
    op.create_index(
        "user_notification_recipient_event_key",
        "user_notification",
        ["recipient_user_id", "event_key"],
        unique=True,
    )
    op.create_index(
        "user_notification_recipient_module_created_idx",
        "user_notification",
        ["recipient_user_id", "module_key", "created_at"],
    )
    op.create_index(
        "user_notification_recipient_unread_idx",
        "user_notification",
        ["recipient_user_id", "module_key"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(
        "user_notification_reopen_request_idx",
        "user_notification",
        ["reopen_request_id"],
    )


def downgrade() -> None:
    op.drop_index("user_notification_reopen_request_idx", table_name="user_notification")
    op.drop_index("user_notification_recipient_unread_idx", table_name="user_notification")
    op.drop_index(
        "user_notification_recipient_module_created_idx", table_name="user_notification"
    )
    op.drop_index("user_notification_recipient_event_key", table_name="user_notification")
    op.drop_table("user_notification")
