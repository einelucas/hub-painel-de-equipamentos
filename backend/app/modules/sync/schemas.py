from __future__ import annotations

from datetime import datetime
from typing import Any

from app.shared.schema import CamelModel


class SyncEventOut(CamelModel):
    id: int
    event_type: str
    entity_type: str
    entity_id: str
    unit_id: str
    project_context_id: str | None
    equipment_id: str | None
    actor_user_id: str | None
    payload: dict[str, Any] | None
    created_at: datetime


class SyncEventListOut(CamelModel):
    items: list[SyncEventOut]
    cursor: int
