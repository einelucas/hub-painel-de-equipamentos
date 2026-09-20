from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.modules.equipments.schemas import NamedRefOut, PaginationOut, UserRefOut
from app.shared.schema import CamelModel


class PendingRequirementOut(CamelModel):
    """O que falta para o equipamento avançar, vindo da mesma regra do workflow."""

    code: str
    field: str
    message: str


class QueueRowOut(CamelModel):
    equipment_id: str
    equipment_name: str
    unit: NamedRefOut
    project_context: NamedRefOut
    current_stage: int
    current_stage_name: str
    next_stage: int | None
    next_stage_name: str | None
    pending: list[PendingRequirementOut]


class EngineeringRowOut(QueueRowOut):
    discipline: NamedRefOut | None
    area: NamedRefOut | None
    work_package: NamedRefOut | None
    responsible_user: UserRefOut | None
    startup_at: date | None
    criticality: str | None
    components_count: int


class LegalRowOut(QueueRowOut):
    responsible_user: UserRefOut | None
    opened_at: date | None
    ticket_number: str | None
    draft_prepared: bool
    draft_approved: bool
    contract_number: str | None
    executed_at: date | None
    delivery_at: date | None


class ProcurementRowOut(QueueRowOut):
    responsible_user: UserRefOut | None
    kind: str | None
    request_number: str | None
    requested_at: date | None
    order_number: str | None
    ordered_at: date | None
    amount: Decimal | None


class EngineeringQueueOut(CamelModel):
    items: list[EngineeringRowOut]
    pagination: PaginationOut


class LegalQueueOut(CamelModel):
    items: list[LegalRowOut]
    pagination: PaginationOut


class ProcurementQueueOut(CamelModel):
    items: list[ProcurementRowOut]
    pagination: PaginationOut
