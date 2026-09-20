"""Processo de aquisição: negociação, jurídico, contrato, SC/OCI e OC.

Revision ID: 0003_acquisition_process
Revises: 0002_equipment_domain
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_acquisition_process"
down_revision: str | None = "0002_equipment_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3)
    op.create_table(
        "negotiation",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("equalized", sa.Boolean(), nullable=False),
        sa.Column("negotiated_at", sa.Date(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id"),
    )
    op.create_table(
        "legal_process",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("opened_at", sa.Date(), nullable=True),
        sa.Column("ticket_number", sa.String(length=80), nullable=True),
        sa.Column("draft_prepared", sa.Boolean(), nullable=False),
        sa.Column("draft_approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id"),
    )
    op.create_table(
        "contract",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("contract_number", sa.String(length=80), nullable=True),
        sa.Column("executed_at", sa.Date(), nullable=True),
        sa.Column("delivery_at", sa.Date(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id"),
    )
    op.create_table(
        "purchase_request",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=True),
        sa.Column("request_number", sa.String(length=80), nullable=True),
        sa.Column("requested_at", sa.Date(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("kind IS NULL OR kind IN ('SC', 'OCI')", name="purchase_request_kind_check"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id"),
    )
    op.create_table(
        "purchase_order",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("order_number", sa.String(length=80), nullable=True),
        sa.Column("ordered_at", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="purchase_order_amount_check"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_id"),
    )


def downgrade() -> None:
    op.drop_table("purchase_order")
    op.drop_table("purchase_request")
    op.drop_table("contract")
    op.drop_table("legal_process")
    op.drop_table("negotiation")
