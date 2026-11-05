"""Habilita a extensão `unaccent` para buscas sem acento.

Revision ID: 0030_unaccent_search
Revises: 0029_project_cascade_sync
"""

from __future__ import annotations

from alembic import op

revision = "0030_unaccent_search"
down_revision = "0029_project_cascade_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS unaccent")
