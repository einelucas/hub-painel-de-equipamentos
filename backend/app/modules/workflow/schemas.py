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
    kind: Literal["advance", "reopen"]
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
    kind: Literal["transition", "change"]
    action: str
    title: str
    from_stage: int | None = None
    from_stage_label: str | None = None
    to_stage: int | None = None
    to_stage_label: str | None = None
    reason: str | None = None
    actor: UserRefOut | None = None
    occurred_at: datetime
    previous_data: dict[str, Any] | None = None
    new_data: dict[str, Any] | None = None


class HistoryOut(CamelModel):
    items: list[HistoryEntryOut]
