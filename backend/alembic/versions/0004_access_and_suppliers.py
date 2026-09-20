"""Acesso por unidade e fornecedores.

Revision ID: 0004_access_and_suppliers
Revises: 0003_acquisition_process
Create Date: 2026-09-20

Backfill: até aqui todo usuário enxergava todas as unidades. Para não remover
acesso de quem já usa o sistema, VIEWER/ANALYST existentes recebem vínculo com
as unidades que existem hoje. ADMIN não precisa de vínculo (é global por perfil)
e usuários criados depois desta migration exigem atribuição explícita.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_access_and_suppliers"
down_revision: str | None = "0003_acquisition_process"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3)

    op.create_table(
        "user_unit_access",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["User.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["unit.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "user_unit_access_user_unit_key", "user_unit_access", ["user_id", "unit_id"], unique=True
    )
    op.create_index("user_unit_access_user_id_idx", "user_unit_access", ["user_id"])

    op.create_table(
        "supplier",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("trade_name", sa.String(length=200), nullable=True),
        sa.Column("tax_id", sa.String(length=32), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "supplier_tax_id_key",
        "supplier",
        ["tax_id"],
        unique=True,
        postgresql_where=sa.text("tax_id IS NOT NULL"),
    )
    op.create_index("supplier_legal_name_idx", "supplier", ["legal_name"])

    op.create_table(
        "equipment_supplier",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("supplier_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["supplier.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "equipment_supplier_pair_key",
        "equipment_supplier",
        ["equipment_id", "supplier_id"],
        unique=True,
    )
    op.create_index(
        "equipment_supplier_primary_key",
        "equipment_supplier",
        ["equipment_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_index(
        "equipment_supplier_equipment_id_idx", "equipment_supplier", ["equipment_id"]
    )

    op.execute(
        sa.text(
            """
            INSERT INTO user_unit_access (id, user_id, unit_id, created_at)
            SELECT gen_random_uuid()::text, u."id", un.id, NOW()
            FROM "User" u
            CROSS JOIN unit un
            WHERE u."role" IN ('VIEWER', 'ANALYST')
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("equipment_supplier_equipment_id_idx", table_name="equipment_supplier")
    op.drop_index("equipment_supplier_primary_key", table_name="equipment_supplier")
    op.drop_index("equipment_supplier_pair_key", table_name="equipment_supplier")
    op.drop_table("equipment_supplier")
    op.drop_index("supplier_legal_name_idx", table_name="supplier")
    op.drop_index("supplier_tax_id_key", table_name="supplier")
    op.drop_table("supplier")
    op.drop_index("user_unit_access_user_id_idx", table_name="user_unit_access")
    op.drop_index("user_unit_access_user_unit_key", table_name="user_unit_access")
    op.drop_table("user_unit_access")
