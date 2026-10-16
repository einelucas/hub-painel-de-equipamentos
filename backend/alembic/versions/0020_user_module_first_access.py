"""Registra o primeiro acesso ao contexto global do módulo por usuário.

Revision ID: 0020_user_module_first_access
Revises: 0019_discipline_ei_code_name
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020_user_module_first_access"
down_revision: str | None = "0019_discipline_ei_code_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_module_context_preference",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "first_access_at",
            postgresql.TIMESTAMP(precision=3),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["User.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_module_context_preference")
