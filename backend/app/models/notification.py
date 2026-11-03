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
    from app.models.user import User
    from app.models.workflow_extras import ReopenRequest

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


class EmailTemplate(Base):
    """Modelo visual de cada tipo de notificação, independente da regra.

    `notification_rule` continua guardando ativação, destinatários e prazos;
    aqui ficam apenas os textos e opções visuais usados na renderização.
    A primeira leitura de um tipo cria a linha a partir dos textos legados da
    regra, preservando o que já estava configurado antes desta tabela existir.
    """

    __tablename__ = "email_template"

    id: Mapped[str] = uuid_pk()
    kind: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    title_template: Mapped[str] = mapped_column(Text, nullable=False)
    intro_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    button_label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    footer_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    custom_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    use_custom_html: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_details: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_button: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_footer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    provider: Mapped[str] = mapped_column(String(16), nullable=False, default="graph")
    recipient_summary: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Alternativa HTML. Nula nos envios antigos, que continuam só com texto.
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
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


USER_NOTIFICATION_MODULE = "EQUIPMENT_PANEL"
USER_NOTIFICATION_EVENT_TYPES = (
    "REOPEN_REQUESTED",
    "REOPEN_APPROVED",
    "REOPEN_REJECTED",
    "KICKOFF",
    "FUP",
    "STARTUP_REMINDER",
    "NEGOTIATION_OVERDUE",
    "DELIVERY_REMINDER",
    "COMPLETED",
)


class UserNotification(Base):
    """Caixa interna persistente e individual do Painel de Equipamentos.

    Não representa envio de e-mail nem o evento de domínio. ``read_at`` é
    exclusivamente o estado de leitura deste destinatário.
    """

    __tablename__ = "user_notification"

    id: Mapped[str] = uuid_pk()
    recipient_user_id: Mapped[str] = mapped_column(
        ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    module_key: Mapped[str] = mapped_column(
        String(40), nullable=False, default=USER_NOTIFICATION_MODULE
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    equipment_id: Mapped[str | None] = mapped_column(
        ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True
    )
    reopen_request_id: Mapped[str | None] = mapped_column(
        ForeignKey("reopen_request.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)

    recipient: Mapped[User] = relationship("User", foreign_keys=[recipient_user_id])
    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_user_id])
    equipment: Mapped[Equipment | None] = relationship("Equipment")
    reopen_request: Mapped[ReopenRequest | None] = relationship("ReopenRequest")

    __table_args__ = (
        CheckConstraint(
            "module_key = 'EQUIPMENT_PANEL'", name="user_notification_module_check"
        ),
        CheckConstraint(
            "event_type IN ('REOPEN_REQUESTED','REOPEN_APPROVED','REOPEN_REJECTED',"
            "'KICKOFF','FUP','STARTUP_REMINDER','NEGOTIATION_OVERDUE',"
            "'DELIVERY_REMINDER','COMPLETED')",
            name="user_notification_event_type_check",
        ),
        Index(
            "user_notification_recipient_event_key",
            "recipient_user_id",
            "event_key",
            unique=True,
        ),
        Index(
            "user_notification_recipient_module_created_idx",
            "recipient_user_id",
            "module_key",
            "created_at",
        ),
        Index(
            "user_notification_recipient_unread_idx",
            "recipient_user_id",
            "module_key",
            postgresql_where=read_at.is_(None),
        ),
        Index("user_notification_reopen_request_idx", "reopen_request_id"),
    )
