from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.modules.equipments.schemas import UserRefOut
from app.shared.schema import CamelModel

# --- Etapa 7.1: requisitos agrupados + dispensa (RequirementWaiver) ---


class RequirementWaiverOut(CamelModel):
    id: str
    equipment_id: str
    stage: int
    requirement_group_code: str
    requirement_group_label: str
    reason_code: Literal["IMPORTATION", "FIXED_SUPPLIER", "EXCEPTIONAL_PROCESS", "OTHER"]
    justification: str
    status: Literal["ACTIVE", "REVOKED"]
    created_by: UserRefOut | None = None
    created_at: datetime
    revoked_by: UserRefOut | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


class RequirementWaiverListOut(CamelModel):
    items: list[RequirementWaiverOut]


class RequirementWaiverCreateIn(CamelModel):
    stage: int = Field(ge=0, le=8)
    requirement_group_code: str = Field(min_length=1, max_length=40)
    reason_code: Literal["IMPORTATION", "FIXED_SUPPLIER", "EXCEPTIONAL_PROCESS", "OTHER"]
    justification: str = Field(min_length=1, max_length=1000)


class RequirementWaiverRevokeIn(CamelModel):
    revoke_reason: str | None = Field(default=None, max_length=1000)


class RequirementGroupOut(CamelModel):
    code: str
    label: str
    status: Literal["SATISFIED", "WAIVED", "MISSING"]
    waivable: bool
    fields: list[str]
    message: str
    waiver: RequirementWaiverOut | None = None


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
    # Etapa 7.1: substitui `requirements`/`satisfied_requirements`/
    # `missing_requirements` (por campo) — a UI não reconstrói a regra
    # localmente, só reflete o que o backend calculou por grupo.
    requirement_groups: list[RequirementGroupOut]


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


# Etapa 7B introduziu `WorkflowException` (FIXED_SUPPLIER/IMPORTATION) como
# exceção de fluxo rígida. Etapa 7.1 substitui esse mecanismo por
# `RequirementWaiver` (dispensa por grupo, ver acima) — os schemas
# `WorkflowException*` foram removidos daqui; o modelo/tabela seguem
# existindo só por compatibilidade (nenhum registro real em produção, ver
# docs/validation/etapa-07-1-requirement-waivers.md).


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
