"""Etapa 7F — Kickoff/FUP: um evento por transição real, nunca fabricado.

Desacoplado de qualquer provedor de e-mail real (ainda não definido pelo
time de Automação/Microsoft): o adapter em uso hoje só registra o evento
(log/outbox), nunca finge enviar e-mail de verdade. `workflow_transition_id`
é único por (`kind`) — a mesma transição nunca gera dois eventos do mesmo
tipo, mesmo que o gatilho seja chamado de novo (idempotência).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
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
    # Resumo legível dos destinatários resolvidos no momento do envio
    # (responsável + superiores, quando um provedor existir) — não é a
    # fonte de verdade de "quem é responsável", só o retrato do envio.
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
        # Idempotência: a mesma transição nunca gera dois eventos do mesmo tipo.
        Index(
            "notification_event_transition_kind_key",
            "workflow_transition_id",
            "kind",
            unique=True,
        ),
        Index("notification_event_equipment_id_idx", "equipment_id"),
    )
