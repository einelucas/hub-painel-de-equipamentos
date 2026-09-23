from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.modules.equipments.schemas import UserRefOut
from app.shared.schema import CamelModel


class RequirementOut(CamelModel):
    code: str
    field: str
    message: str
    satisfied: bool


class TransitionOptionOut(CamelModel):
    target_stage: int
    target_stage_label: str
    # Etapa 7C: reabertura não é mais oferecida aqui — passou a ser
    # `ReopenRequest` (solicitação + aprovação). `kind` só tem "advance"
    # agora; o literal fica só como documentação do contrato.
    kind: Literal["advance"]
    can_execute: bool
    requires_reason: bool
    blocked_reason: str | None = None
    requirements: list[RequirementOut]
    satisfied_requirements: list[RequirementOut]
    missing_requirements: list[RequirementOut]


class AvailableTransitionsOut(CamelModel):
    current_stage: int
    current_stage_label: str
    transitions: list[TransitionOptionOut]


class TransitionRequestIn(CamelModel):
    target_stage: int = Field(ge=0, le=8)
    reason: str | None = Field(default=None, max_length=500)


class HistoryEntryOut(CamelModel):
    id: str
    kind: Literal["transition", "change", "operational_status"]
    action: str
    title: str
    from_stage: int | None = None
    from_stage_label: str | None = None
    to_stage: int | None = None
    to_stage_label: str | None = None
    reason: str | None = None
    # Etapa 7B: justificativa de Standby/Cancelado/Saneamento — visível
    # depois, no histórico, sem poluir o stepper de fases.
    justification: str | None = None
    actor: UserRefOut | None = None
    occurred_at: datetime
    previous_data: dict[str, Any] | None = None
    new_data: dict[str, Any] | None = None


class HistoryOut(CamelModel):
    items: list[HistoryEntryOut]


# --- Etapa 7B: estado operacional (Standby/Cancelado/Em Saneamento) ---


class JustificationIn(CamelModel):
    justification: str = Field(min_length=1, max_length=1000)


class OptionalJustificationIn(CamelModel):
    justification: str | None = Field(default=None, max_length=1000)


class OperationalStatusEventOut(CamelModel):
    id: str
    kind: str
    resulting_status: str
    stage_at_event: int
    justification: str
    actor: UserRefOut | None = None
    occurred_at: datetime


class EquipmentOperationalStatusOut(CamelModel):
    operational_status: str
    events: list[OperationalStatusEventOut]


# --- Etapa 7B: exceções de workflow (fornecedor fixo / importação) ---


class WorkflowExceptionCreateIn(CamelModel):
    type: Literal["FIXED_SUPPLIER", "IMPORTATION"]
    justification: str = Field(min_length=1, max_length=1000)


class WorkflowExceptionOut(CamelModel):
    id: str
    equipment_id: str
    type: Literal["FIXED_SUPPLIER", "IMPORTATION"]
    status: Literal["ACTIVE", "COMPLETED", "CANCELLED"]
    source_stage: int
    intended_target_stage: int
    justification: str
    created_by: UserRefOut | None = None
    created_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


class WorkflowExceptionListOut(CamelModel):
    items: list[WorkflowExceptionOut]


# --- Etapa 7C: reabertura com aprovação ---


class ReopenRequestCreateIn(CamelModel):
    target_stage: int = Field(ge=0, le=8)
    justification: str = Field(min_length=1, max_length=1000)


class ReopenDecisionIn(CamelModel):
    note: str | None = Field(default=None, max_length=1000)


class ReopenRequestOut(CamelModel):
    id: str
    equipment_id: str
    source_stage: int
    source_stage_label: str
    target_stage: int
    target_stage_label: str
    justification: str
    status: Literal["PENDING", "APPROVED", "REJECTED"]
    requested_by: UserRefOut | None = None
    requested_at: datetime
    decided_by: UserRefOut | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None


class ReopenRequestListOut(CamelModel):
    items: list[ReopenRequestOut]
