from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.shared.schema import CamelModel


class SupplierCreateIn(CamelModel):
    legal_name: str = Field(min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def clean(self) -> SupplierCreateIn:
        if not self.legal_name.strip():
            raise ValueError("Razão social obrigatória")
        return self


class SupplierUpdateIn(CamelModel):
    legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    trade_name: str | None = Field(default=None, max_length=200)
    tax_id: str | None = Field(default=None, max_length=32)
    active: bool | None = None

    @model_validator(mode="after")
    def has_update(self) -> SupplierUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        if self.legal_name is not None and not self.legal_name.strip():
            raise ValueError("Razão social obrigatória")
        return self


class SupplierOut(CamelModel):
    id: str
    legal_name: str
    trade_name: str | None
    tax_id: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class SupplierListOut(CamelModel):
    items: list[SupplierOut]


class EquipmentSupplierLinkIn(CamelModel):
    supplier_id: str
    role: str | None = Field(default=None, max_length=80)
    is_primary: bool = False


class EquipmentSupplierUpdateIn(CamelModel):
    role: str | None = Field(default=None, max_length=80)
    is_primary: bool | None = None

    @model_validator(mode="after")
    def has_update(self) -> EquipmentSupplierUpdateIn:
        if not self.model_fields_set:
            raise ValueError("Informe ao menos um campo para atualizar")
        return self


class EquipmentSupplierOut(CamelModel):
    supplier: SupplierOut
    role: str | None
    is_primary: bool
    created_at: datetime


class EquipmentSupplierListOut(CamelModel):
    items: list[EquipmentSupplierOut]
