"""Staging idempotente e mapeamento externo do importador Monday.

Revision ID: 0005_monday_import_foundation
Revises: 0004_access_and_suppliers
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_monday_import_foundation"
down_revision: str | None = "0004_access_and_suppliers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    timestamp = postgresql.TIMESTAMP(precision=3)
    jsonb = postgresql.JSONB(astext_type=sa.Text())

    op.create_table(
        "monday_import_batch",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("board_title", sa.String(length=200), nullable=True),
        sa.Column("sheet_name", sa.String(length=200), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", jsonb, nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("completed_at", timestamp, nullable=True),
        sa.CheckConstraint(
            "status IN ('STAGED', 'APPLIED', 'FAILED')", name="monday_import_batch_status_check"
        ),
        sa.ForeignKeyConstraint(["project_context_id"], ["project_context.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "monday_import_batch_identity_key",
        "monday_import_batch",
        ["project_context_id", "source_system", "file_sha256"],
        unique=True,
    )
    op.create_index(
        "monday_import_batch_context_idx",
        "monday_import_batch",
        ["project_context_id"],
    )

    op.create_table(
        "monday_import_record",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("parent_record_id", sa.String(), nullable=True),
        sa.Column("record_kind", sa.String(length=20), nullable=False),
        sa.Column("source_key", sa.String(length=500), nullable=False),
        sa.Column("group_name", sa.String(length=200), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_payload", jsonb, nullable=False),
        sa.Column("normalized_payload", jsonb, nullable=False),
        sa.Column("final_entity_type", sa.String(length=80), nullable=True),
        sa.Column("final_entity_id", sa.String(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.CheckConstraint(
            "record_kind IN ('equipment', 'component')",
            name="monday_import_record_kind_check",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["monday_import_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_record_id"], ["monday_import_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "monday_import_record_row_key",
        "monday_import_record",
        ["batch_id", "record_kind", "row_number"],
        unique=True,
    )
    op.create_index("monday_import_record_batch_idx", "monday_import_record", ["batch_id"])
    op.create_index("monday_import_record_source_key_idx", "monday_import_record", ["source_key"])
    op.create_index(
        "monday_import_record_final_idx",
        "monday_import_record",
        ["final_entity_type", "final_entity_id"],
    )

    op.create_table(
        "monday_import_issue",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("record_id", sa.String(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("field", sa.String(length=160), nullable=True),
        sa.Column("message", sa.String(length=1000), nullable=False),
        sa.Column("raw_value", jsonb, nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.CheckConstraint("severity IN ('warning', 'error')", name="monday_import_issue_severity_check"),
        sa.ForeignKeyConstraint(["batch_id"], ["monday_import_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["record_id"], ["monday_import_record.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("monday_import_issue_batch_idx", "monday_import_issue", ["batch_id"])
    op.create_index("monday_import_issue_code_idx", "monday_import_issue", ["code"])

    op.create_table(
        "external_mapping",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_context_id", sa.String(), nullable=False),
        sa.Column("source_system", sa.String(length=40), nullable=False),
        sa.Column("source_entity_type", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=500), nullable=False),
        sa.Column("identity_strategy", sa.String(length=80), nullable=False),
        sa.Column("target_entity_type", sa.String(length=80), nullable=False),
        sa.Column("target_entity_id", sa.String(), nullable=False),
        sa.Column("raw_identity", jsonb, nullable=True),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.ForeignKeyConstraint(["project_context_id"], ["project_context.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "external_mapping_source_key",
        "external_mapping",
        ["project_context_id", "source_system", "source_entity_type", "external_id"],
        unique=True,
    )
    op.create_index(
        "external_mapping_target_idx",
        "external_mapping",
        ["target_entity_type", "target_entity_id"],
    )


def downgrade() -> None:
    op.drop_index("external_mapping_target_idx", table_name="external_mapping")
    op.drop_index("external_mapping_source_key", table_name="external_mapping")
    op.drop_table("external_mapping")
    op.drop_index("monday_import_issue_code_idx", table_name="monday_import_issue")
    op.drop_index("monday_import_issue_batch_idx", table_name="monday_import_issue")
    op.drop_table("monday_import_issue")
    op.drop_index("monday_import_record_final_idx", table_name="monday_import_record")
    op.drop_index("monday_import_record_source_key_idx", table_name="monday_import_record")
    op.drop_index("monday_import_record_batch_idx", table_name="monday_import_record")
    op.drop_index("monday_import_record_row_key", table_name="monday_import_record")
    op.drop_table("monday_import_record")
    op.drop_index("monday_import_batch_context_idx", table_name="monday_import_batch")
    op.drop_index("monday_import_batch_identity_key", table_name="monday_import_batch")
    op.drop_table("monday_import_batch")
