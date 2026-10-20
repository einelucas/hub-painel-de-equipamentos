"""Eventos legados do workflow + configuração e outbox de e-mails."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk

if TYPE_CHECKING:
    from app.models.equipment import Equipment, WorkflowTransition

NOTIFICATION_EVENT_KINDS = ("KICKOFF", "FUP")
NOTIFICATION_EVENT_STATUSES = ("PENDING", "SENT", "FAILED")


class NotificationEvent(Base):
    __tablename__ = "notification_event"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    workflow_transition_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_transition.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    recipient_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)

    equipment: Mapped[Equipment] = relationship("Equipment")
    transition: Mapped[WorkflowTransition] = relationship("WorkflowTransition")

    __table_args__ = (
        CheckConstraint("kind IN ('KICKOFF','FUP')", name="notification_event_kind_check"),
        CheckConstraint(
            "status IN ('PENDING','SENT','FAILED')", name="notification_event_status_check"
        ),
        Index("notification_event_transition_kind_key", "workflow_transition_id", "kind", unique=True),
        Index("notification_event_equipment_id_idx", "equipment_id"),
    )


class NotificationRule(Base):
    __tablename__ = "notification_rule"

    id: Mapped[str] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    include_responsible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    days_before: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recipient_emails: Mapped[str] = mapped_column(Text, default="", nullable=False)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(Timestamp3, default=utcnow, onupdate=utcnow)


class EmailDelivery(Base):
    __tablename__ = "email_delivery"

    id: Mapped[str] = uuid_pk()
    dedup_key: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    equipment_id: Mapped[str | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    recipient_summary: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','ACCEPTED','SIMULATED','FAILED','SKIPPED')",
            name="email_delivery_status_check",
        ),
        Index("email_delivery_status_idx", "status", "created_at"),
        Index("email_delivery_equipment_idx", "equipment_id"),
    )
