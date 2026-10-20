"""Persiste o provedor de cada e-mail na outbox sem alterar envios já criados.

Revision ID: 0025_email_delivery_provider
Revises: 0024_notification_delivery
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025_email_delivery_provider"
down_revision = "0024_notification_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_delivery",
        sa.Column("provider", sa.String(length=16), nullable=False, server_default="graph"),
    )
    op.create_check_constraint(
        "email_delivery_provider_check",
        "email_delivery",
        "provider IN ('graph','resend')",
    )


def downgrade() -> None:
    op.drop_constraint("email_delivery_provider_check", "email_delivery", type_="check")
    op.drop_column("email_delivery", "provider")
