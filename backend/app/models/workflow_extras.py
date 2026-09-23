"""Etapa 7 — estado operacional, exceções de workflow, reabertura com
aprovação e comentários.

Todos auditáveis por natureza: cada mudança de estado especial ou exceção
grava seu próprio evento (usuário, data/hora, fase, justificativa), nunca só
um campo mutável em `Equipment`. Isso preserva histórico mesmo quando o
estado "atual" muda de novo.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.equipment import Equipment
from app.models.user import User

if TYPE_CHECKING:
    pass

OPERATIONAL_STATUSES = ("ACTIVE", "STANDBY", "CANCELLED", "IN_SANITATION")

# Ações que geram um OperationalStatusEvent — não são todas simétricas:
# entrar em STANDBY/CANCELLED/IN_SANITATION e sair de STANDBY/IN_SANITATION
# de volta para ACTIVE.
OPERATIONAL_STATUS_EVENT_KINDS = (
    "STANDBY_ENTERED",
    "STANDBY_LIFTED",
    "CANCELLED",
    "SANITATION_ENTERED",
    "SANITATION_ENDED",
)

WORKFLOW_EXCEPTION_TYPES = ("FIXED_SUPPLIER", "IMPORTATION")
WORKFLOW_EXCEPTION_STATUSES = ("ACTIVE", "COMPLETED", "CANCELLED")

REOPEN_REQUEST_STATUSES = ("PENDING", "APPROVED", "REJECTED")

# Etapa 7.1 — substitui WorkflowException/EXCEPTION_DISPENSED_REQUIREMENT_CODES.
REQUIREMENT_WAIVER_STATUSES = ("ACTIVE", "REVOKED")
REQUIREMENT_WAIVER_REASON_CODES = ("IMPORTATION", "FIXED_SUPPLIER", "EXCEPTIONAL_PROCESS", "OTHER")


class OperationalStatusEvent(Base):
    """Um evento por mudança de `Equipment.operational_status` (entrada ou
    saída de STANDBY/CANCELLED/IN_SANITATION). `Equipment.operational_status`
    é sempre derivado do evento mais recente — nunca editado direto sem
    passar por aqui, para a justificativa nunca ficar órfã."""

    __tablename__ = "operational_status_event"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # Estado resultante após este evento (o que `Equipment.operational_status`
    # passou a valer).
    resulting_status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Fase do equipamento no momento do evento — para STANDBY/CANCELLED é a
    # fase corrente; para SANITATION_ENTERED é a fase de origem (antes de
    # cair para 0).
    stage_at_event: Mapped[int] = mapped_column(nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    equipment: Mapped[Equipment] = relationship(back_populates="operational_status_events")
    actor: Mapped[User | None] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "kind IN ('STANDBY_ENTERED','STANDBY_LIFTED','CANCELLED',"
            "'SANITATION_ENTERED','SANITATION_ENDED')",
            name="operational_status_event_kind_check",
        ),
        CheckConstraint(
            "resulting_status IN ('ACTIVE','STANDBY','CANCELLED','IN_SANITATION')",
            name="operational_status_event_resulting_status_check",
        ),
        Index("operational_status_event_equipment_id_idx", "equipment_id"),
    )


class WorkflowException(Base):
    """Exceção explícita de fluxo (fornecedor fixo / importação). Nunca um
    `force=true` genérico: tipo, fase de origem, destino pretendido e
    justificativa são sempre conhecidos e auditáveis. O avanço continua
    manual, fase por fase — a exceção só dispensa validações específicas
    enquanto `status == 'ACTIVE'` (ver `app.modules.workflow.stages`)."""

    __tablename__ = "workflow_exception"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="ACTIVE")
    source_stage: Mapped[int] = mapped_column(nullable=False)
    intended_target_stage: Mapped[int] = mapped_column(nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)

    equipment: Mapped[Equipment] = relationship(back_populates="workflow_exceptions")
    created_by: Mapped[User | None] = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "type IN ('FIXED_SUPPLIER','IMPORTATION')", name="workflow_exception_type_check"
        ),
        CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','CANCELLED')",
            name="workflow_exception_status_check",
        ),
        CheckConstraint(
            "source_stage BETWEEN 0 AND 8", name="workflow_exception_source_stage_check"
        ),
        CheckConstraint(
            "intended_target_stage BETWEEN 0 AND 8",
            name="workflow_exception_target_stage_check",
        ),
        # Só uma exceção ativa por equipamento por vez — evita duas
        # justificativas concorrentes cobrindo o mesmo avanço manual.
        Index(
            "workflow_exception_one_active_key",
            "equipment_id",
            unique=True,
            postgresql_where=status.is_("ACTIVE"),
        ),
        Index("workflow_exception_equipment_id_idx", "equipment_id"),
    )


class ReopenRequest(Base):
    """Solicitação de reabertura com aprovação (Etapa 7C). O equipamento só
    muda de fase quando `status` vira `APPROVED` — nunca no momento da
    solicitação. `target_stage` é sempre anterior a `source_stage`."""

    __tablename__ = "reopen_request"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    source_stage: Mapped[int] = mapped_column(nullable=False)
    target_stage: Mapped[int] = mapped_column(nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="PENDING")
    requested_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    decided_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment: Mapped[Equipment] = relationship(back_populates="reopen_requests")
    requested_by: Mapped[User | None] = relationship("User", foreign_keys=[requested_by_id])
    decided_by: Mapped[User | None] = relationship("User", foreign_keys=[decided_by_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED')", name="reopen_request_status_check"
        ),
        CheckConstraint("source_stage BETWEEN 0 AND 8", name="reopen_request_source_stage_check"),
        CheckConstraint("target_stage BETWEEN 0 AND 8", name="reopen_request_target_stage_check"),
        CheckConstraint("target_stage < source_stage", name="reopen_request_target_before_source_check"),
        # Só uma solicitação pendente por equipamento por vez.
        Index(
            "reopen_request_one_pending_key",
            "equipment_id",
            unique=True,
            postgresql_where=status.is_("PENDING"),
        ),
        Index("reopen_request_equipment_id_idx", "equipment_id"),
    )


class RequirementWaiver(Base):
    """Etapa 7.1 — dispensa de um GRUPO de requisitos de uma fase
    específica (ex.: "não possui contrato"). Substitui o mecanismo rígido
    de `WorkflowException`/`EXCEPTION_DISPENSED_REQUIREMENT_CODES`: aqui
    `reason_code` é só classificação para auditoria — quem decide QUAIS
    grupos existem e quais são dispensáveis é o backend
    (`app.modules.workflow.stages`), nunca o motivo escolhido pelo usuário.
    Nunca apagado: revogar é um novo estado (`REVOKED`), auditável — o
    registro original (quem, quando, por quê) fica preservado."""

    __tablename__ = "requirement_waiver"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[int] = mapped_column(nullable=False)
    requirement_group_code: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(20), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="ACTIVE")
    created_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    revoked_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(Timestamp3, nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    equipment: Mapped[Equipment] = relationship(back_populates="requirement_waivers")
    created_by: Mapped[User | None] = relationship("User", foreign_keys=[created_by_id])
    revoked_by: Mapped[User | None] = relationship("User", foreign_keys=[revoked_by_id])

    __table_args__ = (
        CheckConstraint("stage BETWEEN 0 AND 8", name="requirement_waiver_stage_check"),
        CheckConstraint(
            "status IN ('ACTIVE','REVOKED')", name="requirement_waiver_status_check"
        ),
        CheckConstraint(
            "reason_code IN ('IMPORTATION','FIXED_SUPPLIER','EXCEPTIONAL_PROCESS','OTHER')",
            name="requirement_waiver_reason_code_check",
        ),
        CheckConstraint(
            "length(trim(justification)) > 0", name="requirement_waiver_justification_check"
        ),
        # Só uma dispensa ativa por equipamento+fase+grupo — evita duas
        # justificativas concorrentes cobrindo o mesmo requisito.
        Index(
            "requirement_waiver_one_active_key",
            "equipment_id",
            "stage",
            "requirement_group_code",
            unique=True,
            postgresql_where=status.is_("ACTIVE"),
        ),
        Index("requirement_waiver_equipment_id_idx", "equipment_id"),
    )


class Comment(Base):
    """Comentário do equipamento (Etapa 7E). Sem anexos — texto puro. Não é
    AuditLog nem WorkflowTransition: é um conceito à parte (conversa sobre o
    equipamento), não uma mudança de dado nem de fase."""

    __tablename__ = "comment"

    id: Mapped[str] = uuid_pk()
    equipment_id: Mapped[str] = mapped_column(
        ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

    equipment: Mapped[Equipment] = relationship(back_populates="comments")
    author: Mapped[User | None] = relationship("User")

    __table_args__ = (
        CheckConstraint("length(trim(text)) > 0", name="comment_text_not_blank_check"),
        Index("comment_equipment_id_idx", "equipment_id", "created_at"),
    )
