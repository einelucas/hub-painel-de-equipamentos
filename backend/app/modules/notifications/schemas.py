from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.shared.schema import CamelModel


class NotificationEventOut(CamelModel):
    id: str
    equipment_id: str
    workflow_transition_id: str
    kind: Literal["KICKOFF", "FUP"]
    status: Literal["PENDING", "SENT", "FAILED"]
    recipient_summary: str | None
    failure_reason: str | None
    created_at: datetime
    sent_at: datetime | None


class NotificationEventListOut(CamelModel):
    items: list[NotificationEventOut]
