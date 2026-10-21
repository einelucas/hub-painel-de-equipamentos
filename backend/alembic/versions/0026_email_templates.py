"""Modelos HTML por tipo de notificação e alternativa HTML na outbox.

Revision ID: 0026_email_templates
Revises: 0025_email_delivery_provider

Compatível com os modelos antigos: a tabela nasce vazia e cada linha é criada
sob demanda a partir do `notification_rule` correspondente, preservando os
textos já configurados. `email_delivery.html_body` é opcional, então os envios
anteriores continuam válidos apenas com texto simples.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision = "0026_email_templates"
down_revision = "0025_email_delivery_provider"
branch_labels = None
depends_on = None
_TIMESTAMP3 = TIMESTAMP(precision=3, timezone=False)


def upgrade() -> None:
    op.create_table(
        "email_template",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False, unique=True),
        sa.Column("subject_template", sa.Text(), nullable=False),
        sa.Column("title_template", sa.Text(), nullable=False),
        sa.Column("intro_template", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_template", sa.Text(), nullable=False, server_default=""),
        sa.Column("button_label", sa.Text(), nullable=False, server_default=""),
        sa.Column("footer_template", sa.Text(), nullable=False, server_default=""),
        sa.Column("custom_html", sa.Text(), nullable=True),
        sa.Column(
            "use_custom_html", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("show_details", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_alert", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_button", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_footer", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", _TIMESTAMP3, nullable=False),
    )
    op.add_column("email_delivery", sa.Column("html_body", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_delivery", "html_body")
    op.drop_table("email_template")
