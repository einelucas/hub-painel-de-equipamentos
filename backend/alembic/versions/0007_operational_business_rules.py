"""Etapa 7A — modelo de dados das regras operacionais do negócio.

- Contract/PurchaseRequest/PurchaseOrder passam de 1:1 para 1:N com Equipment.
- Contract ganha metadado de arquivo (1:1 arquivo-contrato); perde
  `delivery_at` — a janela de entrega contratual passa a pertencer ao
  Equipment (`contractual_delivery_start/end`), com o `delivery_at` legado
  migrado como data final antes da coluna ser removida.
- Equipment ganha `operational_status`, `project_total_value` e a janela de
  entrega contratual.
- EquipmentSupplier passa a permitir no máximo um vínculo por equipamento.
- Novas tabelas: operational_status_event, workflow_exception,
  reopen_request, comment.

Revision ID: 0007_operational_business_rules
Revises: 0006_monday_apply_foundation
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_operational_business_rules"
down_revision: str | None = "0006_monday_apply_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3)

    # --- Equipment: estado operacional, valor total, janela de entrega ---
    op.add_column(
        "equipment",
        sa.Column("operational_status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("equipment", sa.Column("project_total_value", sa.Numeric(18, 2), nullable=True))
    op.add_column("equipment", sa.Column("contractual_delivery_start", sa.Date(), nullable=True))
    op.add_column("equipment", sa.Column("contractual_delivery_end", sa.Date(), nullable=True))
    op.alter_column("equipment", "operational_status", server_default=None)
    op.create_check_constraint(
        "equipment_operational_status_check",
        "equipment",
        "operational_status IN ('ACTIVE','STANDBY','CANCELLED','IN_SANITATION')",
    )
    op.create_check_constraint(
        "equipment_project_total_value_check",
        "equipment",
        "project_total_value IS NULL OR project_total_value >= 0",
    )
    op.create_check_constraint(
        "equipment_delivery_window_order_check",
        "equipment",
        "contractual_delivery_start IS NULL OR contractual_delivery_end IS NULL "
        "OR contractual_delivery_start <= contractual_delivery_end",
    )
    op.create_index("equipment_operational_status_idx", "equipment", ["operational_status"])

    # --- Migra Contract.delivery_at -> Equipment.contractual_delivery_end ---
    # (data final da janela, conforme instruído) antes de remover a coluna.
    op.execute(
        """
        UPDATE equipment
        SET contractual_delivery_end = contract.delivery_at
        FROM contract
        WHERE contract.equipment_id = equipment.id
          AND contract.delivery_at IS NOT NULL
        """
    )

    # --- Contract: 1:1 -> 1:N, ganha metadado de arquivo, perde delivery_at ---
    op.drop_constraint("contract_equipment_id_key", "contract", type_="unique")
    op.add_column("contract", sa.Column("file_storage_key", sa.String(length=500), nullable=True))
    op.add_column("contract", sa.Column("file_name", sa.String(length=255), nullable=True))
    op.add_column("contract", sa.Column("file_content_type", sa.String(length=120), nullable=True))
    op.add_column("contract", sa.Column("file_size_bytes", sa.Integer(), nullable=True))
    op.add_column("contract", sa.Column("file_uploaded_by_id", sa.String(), nullable=True))
    op.add_column("contract", sa.Column("file_uploaded_at", timestamp, nullable=True))
    op.create_foreign_key(
        "contract_file_uploaded_by_id_fkey",
        "contract",
        "User",
        ["file_uploaded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "contract_file_size_check", "contract", "file_size_bytes IS NULL OR file_size_bytes >= 0"
    )
    op.drop_column("contract", "delivery_at")

    # --- PurchaseRequest / PurchaseOrder: 1:1 -> 1:N ---
    op.drop_constraint("purchase_request_equipment_id_key", "purchase_request", type_="unique")
    op.drop_constraint("purchase_order_equipment_id_key", "purchase_order", type_="unique")

    # --- EquipmentSupplier: no máximo um vínculo por equipamento ---
    op.drop_index("equipment_supplier_primary_key", table_name="equipment_supplier")
    op.create_index(
        "equipment_supplier_single_key", "equipment_supplier", ["equipment_id"], unique=True
    )

    # --- OperationalStatusEvent ---
    op.create_table(
        "operational_status_event",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("resulting_status", sa.String(length=20), nullable=False),
        sa.Column("stage_at_event", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("occurred_at", timestamp, nullable=False),
        sa.CheckConstraint(
            "kind IN ('STANDBY_ENTERED','STANDBY_LIFTED','CANCELLED',"
            "'SANITATION_ENTERED','SANITATION_ENDED')",
            name="operational_status_event_kind_check",
        ),
        sa.CheckConstraint(
            "resulting_status IN ('ACTIVE','STANDBY','CANCELLED','IN_SANITATION')",
            name="operational_status_event_resulting_status_check",
        ),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["User.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "operational_status_event_equipment_id_idx", "operational_status_event", ["equipment_id"]
    )

    # --- WorkflowException ---
    op.create_table(
        "workflow_exception",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="ACTIVE"),
        sa.Column("source_stage", sa.Integer(), nullable=False),
        sa.Column("intended_target_stage", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("created_by_id", sa.String(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("completed_at", timestamp, nullable=True),
        sa.Column("cancelled_at", timestamp, nullable=True),
        sa.CheckConstraint("type IN ('FIXED_SUPPLIER','IMPORTATION')", name="workflow_exception_type_check"),
        sa.CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','CANCELLED')", name="workflow_exception_status_check"
        ),
        sa.CheckConstraint("source_stage BETWEEN 0 AND 8", name="workflow_exception_source_stage_check"),
        sa.CheckConstraint(
            "intended_target_stage BETWEEN 0 AND 8", name="workflow_exception_target_stage_check"
        ),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["User.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("workflow_exception", "status", server_default=None)
    op.create_index(
        "workflow_exception_one_active_key",
        "workflow_exception",
        ["equipment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index("workflow_exception_equipment_id_idx", "workflow_exception", ["equipment_id"])

    # --- ReopenRequest ---
    op.create_table(
        "reopen_request",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("source_stage", sa.Integer(), nullable=False),
        sa.Column("target_stage", sa.Integer(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="PENDING"),
        sa.Column("requested_by_id", sa.String(), nullable=True),
        sa.Column("requested_at", timestamp, nullable=False),
        sa.Column("decided_by_id", sa.String(), nullable=True),
        sa.Column("decided_at", timestamp, nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')", name="reopen_request_status_check"
        ),
        sa.CheckConstraint("source_stage BETWEEN 0 AND 8", name="reopen_request_source_stage_check"),
        sa.CheckConstraint("target_stage BETWEEN 0 AND 8", name="reopen_request_target_stage_check"),
        sa.CheckConstraint("target_stage < source_stage", name="reopen_request_target_before_source_check"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["User.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_id"], ["User.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("reopen_request", "status", server_default=None)
    op.create_index(
        "reopen_request_one_pending_key",
        "reopen_request",
        ["equipment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index("reopen_request_equipment_id_idx", "reopen_request", ["equipment_id"])

    # --- Comment ---
    op.create_table(
        "comment",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("author_user_id", sa.String(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.CheckConstraint("length(trim(text)) > 0", name="comment_text_not_blank_check"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["User.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("comment_equipment_id_idx", "comment", ["equipment_id", "created_at"])


def downgrade() -> None:
    op.drop_table("comment")

    op.drop_index("reopen_request_equipment_id_idx", table_name="reopen_request")
    op.drop_index("reopen_request_one_pending_key", table_name="reopen_request")
    op.drop_table("reopen_request")

    op.drop_index("workflow_exception_equipment_id_idx", table_name="workflow_exception")
    op.drop_index("workflow_exception_one_active_key", table_name="workflow_exception")
    op.drop_table("workflow_exception")

    op.drop_index(
        "operational_status_event_equipment_id_idx", table_name="operational_status_event"
    )
    op.drop_table("operational_status_event")

    op.drop_index("equipment_supplier_single_key", table_name="equipment_supplier")
    op.create_index(
        "equipment_supplier_primary_key",
        "equipment_supplier",
        ["equipment_id"],
        unique=True,
        postgresql_where=sa.text("is_primary = true"),
    )

    op.create_unique_constraint("purchase_order_equipment_id_key", "purchase_order", ["equipment_id"])
    op.create_unique_constraint(
        "purchase_request_equipment_id_key", "purchase_request", ["equipment_id"]
    )

    op.add_column("contract", sa.Column("delivery_at", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE contract
        SET delivery_at = equipment.contractual_delivery_end
        FROM equipment
        WHERE equipment.id = contract.equipment_id
          AND equipment.contractual_delivery_end IS NOT NULL
        """
    )
    op.drop_constraint("contract_file_size_check", "contract", type_="check")
    op.drop_constraint("contract_file_uploaded_by_id_fkey", "contract", type_="foreignkey")
    op.drop_column("contract", "file_uploaded_at")
    op.drop_column("contract", "file_uploaded_by_id")
    op.drop_column("contract", "file_size_bytes")
    op.drop_column("contract", "file_content_type")
    op.drop_column("contract", "file_name")
    op.drop_column("contract", "file_storage_key")
    op.create_unique_constraint("contract_equipment_id_key", "contract", ["equipment_id"])

    op.drop_index("equipment_operational_status_idx", table_name="equipment")
    op.drop_constraint("equipment_delivery_window_order_check", "equipment", type_="check")
    op.drop_constraint("equipment_project_total_value_check", "equipment", type_="check")
    op.drop_constraint("equipment_operational_status_check", "equipment", type_="check")
    op.drop_column("equipment", "contractual_delivery_end")
    op.drop_column("equipment", "contractual_delivery_start")
    op.drop_column("equipment", "project_total_value")
    op.drop_column("equipment", "operational_status")
