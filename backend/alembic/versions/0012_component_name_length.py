"""Amplia `equipment_component.name` de VARCHAR(200) para VARCHAR(500).

Somente o tamanho da coluna muda: NOT NULL, índices, FKs e a estratégia de
identidade dos componentes permanecem iguais (a identidade vem da origem, não do
nome gravado). Motivo: subitens reais do Monday com nomes de 215 a 233
caracteres, que não podem ser truncados.

Downgrade: só é executável quando NÃO existir `length(name) > 200`. Não há
truncamento automático; antes de qualquer downgrade, valide explicitamente:

    SELECT count(*) FROM equipment_component WHERE length(name) > 200;  -- deve ser 0

Revision ID: 0012_component_name_length
Revises: 0011_eap_foundation
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0012_component_name_length"
down_revision = "0011_eap_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "equipment_component",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.String(length=500),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Validação explícita: recusa (nunca trunca) se algum nome não couber em 200.
    too_long = op.get_bind().execute(
        sa.text("SELECT count(*) FROM equipment_component WHERE length(name) > 200")
    ).scalar_one()
    if too_long:
        raise RuntimeError(
            f"Downgrade bloqueado: {too_long} componente(s) com nome > 200 caracteres. "
            "Não há truncamento automático; trate os dados antes."
        )
    op.alter_column(
        "equipment_component",
        "name",
        existing_type=sa.String(length=500),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
