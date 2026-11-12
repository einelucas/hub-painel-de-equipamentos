"""Snapshots de revisão e recibos idempotentes da edição em lote."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class BulkEditBatch(Base):
    __tablename__ = "bulk_edit_batch"

    id: Mapped[str] = uuid_pk()
    preview_token: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("User.id", ondelete="RESTRICT"), nullable=False)
    project_context_id: Mapped[str] = mapped_column(
        ForeignKey("project_context.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id: Mapped[str | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=True
    )
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preview_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PREVIEW")
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    __table_args__ = (
        CheckConstraint(
            "target IN ('equipment', 'component')",
            name="bulk_edit_batch_target_check",
        ),
        CheckConstraint(
            "status IN ('PREVIEW', 'APPLIED')",
            name="bulk_edit_batch_status_check",
        ),
        CheckConstraint(
            "(target = 'equipment' AND equipment_id IS NULL) "
            "OR (target = 'component' AND equipment_id IS NOT NULL)",
            name="bulk_edit_batch_target_equipment_check",
        ),
        Index("bulk_edit_batch_actor_idempotency_key", "actor_user_id", "idempotency_key", unique=True),
        Index("bulk_edit_batch_expiry_idx", "expires_at"),
    )
