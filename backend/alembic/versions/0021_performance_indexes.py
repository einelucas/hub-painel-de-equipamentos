"""Adiciona índices para os filtros e relacionamentos das telas operacionais.

Revision ID: 0021_performance_indexes
Revises: 0020_user_module_first_access
Create Date: 2026-10-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0021_performance_indexes"
down_revision: str | None = "0020_user_module_first_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "equipment_context_stage_name_idx",
        "equipment",
        ["project_context_id", "current_stage", "name"],
    )
    op.create_index(
        "equipment_discipline_stage_idx",
        "equipment",
        ["discipline_id", "current_stage"],
    )
    op.create_index(
        "equipment_responsible_stage_idx",
        "equipment",
        ["responsible_user_id", "current_stage"],
    )
    op.create_index(
        "contract_equipment_created_idx",
        "contract",
        ["equipment_id", "created_at"],
    )
    op.create_index(
        "purchase_request_equipment_created_idx",
        "purchase_request",
        ["equipment_id", "created_at"],
    )
    op.create_index(
        "purchase_order_equipment_created_idx",
        "purchase_order",
        ["equipment_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("purchase_order_equipment_created_idx", table_name="purchase_order")
    op.drop_index("purchase_request_equipment_created_idx", table_name="purchase_request")
    op.drop_index("contract_equipment_created_idx", table_name="contract")
    op.drop_index("equipment_responsible_stage_idx", table_name="equipment")
    op.drop_index("equipment_discipline_stage_idx", table_name="equipment")
    op.drop_index("equipment_context_stage_name_idx", table_name="equipment")
