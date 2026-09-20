"""Staging e identidades externas para a futura migração do Monday."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class MondayImportBatch(Base):
    __tablename__ = "monday_import_batch"

    id: Mapped[str] = uuid_pk()
    project_context_id: Mapped[str] = mapped_column(
        ForeignKey("project_context.id", ondelete="RESTRICT"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(40), nullable=False, default="monday")
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    board_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sheet_name: Mapped[str] = mapped_column(String(200), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="STAGED")
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('STAGED', 'APPLIED', 'FAILED')", name="monday_import_batch_status_check"),
        Index(
            "monday_import_batch_identity_key",
            "project_context_id",
            "source_system",
            "file_sha256",
            unique=True,
        ),
        Index("monday_import_batch_context_idx", "project_context_id"),
    )


class MondayImportRecord(Base):
    __tablename__ = "monday_import_record"

    id: Mapped[str] = uuid_pk()
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("monday_import_batch.id", ondelete="CASCADE"), nullable=False
    )
    parent_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("monday_import_record.id", ondelete="CASCADE"), nullable=True
    )
    record_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_key: Mapped[str] = mapped_column(String(500), nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    final_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    final_entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "record_kind IN ('equipment', 'component')",
            name="monday_import_record_kind_check",
        ),
        Index(
            "monday_import_record_row_key",
            "batch_id",
            "record_kind",
            "row_number",
            unique=True,
        ),
        Index("monday_import_record_batch_idx", "batch_id"),
        Index("monday_import_record_source_key_idx", "source_key"),
        Index("monday_import_record_final_idx", "final_entity_type", "final_entity_id"),
    )


class MondayImportIssue(Base):
    __tablename__ = "monday_import_issue"

    id: Mapped[str] = uuid_pk()
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("monday_import_batch.id", ondelete="CASCADE"), nullable=False
    )
    record_id: Mapped[str | None] = mapped_column(
        ForeignKey("monday_import_record.id", ondelete="SET NULL"), nullable=True
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    field: Mapped[str | None] = mapped_column(String(160), nullable=True)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    raw_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint("severity IN ('warning', 'error')", name="monday_import_issue_severity_check"),
        Index("monday_import_issue_batch_idx", "batch_id"),
        Index("monday_import_issue_code_idx", "code"),
    )


class ExternalMapping(Base):
    """Vínculo genérico para não espalhar IDs do Monday pelo domínio."""

    __tablename__ = "external_mapping"

    id: Mapped[str] = uuid_pk()
    project_context_id: Mapped[str] = mapped_column(
        ForeignKey("project_context.id", ondelete="CASCADE"), nullable=False
    )
    source_system: Mapped[str] = mapped_column(String(40), nullable=False)
    source_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    identity_strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    raw_identity: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index(
            "external_mapping_source_key",
            "project_context_id",
            "source_system",
            "source_entity_type",
            "external_id",
            unique=True,
        ),
        Index("external_mapping_target_idx", "target_entity_type", "target_entity_id"),
    )
