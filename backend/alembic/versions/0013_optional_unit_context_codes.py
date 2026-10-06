"""Torna códigos de unidade e obra opcionais.

Revision ID: 0013_optional_unit_context_codes
Revises: 0012_component_name_length
Create Date: 2026-10-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_optional_unit_context_codes"
down_revision: str | None = "0012_component_name_length"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("unit", "code", existing_type=sa.String(length=40), nullable=True)
    op.alter_column("project_context", "code", existing_type=sa.String(length=60), nullable=True)


def downgrade() -> None:
    # IDs são únicos e cabem nos limites das colunas; preenchem apenas registros
    # que não têm mais código antes de restaurar as restrições NOT NULL.
    op.execute(sa.text("UPDATE unit SET code = id WHERE code IS NULL"))
    op.execute(sa.text("UPDATE project_context SET code = id WHERE code IS NULL"))
    op.alter_column("project_context", "code", existing_type=sa.String(length=60), nullable=False)
    op.alter_column("unit", "code", existing_type=sa.String(length=40), nullable=False)
