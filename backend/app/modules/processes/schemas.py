from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from app.modules.equipments.schemas import UserRefOut
from app.shared.schema import CamelModel

PurchaseRequestKind = Literal["SC", "OCI"]


class _ProcessUpdateIn(CamelModel):
    @model_validator(mode="after")
    def has_update(self) -> _ProcessUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class _ProcessOut(CamelModel):
    """Um processo ainda não iniciado é devolvido com `id` nulo e valores padrão."""

    id: str | None = None
    equipment_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NegotiationUpdateIn(_ProcessUpdateIn):
    equalized: bool | None = None
    negotiated_at: date | None = None


class NegotiationOut(_ProcessOut):
    equalized: bool = False
    negotiated_at: date | None = None


class LegalProcessUpdateIn(_ProcessUpdateIn):
    opened_at: date | None = None
    ticket_number: str | None = Field(default=None, max_length=80)
    draft_prepared: bool | None = None
    draft_approved: bool | None = None


class LegalProcessOut(_ProcessOut):
    opened_at: date | None = None
    ticket_number: str | None = None
    draft_prepared: bool = False
    draft_approved: bool = False


# --- Contract / PurchaseRequest / PurchaseOrder: 1:N com o equipamento
# (Etapa 7A) — cada linha é sempre um registro real e persistido, então
# (diferente de `_ProcessOut`) `id`/`createdAt`/`updatedAt` nunca são nulos
# aqui. `delivery_at` saiu do contrato: a janela de entrega agora é do
# equipamento (`EquipmentOut.contractualDeliveryStart/End`).


class ContractCreateIn(CamelModel):
    contract_number: str | None = Field(default=None, max_length=80)
    executed_at: date | None = None


class ContractUpdateIn(_ProcessUpdateIn):
    contract_number: str | None = Field(default=None, max_length=80)
    executed_at: date | None = None


class ContractFileOut(CamelModel):
    file_name: str
    file_content_type: str | None = None
    file_size_bytes: int | None = None
    file_uploaded_by: UserRefOut | None = None
    file_uploaded_at: datetime | None = None


class ContractOut(CamelModel):
    id: str
    equipment_id: str
    contract_number: str | None = None
    executed_at: date | None = None
    file: ContractFileOut | None = None
    created_at: datetime
    updated_at: datetime


class ContractListOut(CamelModel):
    items: list[ContractOut]


class PurchaseRequestCreateIn(CamelModel):
    kind: PurchaseRequestKind | None = None
    request_number: str | None = Field(default=None, max_length=80)
    requested_at: date | None = None


class PurchaseRequestUpdateIn(_ProcessUpdateIn):
    kind: PurchaseRequestKind | None = None
    request_number: str | None = Field(default=None, max_length=80)
    requested_at: date | None = None


class PurchaseRequestOut(CamelModel):
    id: str
    equipment_id: str
    kind: PurchaseRequestKind | None = None
    request_number: str | None = None
    requested_at: date | None = None
    created_at: datetime
    updated_at: datetime


class PurchaseRequestListOut(CamelModel):
    items: list[PurchaseRequestOut]


class PurchaseOrderCreateIn(CamelModel):
    order_number: str | None = Field(default=None, max_length=80)
    ordered_at: date | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class PurchaseOrderUpdateIn(_ProcessUpdateIn):
    order_number: str | None = Field(default=None, max_length=80)
    ordered_at: date | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)


class PurchaseOrderOut(CamelModel):
    id: str
    equipment_id: str
    order_number: str | None = None
    ordered_at: date | None = None
    amount: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class PurchaseOrderListOut(CamelModel):
    items: list[PurchaseOrderOut]


class EquipmentProcessesOut(CamelModel):
    negotiation: NegotiationOut
    legal: LegalProcessOut
    contracts: list[ContractOut]
    purchase_requests: list[PurchaseRequestOut]
    purchase_orders: list[PurchaseOrderOut]
