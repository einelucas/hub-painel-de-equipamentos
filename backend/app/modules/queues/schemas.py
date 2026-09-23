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
    # 0..N — ver nota de depreciação em `equipments.schemas.EquipmentOut.work_package`.
    work_packages: list[NamedRefOut]
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
    # Etapa 7A: "o contrato" vira "o mais recente" para exibição de fila —
    # a fonte de verdade é a lista em GET /equipments/{id}/contracts.
    contract_number: str | None
    executed_at: date | None
    # Etapa 7A: a janela de entrega contratual passou a ser do equipamento,
    # não de um contrato individual (Contract.delivery_at foi removido).
    contractual_delivery_start: date | None
    contractual_delivery_end: date | None


class SupplierRefOut(CamelModel):
    id: str
    legal_name: str
    trade_name: str | None


class ProcurementRowOut(QueueRowOut):
    responsible_user: UserRefOut | None
    primary_supplier: SupplierRefOut | None
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
